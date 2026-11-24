"""
Shared Axis-Calibration Engine for Stage-1 Matched-Budget Dev Engineering Pilot.

Implements the exact pre-locked specification in `STAGE1_DEV_PROTOCOL.md`:
  - Arm B (Single-resolution 1.0x paper-inspired control):
      4 OCR calls/axis (8 calls/image):
        View B1: (scale=1.0, enhanced)  x {PSM 6, PSM 11}
        View B2: (scale=1.0, clean_gray) x {PSM 6, PSM 11}
  - Arm C (Matched two-resolution 1.0x + 2.0x candidate):
      4 OCR calls/axis (8 calls/image):
        View C1: (scale=1.0, enhanced)  x {PSM 6, PSM 11}
        View C2: (scale=2.0, enhanced)  x {PSM 6, PSM 11}

Both Arm B and Arm C share the IDENTICAL:
  - image-only axis ROI localization (no GT, no per-image thresholds),
  - numeric token parser, adjacent sign merge, image-grounded dropped-minus hypothesis,
  - scale-adaptive band clustering (y_center for X, right-edge x_right for Y),
  - physical tick-slot grouping preserving multi-view hypotheses,
  - original-image tick-geometry alignment (no mandatory snap-to-black),
  - held-out leave-one-tick-out (LOTO) residual agreement & OLS integer-anchor projection,
  - deterministic fallback policy to unmodified upstream LinePilot 8fb89a62 (Arm A).

ZERO ground-truth ticks, values, colors, or traced series are ever passed to this module.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
from pathlib import Path
import re
import statistics
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

# Ensure vendored Tesseract & upstream AxisReader helpers are importable
_ROOT = Path(__file__).resolve().parent
_DIGITIZER_DIR = _ROOT / "upstream_linepilot" / "Digitizer"
if str(_DIGITIZER_DIR) not in sys.path:
    sys.path.insert(0, str(_DIGITIZER_DIR))

import AxisReader  # noqa: E402
import pytesseract  # noqa: E402
from pytesseract import Output  # noqa: E402


# Pre-locked protocol constants (STAGE1_DEV_PROTOCOL.md §3)
ROI_PAD_PX = 16
TESS_WHITELIST = "0123456789.-+,eE"
SCI_RE = re.compile(r"^[-+]?(?:\d+(?:\.\d*)?|\.\d+)[eE][-+]?\d+$")

LOTO_INLIER_REL_TOL = 0.03
LOTO_MAX_RESID_GATE = 0.035
LOTO_MED_RESID_GATE = 0.015
LOTO_MIN_SPAN_FRAC = 0.25
TWO_TICK_MIN_SPAN_FRAC = 0.50
TWO_TICK_MIN_VOTES = 2
TWO_TICK_MIN_CONF = 70.0
MAX_SLOTS_FOR_RANSAC = 25


@dataclass(frozen=True)
class OcrViewSpec:
    name: str
    scale: float
    preprocess: str  # "enhanced" or "clean_gray"
    psm: int


ARM_B_VIEWS: Tuple[OcrViewSpec, ...] = (
    OcrViewSpec("b_1x_enh_psm6", 1.0, "enhanced", 6),
    OcrViewSpec("b_1x_enh_psm11", 1.0, "enhanced", 11),
    OcrViewSpec("b_1x_clean_psm6", 1.0, "clean_gray", 6),
    OcrViewSpec("b_1x_clean_psm11", 1.0, "clean_gray", 11),
)

ARM_C_VIEWS: Tuple[OcrViewSpec, ...] = (
    OcrViewSpec("c_1x_enh_psm6", 1.0, "enhanced", 6),
    OcrViewSpec("c_1x_enh_psm11", 1.0, "enhanced", 11),
    OcrViewSpec("c_2x_enh_psm6", 2.0, "enhanced", 6),
    OcrViewSpec("c_2x_enh_psm11", 2.0, "enhanced", 11),
)


@dataclass(frozen=True)
class RawToken:
    value: float
    left: float
    top: float
    width: float
    height: float
    conf: float
    view_name: str
    scale: float
    synthetic_negated: bool = False

    @property
    def cx(self) -> float:
        return self.left + self.width / 2.0

    @property
    def cy(self) -> float:
        return self.top + self.height / 2.0

    @property
    def right(self) -> float:
        return self.left + self.width


@dataclass(frozen=True)
class SlotHypothesis:
    pos: float
    value: float
    votes: int
    mean_conf: float
    max_conf: float
    views: Tuple[str, ...]
    synthetic_negated: bool = False


@dataclass
class AxisFitResult:
    axis: str  # "x" or "y"
    accepted: bool
    accept_reason: str
    slope: Optional[float] = None
    intercept: Optional[float] = None
    anchor_px_lo: Optional[int] = None
    anchor_px_hi: Optional[int] = None
    anchor_val_lo: Optional[float] = None
    anchor_val_hi: Optional[float] = None
    n_raw_tokens: int = 0
    n_band_tokens: int = 0
    n_slots: int = 0
    n_inliers: int = 0
    total_inlier_votes: int = 0
    inlier_mean_conf: Optional[float] = None
    med_loto_resid: Optional[float] = None
    max_loto_resid: Optional[float] = None
    inlier_pixel_span: Optional[float] = None
    inliers: List[Dict[str, Any]] = field(default_factory=list)
    per_view_token_counts: Dict[str, int] = field(default_factory=dict)


@dataclass
class RoiGeometry:
    width: int
    height: int
    plot_left: int
    plot_right: int
    plot_top: int
    plot_bottom: int
    x_roi: Tuple[int, int, int, int]  # (x0, y0, x1, y1)
    y_roi: Tuple[int, int, int, int]  # (x0, y0, x1, y1)
    spine_tier_h: str
    spine_tier_v: str


@dataclass
class CalibrationProposal:
    arm: str
    accepted: bool
    use_fallback_arm_a: bool
    tick_points: Optional[List[Tuple[int, int]]]  # [xmin_pt, xmax_pt, ymin_pt, ymax_pt]
    axis_values: Optional[List[float]]            # [xmin, xmax, ymin, ymax]
    ocr_call_count: int
    roi_geometry: Dict[str, Any]
    x_fit: Dict[str, Any]
    y_fit: Dict[str, Any]
    timing_s: Dict[str, float]


def _longest_contiguous_run_1d(arr_bool: np.ndarray) -> int:
    if not arr_bool.any():
        return 0
    # Pad with False on both sides and diff to find run lengths in C speed
    padded = np.empty(arr_bool.size + 2, dtype=np.int8)
    padded[0] = 0
    padded[-1] = 0
    padded[1:-1] = arr_bool.view(np.int8)
    diffs = np.diff(padded)
    starts = np.where(diffs == 1)[0]
    ends = np.where(diffs == -1)[0]
    if starts.size == 0:
        return 0
    return int(np.max(ends - starts))


def _collapse_bands(indices: Sequence[int], gap: int = 2) -> List[Tuple[int, int]]:
    if not indices:
        return []
    bands: List[Tuple[int, int]] = []
    start = int(indices[0])
    prev = start
    for idx in indices[1:]:
        val = int(idx)
        if val - prev <= gap:
            prev = val
        else:
            bands.append((start, prev))
            start = val
            prev = val
    bands.append((start, prev))
    return bands


def _find_structural_lines(
    gray: np.ndarray,
    ink_box: Tuple[int, int, int, int],
    threshold: int,
    min_run_frac: float = 0.35,
    require_contiguous: bool = True,
) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]:
    x0, y0, x1, y1 = ink_box
    sub = gray[y0 : y1 + 1, x0 : x1 + 1] < threshold
    ink_h, ink_w = sub.shape
    min_h_run = max(12, int(round(min_run_frac * ink_w)))
    min_v_run = max(12, int(round(min_run_frac * ink_h)))

    row_sums = sub.sum(axis=1)
    cand_rows = np.where(row_sums >= min_h_run)[0]
    if require_contiguous:
        h_hits = [int(y0 + r) for r in cand_rows if _longest_contiguous_run_1d(sub[r, :]) >= min_h_run]
    else:
        h_hits = [int(y0 + r) for r in cand_rows]

    col_sums = sub.sum(axis=0)
    cand_cols = np.where(col_sums >= min_v_run)[0]
    if require_contiguous:
        v_hits = [int(x0 + c) for c in cand_cols if _longest_contiguous_run_1d(sub[:, c]) >= min_v_run]
    else:
        v_hits = [int(x0 + c) for c in cand_cols]

    return _collapse_bands(h_hits), _collapse_bands(v_hits)


def detect_axis_rois(pil_rgb: Image.Image) -> RoiGeometry:
    gray = np.asarray(pil_rgb.convert("L"), dtype=np.uint8)
    h, w = gray.shape
    ink = gray < 245
    if ink.any():
        ys, xs = np.where(ink)
        ink_box = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
    else:
        ink_box = (0, 0, w - 1, h - 1)

    h_t1, v_t1 = _find_structural_lines(gray, ink_box, threshold=200, min_run_frac=0.35, require_contiguous=True)
    h_t2, v_t2 = _find_structural_lines(gray, ink_box, threshold=246, min_run_frac=0.45, require_contiguous=False)

    # Bottom / Top horizontal boundaries
    bot_t1 = [b for b in h_t1 if int(0.48 * h) <= b[1] <= int(0.97 * h)]
    bot_t2 = [b for b in h_t2 if int(0.48 * h) <= b[1] <= int(0.97 * h)]
    if bot_t1:
        plot_bottom = bot_t1[-1][1]
        tier_h = "tier1_dark"
    elif bot_t2:
        plot_bottom = bot_t2[-1][1]
        tier_h = "tier2_light"
    else:
        plot_bottom = int(round(0.82 * h))
        tier_h = "fallback_frac"

    top_t1 = [b for b in h_t1 if int(0.01 * h) <= b[0] <= int(0.45 * h)]
    top_t2 = [b for b in h_t2 if int(0.01 * h) <= b[0] <= int(0.45 * h)]
    if top_t1:
        plot_top = top_t1[0][0]
    elif top_t2:
        plot_top = top_t2[0][0]
    else:
        plot_top = int(round(0.06 * h))

    # Left / Right vertical boundaries
    left_t1 = [b for b in v_t1 if int(0.03 * w) <= b[0] <= int(0.48 * w)]
    left_t2 = [b for b in v_t2 if int(0.03 * w) <= b[0] <= int(0.48 * w)]
    if left_t1:
        plot_left = left_t1[0][0]
        tier_v = "tier1_dark"
    elif left_t2:
        plot_left = left_t2[0][0]
        tier_v = "tier2_light"
    else:
        plot_left = int(round(0.14 * w))
        tier_v = "fallback_frac"

    right_t1 = [b for b in v_t1 if int(0.55 * w) <= b[1] <= int(0.99 * w)]
    right_t2 = [b for b in v_t2 if int(0.55 * w) <= b[1] <= int(0.99 * w)]
    if right_t1:
        plot_right = right_t1[-1][1]
    elif right_t2:
        plot_right = right_t2[-1][1]
    else:
        plot_right = int(round(0.96 * w))

    # Sanity guard on ordering
    if plot_right <= plot_left + 10:
        plot_left = int(round(0.14 * w))
        plot_right = int(round(0.96 * w))
    if plot_bottom <= plot_top + 10:
        plot_top = int(round(0.06 * h))
        plot_bottom = int(round(0.82 * h))

    # X_roi (bottom axis neighborhood)
    pad_x = max(12, int(round(0.06 * w)))
    x_roi_x0 = max(0, plot_left - pad_x)
    x_roi_x1 = w
    if h - plot_bottom < 12:
        x_roi_y0 = max(0, plot_bottom - 2)
    else:
        x_roi_y0 = min(h - 1, plot_bottom + 1)
    x_roi_y1 = h

    # Y_roi (left axis neighborhood)
    pad_y = max(12, int(round(0.06 * h)))
    y_roi_x0 = 0
    if plot_left < 12:
        y_roi_x1 = min(w, plot_left + 2)
    else:
        y_roi_x1 = max(1, plot_left - 1)
    y_roi_y0 = max(0, plot_top - pad_y)
    y_roi_y1 = min(h, plot_bottom + pad_y)

    return RoiGeometry(
        width=w,
        height=h,
        plot_left=plot_left,
        plot_right=plot_right,
        plot_top=plot_top,
        plot_bottom=plot_bottom,
        x_roi=(x_roi_x0, x_roi_y0, x_roi_x1, x_roi_y1),
        y_roi=(y_roi_x0, y_roi_y0, y_roi_x1, y_roi_y1),
        spine_tier_h=tier_h,
        spine_tier_v=tier_v,
    )


def _preprocess_roi(crop_rgb: Image.Image, scale: float, mode: str) -> Image.Image:
    if scale != 1.0:
        nw = max(1, int(round(crop_rgb.width * scale)))
        nh = max(1, int(round(crop_rgb.height * scale)))
        work = crop_rgb.resize((nw, nh), Image.Resampling.BICUBIC)
    else:
        work = crop_rgb
    padded = ImageOps.expand(work, border=ROI_PAD_PX, fill=(255, 255, 255))
    gray = ImageOps.grayscale(padded)
    gray = ImageOps.autocontrast(gray)
    if mode == "enhanced":
        gray = ImageEnhance.Contrast(gray).enhance(1.6)
        gray = gray.filter(ImageFilter.UnsharpMask(radius=1.2, percent=180, threshold=3))
    elif mode == "clean_gray":
        pass
    else:
        raise ValueError(f"Unknown preprocess mode: {mode}")
    return gray


def _parse_numeric_text(text: str) -> Optional[float]:
    s = text.strip().replace(",", "").replace("\u2212", "-").replace("\u2013", "-")
    if not s:
        return None
    if any(ch.isalpha() for ch in s) and not SCI_RE.match(s):
        return None
    cleaned = re.sub(r"(?<=\d),(?=\d)", "", s)
    m = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", cleaned)
    if not m:
        return None
    try:
        v = float(m.group(0))
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def _run_ocr_view_on_roi(
    crop_rgb: Image.Image,
    roi_origin: Tuple[int, int],
    view: OcrViewSpec,
    axis: str,
) -> List[RawToken]:
    roi_x0, roi_y0 = roi_origin
    roi_w, roi_h = crop_rgb.size
    if roi_w < 2 or roi_h < 2:
        return []

    AxisReader._configure_tesseract()
    proc = _preprocess_roi(crop_rgb, scale=view.scale, mode=view.preprocess)
    config = f"--psm {view.psm} -c tessedit_char_whitelist={TESS_WHITELIST}"
    data = pytesseract.image_to_data(proc, output_type=Output.DICT, config=config)

    # First collect raw non-empty boxes mapped back to exact original float image coordinates
    raw_items: List[Dict[str, Any]] = []
    n_items = len(data.get("text", []))
    for i in range(n_items):
        txt = (data["text"][i] or "").strip()
        if not txt:
            continue
        l_s = float(data["left"][i])
        t_s = float(data["top"][i])
        w_s = float(data["width"][i])
        h_s = float(data["height"][i])
        if w_s <= 0.0 or h_s <= 0.0:
            continue
        left = roi_x0 + (l_s - ROI_PAD_PX) / view.scale
        top = roi_y0 + (t_s - ROI_PAD_PX) / view.scale
        width = w_s / view.scale
        height = h_s / view.scale
        # Reject full-ROI border artifacts along the axis direction (a Y-tick label can span up to 95% of narrow Y_roi width,
        # and an X-tick label can span up to 95% of short X_roi height!)
        if axis == "x" and width > 0.60 * roi_w:
            continue
        if axis == "y" and height > 0.45 * roi_h:
            continue
        if width > 0.98 * roi_w and height > 0.98 * roi_h:
            continue
        try:
            conf = float(data["conf"][i])
        except (IndexError, TypeError, ValueError):
            conf = -1.0
        raw_items.append(
            {
                "text": txt,
                "left": left,
                "top": top,
                "width": width,
                "height": height,
                "conf": conf,
            }
        )

    # Merge adjacent standalone sign tokens immediately left of a numeric token on the same line
    raw_items.sort(key=lambda d: (d["top"], d["left"]))
    used_sign: set[int] = set()
    tokens: List[RawToken] = []

    for idx, item in enumerate(raw_items):
        if idx in used_sign:
            continue
        txt_norm = item["text"].replace("\u2212", "-").replace("\u2013", "-")
        if txt_norm in {"-", "+"}:
            # Look for immediate right neighbor numeric token on the same line
            sign_right = item["left"] + item["width"]
            sign_cy = item["top"] + item["height"] / 2.0
            best_j = None
            best_gap = float("inf")
            for j, cand in enumerate(raw_items):
                if j == idx or j in used_sign:
                    continue
                val_c = _parse_numeric_text(cand["text"])
                if val_c is None:
                    continue
                cand_cy = cand["top"] + cand["height"] / 2.0
                gap = cand["left"] - sign_right
                if abs(sign_cy - cand_cy) <= 0.6 * cand["height"] and -0.25 * cand["height"] <= gap <= 1.2 * cand["height"]:
                    if gap < best_gap:
                        best_gap = gap
                        best_j = j
            if best_j is not None:
                cand = raw_items[best_j]
                merged_val = _parse_numeric_text(txt_norm + cand["text"].lstrip("+-"))
                if merged_val is not None:
                    u_left = min(item["left"], cand["left"])
                    u_top = min(item["top"], cand["top"])
                    u_right = max(item["left"] + item["width"], cand["left"] + cand["width"])
                    u_bottom = max(item["top"] + item["height"], cand["top"] + cand["height"])
                    used_sign.add(idx)
                    used_sign.add(best_j)
                    tokens.append(
                        RawToken(
                            value=merged_val,
                            left=u_left,
                            top=u_top,
                            width=u_right - u_left,
                            height=u_bottom - u_top,
                            conf=max(cand["conf"], 0.0),
                            view_name=view.name,
                            scale=view.scale,
                        )
                    )
                    continue
            continue

        val = _parse_numeric_text(item["text"])
        if val is None:
            continue
        tokens.append(
            RawToken(
                value=val,
                left=item["left"],
                top=item["top"],
                width=item["width"],
                height=item["height"],
                conf=max(item["conf"], 0.0),
                view_name=view.name,
                scale=view.scale,
            )
        )

    return tokens


def _augment_dropped_minus_hypotheses(
    tokens: List[RawToken],
    gray_orig: np.ndarray,
) -> List[RawToken]:
    """Image-grounded dropped-minus check (STAGE1_DEV_PROTOCOL.md §3.3).

    Only emits a secondary negated hypothesis (-val, 0.85 * conf) for positive tokens
    when dark ink actually exists immediately left of the token box at vertical midline.
    """
    h_img, w_img = gray_orig.shape
    out = list(tokens)
    for tok in tokens:
        if tok.value <= 0.0:
            continue
        h = max(4.0, tok.height)
        x0 = max(0, int(math.floor(tok.left - 0.85 * h)))
        x1 = max(x0, min(w_img, int(math.ceil(tok.left - 1.0))))
        y0 = max(0, int(math.floor(tok.cy - 0.25 * h)))
        y1 = max(y0, min(h_img, int(math.ceil(tok.cy + 0.25 * h))))
        if x1 - x0 < 2 or y1 - y0 < 1:
            continue
        patch = gray_orig[y0:y1, x0:x1]
        min_val = float(np.min(patch))
        # Local context background around the strip
        bg_y0 = max(0, int(math.floor(tok.top - 0.5 * h)))
        bg_y1 = min(h_img, int(math.ceil(tok.top + 1.5 * h)))
        bg_patch = gray_orig[bg_y0:bg_y1, x0 : min(w_img, int(math.ceil(tok.right)))]
        local_bg = float(np.percentile(bg_patch, 90)) if bg_patch.size else 255.0
        if min_val < 180.0 and (local_bg - min_val) >= 35.0:
            out.append(
                RawToken(
                    value=-tok.value,
                    left=tok.left,
                    top=tok.top,
                    width=tok.width,
                    height=tok.height,
                    conf=tok.conf * 0.85,
                    view_name=tok.view_name + ":neg",
                    scale=tok.scale,
                    synthetic_negated=True,
                )
            )
    return out


def _cluster_axis_bands(
    tokens: List[RawToken],
    axis: str,
    img_w: int,
    img_h: int,
) -> List[List[RawToken]]:
    if not tokens:
        return []
    heights = [t.height for t in tokens if not t.synthetic_negated and t.height > 0]
    med_h = statistics.median(heights) if heights else 10.0
    if axis == "x":
        tol = max(6.0, 0.55 * med_h, 0.015 * min(img_w, img_h))
        key_fn = lambda t: t.cy
    else:
        # Right-edge alignment for Y-axis tick labels
        tol = max(8.0, 0.85 * med_h, 0.020 * min(img_w, img_h))
        key_fn = lambda t: t.right

    ordered = sorted(tokens, key=key_fn)
    bands: List[List[RawToken]] = []
    cur = [ordered[0]]
    cur_mean = key_fn(ordered[0])
    for tok in ordered[1:]:
        pos = key_fn(tok)
        if abs(pos - cur_mean) <= tol:
            cur.append(tok)
            cur_mean = sum(key_fn(t) for t in cur) / len(cur)
        else:
            bands.append(cur)
            cur = [tok]
            cur_mean = pos
    bands.append(cur)
    return bands


def _group_into_physical_slots(
    band: List[RawToken],
    axis: str,
) -> List[List[SlotHypothesis]]:
    if not band:
        return []
    heights = [t.height for t in band if not t.synthetic_negated and t.height > 0]
    med_h = statistics.median(heights) if heights else 10.0
    slot_tol = max(6.0, 0.65 * med_h)
    pos_fn = (lambda t: t.cx) if axis == "x" else (lambda t: t.cy)

    ordered = sorted(band, key=pos_fn)
    raw_slots: List[List[RawToken]] = []
    cur = [ordered[0]]
    cur_pos = pos_fn(ordered[0])
    for tok in ordered[1:]:
        p = pos_fn(tok)
        if abs(p - cur_pos) <= slot_tol:
            cur.append(tok)
            cur_pos = sum(pos_fn(t) for t in cur) / len(cur)
        else:
            raw_slots.append(cur)
            cur = [tok]
            cur_pos = p
    raw_slots.append(cur)

    # Collapse identical numeric readings inside each physical slot into SlotHypothesis objects
    slot_hyps: List[List[SlotHypothesis]] = []
    for slot in raw_slots:
        by_val: Dict[float, List[RawToken]] = {}
        for tok in slot:
            # Quantize float key slightly to avoid -0.0 / 0.0 split or float repr jitter
            val_key = 0.0 if abs(tok.value) == 0.0 else float(f"{tok.value:.10g}")
            by_val.setdefault(val_key, []).append(tok)

        hyps: List[SlotHypothesis] = []
        for val_key, grp in by_val.items():
            # Count distinct base views supporting this reading
            base_views = tuple(sorted({t.view_name.split(":")[0] for t in grp}))
            all_synth = all(t.synthetic_negated for t in grp)
            confs = [t.conf for t in grp]
            # Robust unweighted median position prevents a single shifted box with higher
            # nominal confidence from overriding multiple agreeing views.
            pos = float(statistics.median(pos_fn(t) for t in grp))
            hyps.append(
                SlotHypothesis(
                    pos=pos,
                    value=val_key,
                    votes=len(base_views),
                    mean_conf=sum(confs) / len(confs),
                    max_conf=max(confs),
                    views=base_views,
                    synthetic_negated=all_synth,
                )
            )
        hyps.sort(key=lambda h: (not h.synthetic_negated, h.votes, h.mean_conf), reverse=True)
        slot_hyps.append(hyps[:4])

    # Cap total slots for O(1) bounded RANSAC if extremely noisy
    if len(slot_hyps) > MAX_SLOTS_FOR_RANSAC:
        slot_hyps.sort(
            key=lambda hs: (max(h.votes for h in hs), max(h.max_conf for h in hs)),
            reverse=True,
        )
        slot_hyps = slot_hyps[:MAX_SLOTS_FOR_RANSAC]
        slot_hyps.sort(key=lambda hs: hs[0].pos)

    return slot_hyps


def _ols_fit(ps: Sequence[float], vs: Sequence[float]) -> Optional[Tuple[float, float]]:
    n = len(ps)
    if n < 2:
        return None
    mp = sum(ps) / n
    mv = sum(vs) / n
    sxx = sum((p - mp) ** 2 for p in ps)
    if sxx < 1e-9:
        return None
    sxy = sum((p - mp) * (v - mv) for p, v in zip(ps, vs))
    slope = sxy / sxx
    intercept = mv - slope * mp
    if not (math.isfinite(slope) and math.isfinite(intercept)):
        return None
    return slope, intercept


def _compute_loto_residuals(ps: Sequence[float], vs: Sequence[float], v_span: float) -> Optional[Tuple[float, float]]:
    m = len(ps)
    if m < 3 or v_span <= 0.0:
        return None
    resids: List[float] = []
    for k in range(m):
        p_sub = [ps[i] for i in range(m) if i != k]
        v_sub = [vs[i] for i in range(m) if i != k]
        fit_sub = _ols_fit(p_sub, v_sub)
        if fit_sub is None:
            return None
        a_sub, b_sub = fit_sub
        pred = a_sub * ps[k] + b_sub
        resids.append(abs(vs[k] - pred) / v_span)
    return float(statistics.median(resids)), float(max(resids))


def _fit_axis_from_band(
    band: List[RawToken],
    axis: str,
    expected_plot_span: float,
    anchor_ortho_ref: float,
) -> AxisFitResult:
    prefer_sign = 1.0 if axis == "x" else -1.0
    slot_hyps = _group_into_physical_slots(band, axis=axis)
    n_slots = len(slot_hyps)
    min_pair_dp = max(10.0, 0.05 * expected_plot_span)

    best_loto: Optional[Tuple[Tuple[Any, ...], Dict[str, Any]]] = None
    best_two_tick: Optional[Tuple[Tuple[Any, ...], Dict[str, Any]]] = None

    for i in range(n_slots):
        for j in range(i + 1, n_slots):
            for hi in slot_hyps[i]:
                for hj in slot_hyps[j]:
                    dp = hj.pos - hi.pos
                    if abs(dp) < min_pair_dp:
                        continue
                    dv = hj.value - hi.value
                    slope0 = dv / dp
                    if slope0 * prefer_sign <= 0.0:
                        continue
                    intercept0 = hi.value - slope0 * hi.pos

                    # Estimate axis value span across all observed slots
                    all_pos = [hs[0].pos for hs in slot_hyps]
                    span_est = abs(slope0) * max(abs(dp), max(all_pos) - min(all_pos))
                    if span_est <= 0.0 or not math.isfinite(span_est):
                        continue

                    # Collect at most 1 best hypothesis per slot within LOTO_INLIER_REL_TOL,
                    # and enforce strictly distinct numeric tick values across inliers.
                    chosen_by_val: Dict[float, Tuple[Tuple[Any, ...], SlotHypothesis]] = {}
                    for s_idx, hs in enumerate(slot_hyps):
                        best_h = None
                        best_err = float("inf")
                        for h in hs:
                            err = abs(h.value - (slope0 * h.pos + intercept0)) / span_est
                            if err <= LOTO_INLIER_REL_TOL and err < best_err:
                                best_err = err
                                best_h = h
                        if best_h is not None:
                            vk = best_h.value
                            v_rank = (not best_h.synthetic_negated, best_h.votes, -best_err, best_h.mean_conf)
                            if vk not in chosen_by_val or v_rank > chosen_by_val[vk][0]:
                                chosen_by_val[vk] = (v_rank, best_h)
                    chosen = [pair[1] for pair in chosen_by_val.values()]

                    m = len(chosen)
                    if m < 2:
                        continue

                    ps = [h.pos for h in chosen]
                    vs = [h.value for h in chosen]
                    ols = _ols_fit(ps, vs)
                    if ols is None:
                        continue
                    slope, intercept = ols
                    if slope * prefer_sign <= 0.0:
                        continue

                    p_min = min(ps)
                    p_max = max(ps)
                    px_span = p_max - p_min
                    v_span = abs(slope) * px_span
                    if v_span <= 0.0 or px_span < min_pair_dp:
                        continue

                    total_votes = sum(h.votes for h in chosen)
                    mean_conf = sum(h.mean_conf for h in chosen) / m
                    non_synth_count = sum(1 for h in chosen if not h.synthetic_negated)

                    if m >= 3:
                        # Require at least 2 non-synthetic OCR detections so we never fit pure synthetic guesses
                        if non_synth_count < 2:
                            continue
                        loto = _compute_loto_residuals(ps, vs, v_span)
                        if loto is None:
                            continue
                        med_r, max_r = loto
                        if (
                            max_r <= LOTO_MAX_RESID_GATE
                            and med_r <= LOTO_MED_RESID_GATE
                            and px_span >= LOTO_MIN_SPAN_FRAC * expected_plot_span
                        ):
                            rank_key = (
                                m,
                                non_synth_count,
                                -round(med_r, 3),
                                total_votes,
                                round(px_span / max(1.0, expected_plot_span), 2),
                                mean_conf,
                            )
                            if best_loto is None or rank_key > best_loto[0]:
                                best_loto = (
                                    rank_key,
                                    {
                                        "slope": slope,
                                        "intercept": intercept,
                                        "chosen": chosen,
                                        "px_span": px_span,
                                        "med_r": med_r,
                                        "max_r": max_r,
                                        "total_votes": total_votes,
                                        "mean_conf": mean_conf,
                                    },
                                )
                    elif m == 2:
                        # Strict secondary two-tick multiview-verified gate (no synthetic flips allowed)
                        if (
                            non_synth_count == 2
                            and px_span >= TWO_TICK_MIN_SPAN_FRAC * expected_plot_span
                            and all(h.votes >= TWO_TICK_MIN_VOTES for h in chosen)
                            and min(h.max_conf for h in chosen) >= TWO_TICK_MIN_CONF
                        ):
                            rank_key = (
                                total_votes,
                                px_span / max(1.0, expected_plot_span),
                                mean_conf,
                            )
                            if best_two_tick is None or rank_key > best_two_tick[0]:
                                best_two_tick = (
                                    rank_key,
                                    {
                                        "slope": slope,
                                        "intercept": intercept,
                                        "chosen": chosen,
                                        "px_span": px_span,
                                        "med_r": None,
                                        "max_r": None,
                                        "total_votes": total_votes,
                                        "mean_conf": mean_conf,
                                    },
                                )

    winner = None
    reason = "no_consistent_scale"
    if best_loto is not None:
        winner = best_loto[1]
        reason = "loto_m>=3_accepted"
    elif best_two_tick is not None:
        winner = best_two_tick[1]
        reason = "two_tick_multiview_verified"

    if winner is None:
        return AxisFitResult(
            axis=axis,
            accepted=False,
            accept_reason=reason,
            n_band_tokens=len(band),
            n_slots=n_slots,
        )

    slope = winner["slope"]
    intercept = winner["intercept"]
    chosen = winner["chosen"]
    ps = [h.pos for h in chosen]

    # For X: p_lo is left (min x_px -> x_min), p_hi is right (max x_px -> x_max).
    # For Y: y_min is at bottom (MAX y_px), y_max is at top (MIN y_px)!
    if axis == "x":
        p_lo_int = int(round(min(ps)))
        p_hi_int = int(round(max(ps)))
        if p_hi_int <= p_lo_int:
            return AxisFitResult(axis=axis, accepted=False, accept_reason="degenerate_int_anchors", n_band_tokens=len(band), n_slots=n_slots)
        v_lo = slope * p_lo_int + intercept
        v_hi = slope * p_hi_int + intercept
    else:
        # y_min anchor is bottom (larger y_px), y_max anchor is top (smaller y_px)
        p_lo_int = int(round(max(ps)))  # bottom -> y_min
        p_hi_int = int(round(min(ps)))  # top -> y_max
        if p_lo_int <= p_hi_int:
            return AxisFitResult(axis=axis, accepted=False, accept_reason="degenerate_int_anchors", n_band_tokens=len(band), n_slots=n_slots)
        v_lo = slope * p_lo_int + intercept  # y_min
        v_hi = slope * p_hi_int + intercept  # y_max

    if not (math.isfinite(v_lo) and math.isfinite(v_hi) and v_hi > v_lo):
        return AxisFitResult(axis=axis, accepted=False, accept_reason="non_monotonic_anchors", n_band_tokens=len(band), n_slots=n_slots)

    inlier_records = [
        {
            "pos_px": round(h.pos, 2),
            "value": h.value,
            "votes": h.votes,
            "mean_conf": round(h.mean_conf, 2),
            "views": list(h.views),
            "synthetic_negated": h.synthetic_negated,
        }
        for h in sorted(chosen, key=lambda item: item.pos)
    ]

    return AxisFitResult(
        axis=axis,
        accepted=True,
        accept_reason=reason,
        slope=float(slope),
        intercept=float(intercept),
        anchor_px_lo=p_lo_int,
        anchor_px_hi=p_hi_int,
        anchor_val_lo=float(v_lo),
        anchor_val_hi=float(v_hi),
        n_band_tokens=len(band),
        n_slots=n_slots,
        n_inliers=len(chosen),
        total_inlier_votes=int(winner["total_votes"]),
        inlier_mean_conf=round(float(winner["mean_conf"]), 2),
        med_loto_resid=round(float(winner["med_r"]), 6) if winner["med_r"] is not None else None,
        max_loto_resid=round(float(winner["max_r"]), 6) if winner["max_r"] is not None else None,
        inlier_pixel_span=round(float(winner["px_span"]), 2),
        inliers=inlier_records,
    )


def _solve_single_axis(
    pil_rgb: Image.Image,
    gray_orig: np.ndarray,
    roi_box: Tuple[int, int, int, int],
    axis: str,
    views: Sequence[OcrViewSpec],
    expected_plot_span: float,
    ortho_ref: float,
) -> Tuple[AxisFitResult, int, float, float]:
    t_ocr0 = time.perf_counter()
    x0, y0, x1, y1 = roi_box
    crop = pil_rgb.crop((x0, y0, x1, y1))

    all_tokens: List[RawToken] = []
    per_view_counts: Dict[str, int] = {}
    calls = 0
    for view in views:
        toks = _run_ocr_view_on_roi(crop, (x0, y0), view, axis=axis)
        calls += 1
        per_view_counts[view.name] = len(toks)
        all_tokens.extend(toks)
    ocr_s = time.perf_counter() - t_ocr0

    t_fit0 = time.perf_counter()
    aug_tokens = _augment_dropped_minus_hypotheses(all_tokens, gray_orig)
    bands = _cluster_axis_bands(aug_tokens, axis=axis, img_w=pil_rgb.width, img_h=pil_rgb.height)

    best_fit: Optional[Tuple[Tuple[Any, ...], AxisFitResult]] = None
    for band in bands:
        fit = _fit_axis_from_band(
            band=band,
            axis=axis,
            expected_plot_span=expected_plot_span,
            anchor_ortho_ref=ortho_ref,
        )
        # Compute band proximity to the axis spine (smaller distance is better)
        if axis == "x":
            band_ortho = statistics.median([t.cy for t in band])
        else:
            band_ortho = statistics.median([t.right for t in band])
        ortho_dist = abs(band_ortho - ortho_ref)

        rank = (
            1 if fit.accepted else 0,
            1 if fit.accept_reason == "loto_m>=3_accepted" else 0,
            fit.n_inliers,
            -(round(fit.med_loto_resid, 3) if fit.med_loto_resid is not None else 1.0),
            fit.total_inlier_votes,
            -ortho_dist,
        )
        if best_fit is None or rank > best_fit[0]:
            best_fit = (rank, fit)

    if best_fit is None:
        result = AxisFitResult(
            axis=axis,
            accepted=False,
            accept_reason="no_ocr_tokens",
            n_raw_tokens=len(all_tokens),
            per_view_token_counts=per_view_counts,
        )
    else:
        result = best_fit[1]
        result.n_raw_tokens = len(all_tokens)
        result.per_view_token_counts = per_view_counts

    fit_s = time.perf_counter() - t_fit0
    return result, calls, ocr_s, fit_s


def calibrate_axes_matched(
    image_path: str | Path,
    arm: str,
) -> CalibrationProposal:
    """Run matched-budget axis calibration for Arm B ('B_single_res') or Arm C ('C_two_res')."""
    if arm == "B_single_res":
        views = ARM_B_VIEWS
    elif arm == "C_two_res":
        views = ARM_C_VIEWS
    else:
        raise ValueError(f"Unsupported arm: {arm}")

    t_total0 = time.perf_counter()
    t_roi0 = time.perf_counter()
    with Image.open(image_path) as im:
        pil_rgb = im.convert("RGB")
    gray_orig = np.asarray(pil_rgb.convert("L"), dtype=np.uint8)
    roi_geom = detect_axis_rois(pil_rgb)
    roi_s = time.perf_counter() - t_roi0

    expected_x_span = float(max(20, roi_geom.plot_right - roi_geom.plot_left))
    expected_y_span = float(max(20, roi_geom.plot_bottom - roi_geom.plot_top))

    x_fit, x_calls, x_ocr_s, x_fit_s = _solve_single_axis(
        pil_rgb=pil_rgb,
        gray_orig=gray_orig,
        roi_box=roi_geom.x_roi,
        axis="x",
        views=views,
        expected_plot_span=expected_x_span,
        ortho_ref=float(roi_geom.plot_bottom),
    )
    y_fit, y_calls, y_ocr_s, y_fit_s = _solve_single_axis(
        pil_rgb=pil_rgb,
        gray_orig=gray_orig,
        roi_box=roi_geom.y_roi,
        axis="y",
        views=views,
        expected_plot_span=expected_y_span,
        ortho_ref=float(roi_geom.plot_left),
    )

    total_calls = x_calls + y_calls
    both_ok = bool(x_fit.accepted and y_fit.accepted)

    tick_points: Optional[List[Tuple[int, int]]] = None
    axis_values: Optional[List[float]] = None
    if both_ok:
        # Strictly horizontal X-anchor pair at y = plot_bottom,
        # strictly vertical Y-anchor pair at x = plot_left.
        y_anchor = int(max(0, min(roi_geom.height - 1, roi_geom.plot_bottom)))
        x_anchor = int(max(0, min(roi_geom.width - 1, roi_geom.plot_left)))
        tick_points = [
            (int(x_fit.anchor_px_lo), y_anchor),  # x_min_pt
            (int(x_fit.anchor_px_hi), y_anchor),  # x_max_pt
            (x_anchor, int(y_fit.anchor_px_lo)),  # y_min_pt (bottom, larger y_px)
            (x_anchor, int(y_fit.anchor_px_hi)),  # y_max_pt (top, smaller y_px)
        ]
        axis_values = [
            float(x_fit.anchor_val_lo),
            float(x_fit.anchor_val_hi),
            float(y_fit.anchor_val_lo),
            float(y_fit.anchor_val_hi),
        ]

    total_s = time.perf_counter() - t_total0
    return CalibrationProposal(
        arm=arm,
        accepted=both_ok,
        use_fallback_arm_a=not both_ok,
        tick_points=tick_points,
        axis_values=axis_values,
        ocr_call_count=total_calls,
        roi_geometry=asdict(roi_geom),
        x_fit=asdict(x_fit),
        y_fit=asdict(y_fit),
        timing_s={
            "roi_s": round(roi_s, 4),
            "ocr_s": round(x_ocr_s + y_ocr_s, 4),
            "fit_s": round(x_fit_s + y_fit_s, 4),
            "calibration_total_s": round(total_s, 4),
        },
    )
