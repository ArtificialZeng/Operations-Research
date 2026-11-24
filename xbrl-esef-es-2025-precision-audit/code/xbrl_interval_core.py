"""
Core exact-arithmetic iXBRL ingestion and XBRL Calculations 1.1 fact-interval engine.

Implements:
  1. Strict Inline XBRL 1.1 (`ix:nonFraction`) extraction preserving full provenance:
     (name, namespace, contextRef, period_start, period_end, dimensions, unitRef, currency,
      raw_text, format/transform, scale, sign, decimals, exact Fraction value).
     - Excludes `<ix:exclude>` descendants.
     - Zero sign inference from display scaling or parentheses.
     - Explicit failure on unsupported transforms, missing decimals, or duplicate conflicts.
  2. Official XBRL Calculations 1.1 fact intervals in exact `fractions.Fraction`:
     - `round_to_nearest`: [v - q/2, v + q/2] with strict interior witness check |x - v| < q/2
       (valid under ALL round-to-nearest tie-breaking conventions).
     - `truncation`: truncation towards zero: [v, v+q) if v>0, (v-q, v] if v<0, (-q, q) if v==0,
       with exact forward-truncation witness verification `Fraction(int(x / q)) * q == v`.
     - Conservative convention-uncertainty summary kept strictly separate from same-rule verdicts.
  3. Exact rational threshold evaluators with explicit witness construction & verification:
     - Primary: 1.00% YoY Revenue Growth (`100*A - 101*B > 0`, positive prior denominator B > 0).
     - Secondary: 0.00% YoY Revenue Growth (`A - B > 0`, positive prior denominator B > 0).
     - Optional secondary accounting comparison: Change in Gross Margin (`G_t/R_t > G_{t-1}/R_{t-1}`,
       i.e. `G_t * R_{t-1} - G_{t-1} * R_t > 0`, R_t > 0, R_{t-1} > 0).
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from typing import Any, Dict, List, Optional, Tuple

from lxml import etree

IFRS_FULL_NS_SUBSTR = "xbrl.ifrs.org/taxonomy/"
IFRS_FULL_SUFFIX = "/ifrs-full"


class IXBRLParseError(ValueError):
    """Explicit parse/transform failure (never silently ignored)."""


def _local_name(qname_or_tag: str) -> str:
    if "}" in qname_or_tag:
        return qname_or_tag.rsplit("}", 1)[1]
    if ":" in qname_or_tag:
        return qname_or_tag.split(":", 1)[1]
    return qname_or_tag


def _resolve_qname(qname: str, nsmap: Dict[Optional[str], str]) -> Tuple[Optional[str], str]:
    if ":" in qname:
        pfx, loc = qname.split(":", 1)
        return nsmap.get(pfx), loc
    return nsmap.get(None), qname


def extract_ix_text_excluding_ix_exclude(el: etree._Element) -> str:
    """Extracts text inside `<ix:nonFraction>` skipping any `<ix:exclude>` subtrees."""
    parts: List[str] = []
    if el.text:
        parts.append(el.text)
    for child in el:
        loc = _local_name(child.tag) if isinstance(child.tag, str) else ""
        if loc != "exclude":
            parts.append(extract_ix_text_excluding_ix_exclude(child))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


_XSD_DECIMAL_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")
_WS_AND_THOUSANDS_RE = re.compile(r"[\s\u00a0\u202f\u2009'_]")


def transform_ix_numeric_text(raw_text: str, fmt_attr: Optional[str]) -> Decimal:
    """
    Exact Inline XBRL Transformation Registry (`ixt`) numeric parser.
    NEVER infers sign from display parentheses or scaling.
    Raises `IXBRLParseError` on any unrecognized format or malformed string.
    """
    s = raw_text.strip()
    if fmt_attr is None or fmt_attr.strip() == "":
        # Raw XSD decimal (whitespace stripped)
        s_clean = re.sub(r"\s+", "", s)
        if not _XSD_DECIMAL_RE.match(s_clean):
            raise IXBRLParseError(f"Malformed unformatted XSD decimal: {raw_text!r}")
        try:
            return Decimal(s_clean)
        except InvalidOperation as ex:
            raise IXBRLParseError(f"Decimal parse failed on {raw_text!r}: {ex}") from ex

    fmt_local = _local_name(fmt_attr.strip()).lower()

    if fmt_local in ("fixed-zero", "zerodash", "numdash"):
        return Decimal("0")

    if fmt_local in ("num-comma-decimal", "numcommadecimal", "numspacecomma", "numcommadot"):
        # Standard iXBRL comma-decimal formats represent non-negative magnitudes (sign via sign="-")
        if "-" in s or "(" in s or ")" in s:
            raise IXBRLParseError(f"Unexpected sign/parenthesis in {fmt_attr}: {raw_text!r}")
        s_clean = _WS_AND_THOUSANDS_RE.sub("", s).replace(".", "")
        if s_clean.count(",") > 1:
            raise IXBRLParseError(f"Multiple decimal commas in {fmt_attr}: {raw_text!r}")
        s_dec = s_clean.replace(",", ".")
        if not re.match(r"^(?:\d+(?:\.\d*)?|\.\d+)$", s_dec):
            raise IXBRLParseError(f"Malformed comma-decimal text in {fmt_attr}: {raw_text!r}")
        return Decimal(s_dec)

    if fmt_local in ("num-dot-decimal", "numdotdecimal", "numspacedot", "numdotcomma"):
        if "-" in s or "(" in s or ")" in s:
            raise IXBRLParseError(f"Unexpected sign/parenthesis in {fmt_attr}: {raw_text!r}")
        s_clean = _WS_AND_THOUSANDS_RE.sub("", s).replace(",", "")
        if s_clean.count(".") > 1:
            raise IXBRLParseError(f"Multiple decimal dots in {fmt_attr}: {raw_text!r}")
        if not re.match(r"^(?:\d+(?:\.\d*)?|\.\d+)$", s_clean):
            raise IXBRLParseError(f"Malformed dot-decimal text in {fmt_attr}: {raw_text!r}")
        return Decimal(s_clean)

    raise IXBRLParseError(f"Unsupported iXBRL transform format: {fmt_attr!r} on {raw_text!r}")


def parse_decimals_attr(dec_attr: Optional[str]) -> Any:
    """Returns 'INF' or int(d); raises IXBRLParseError if missing/invalid."""
    if dec_attr is None:
        raise IXBRLParseError("Missing decimals attribute on ix:nonFraction")
    d = dec_attr.strip()
    if d.upper() == "INF":
        return "INF"
    if not re.match(r"^[+-]?\d+$", d):
        raise IXBRLParseError(f"Invalid decimals attribute: {dec_attr!r}")
    return int(d)


def parse_ixbrl_numeric_facts(xhtml_path: str) -> Dict[str, Any]:
    """
    Parses an Inline XBRL XHTML document natively with `lxml` (`recover=False` first;
    fails explicitly if XML is invalid) and extracts contexts, units, and all `ix:nonFraction`
    facts with full provenance.
    """
    parser = etree.XMLParser(recover=False, huge_tree=True)
    tree = etree.parse(str(xhtml_path), parser)
    root = tree.getroot()

    # 1. Contexts
    contexts: Dict[str, Dict[str, Any]] = {}
    for ctx in root.xpath(".//*[local-name()='context']"):
        cid = ctx.get("id")
        if not cid:
            continue
        ent_id_el = ctx.xpath("./*[local-name()='entity']/*[local-name()='identifier']")
        ent_id = ent_id_el[0].text.strip() if ent_id_el and ent_id_el[0].text else None
        ent_scheme = ent_id_el[0].get("scheme") if ent_id_el else None

        start_el = ctx.xpath("./*[local-name()='period']/*[local-name()='startDate']")
        end_el = ctx.xpath("./*[local-name()='period']/*[local-name()='endDate']")
        inst_el = ctx.xpath("./*[local-name()='period']/*[local-name()='instant']")

        p_start = start_el[0].text.strip() if start_el and start_el[0].text else None
        p_end = end_el[0].text.strip() if end_el and end_el[0].text else None
        p_inst = inst_el[0].text.strip() if inst_el and inst_el[0].text else None

        dur_days: Optional[int] = None
        if p_start and p_end:
            try:
                d0 = dt.date.fromisoformat(p_start[:10])
                d1 = dt.date.fromisoformat(p_end[:10])
                dur_days = (d1 - d0).days + 1  # inclusive calendar days (365 or 366 for full FY)
            except ValueError:
                dur_days = None

        dims: List[Dict[str, str]] = []
        for m in ctx.xpath(".//*[local-name()='explicitMember']"):
            dims.append({
                "kind": "explicit",
                "dimension": m.get("dimension") or "",
                "member": (m.text or "").strip(),
            })
        for m in ctx.xpath(".//*[local-name()='typedMember']"):
            dims.append({
                "kind": "typed",
                "dimension": m.get("dimension") or "",
                "member": "".join(m.itertext()).strip(),
            })

        contexts[cid] = {
            "id": cid,
            "entity_identifier": ent_id,
            "entity_scheme": ent_scheme,
            "period_start": p_start,
            "period_end": p_end,
            "period_instant": p_inst,
            "duration_days": dur_days,
            "dimensions": dims,
        }

    # 2. Units
    units: Dict[str, Dict[str, Any]] = {}
    for u in root.xpath(".//*[local-name()='unit']"):
        uid = u.get("id")
        if not uid:
            continue
        direct_measures = [m.text.strip() for m in u.xpath("./*[local-name()='measure']") if m.text]
        has_divide = len(u.xpath("./*[local-name()='divide']")) > 0
        currency = None
        if not has_divide and len(direct_measures) == 1:
            m_txt = direct_measures[0]
            if ":" in m_txt:
                pfx, loc = m_txt.split(":", 1)
                ns = u.nsmap.get(pfx, "")
                if "iso4217" in ns.lower() or pfx.lower() == "iso4217":
                    currency = loc
            elif len(m_txt) == 3 and m_txt.isupper():
                currency = m_txt
        units[uid] = {
            "id": uid,
            "measures": direct_measures,
            "has_divide": has_divide,
            "currency": currency,
        }

    # 3. ix:nonFraction facts
    facts: List[Dict[str, Any]] = []
    parse_errors: List[Dict[str, Any]] = []
    has_cons_sep_axis = any(
        "ConsolidatedAndSeparateFinancialStatementsAxis" in d["dimension"]
        for c in contexts.values()
        for d in c["dimensions"]
    )

    for idx_el, el in enumerate(root.xpath(".//*[local-name()='nonFraction']")):
        name_raw = el.get("name") or ""
        ns_uri, local = _resolve_qname(name_raw, el.nsmap)
        cid = el.get("contextRef")
        uid = el.get("unitRef")
        fmt = el.get("format")
        scale_attr = el.get("scale")
        sign_attr = el.get("sign")
        dec_attr = el.get("decimals")
        raw_text = extract_ix_text_excluding_ix_exclude(el)

        is_ifrs_full = bool(
            (ns_uri and IFRS_FULL_NS_SUBSTR in ns_uri and ns_uri.rstrip("/").endswith(IFRS_FULL_SUFFIX))
            or name_raw.startswith("ifrs-full:")
        )
        # Only strictly parse ifrs-full Revenue / GrossProfit or record errors on target tags
        if not (is_ifrs_full and local in ("Revenue", "GrossProfit")):
            continue

        ctx = contexts.get(cid or "")
        unit = units.get(uid or "")
        prov = {
            "fact_index_in_doc": idx_el,
            "name_raw": name_raw,
            "namespace": ns_uri,
            "local_name": local,
            "contextRef": cid,
            "period_start": ctx["period_start"] if ctx else None,
            "period_end": ctx["period_end"] if ctx else None,
            "period_instant": ctx["period_instant"] if ctx else None,
            "duration_days": ctx["duration_days"] if ctx else None,
            "dimensions": ctx["dimensions"] if ctx else None,
            "entity_identifier": ctx["entity_identifier"] if ctx else None,
            "unitRef": uid,
            "currency": unit["currency"] if unit else None,
            "unit_measures": unit["measures"] if unit else None,
            "raw_text": raw_text,
            "format": fmt,
            "scale": scale_attr,
            "sign": sign_attr,
            "decimals_raw": dec_attr,
        }

        try:
            if ctx is None:
                raise IXBRLParseError(f"Unknown contextRef: {cid!r}")
            if unit is None:
                raise IXBRLParseError(f"Unknown unitRef: {uid!r}")
            mag = transform_ix_numeric_text(raw_text, fmt)
            if sign_attr is None:
                signed_dec = mag
            elif sign_attr.strip() == "-":
                if mag < 0:
                    raise IXBRLParseError(f"Double negative: sign='-' with negative text {raw_text!r}")
                signed_dec = -mag
            else:
                raise IXBRLParseError(f"Unsupported sign attribute: {sign_attr!r}")

            scale_int = 0 if (scale_attr is None or scale_attr.strip() == "") else int(scale_attr.strip())
            decimals_val = parse_decimals_attr(dec_attr)
            exact_val = Fraction(signed_dec) * (Fraction(10) ** scale_int)

            prov["scale_int"] = scale_int
            prov["decimals"] = decimals_val
            prov["exact_value"] = exact_val
            prov["exact_value_str"] = str(Decimal(exact_val.numerator) / Decimal(exact_val.denominator)) if exact_val.denominator in (1, 10, 100, 1000, 10000) else f"{exact_val.numerator}/{exact_val.denominator}"
            facts.append(prov)
        except Exception as ex:
            prov["parse_error"] = str(ex)
            parse_errors.append(prov)

    return {
        "n_contexts": len(contexts),
        "n_units": len(units),
        "has_consolidated_separate_axis": has_cons_sep_axis,
        "target_facts": facts,
        "target_parse_errors": parse_errors,
    }


# ==============================================================================
# Official XBRL Calculations 1.1 Fact Intervals & Exact Witness Verification
# ==============================================================================

def fact_quantum(decimals: Any) -> Fraction:
    """Returns 0 for 'INF', else exact Fraction(10) ** (-decimals)."""
    if decimals == "INF":
        return Fraction(0, 1)
    assert isinstance(decimals, int)
    return Fraction(10, 1) ** (-decimals)


def fact_interval(v: Fraction, decimals: Any, rule: str) -> Tuple[Fraction, Fraction]:
    """
    Official XBRL Calculations 1.1 fact value interval bounds (lo, hi):
      - round_to_nearest: [v - q/2, v + q/2]
      - truncation (towards zero):
          v > 0 -> [v, v + q)
          v < 0 -> (v - q, v]
          v == 0 -> (-q, +q)
      - decimals == 'INF' -> [v, v]
    """
    if decimals == "INF":
        return (v, v)
    q = fact_quantum(decimals)
    if rule == "round_to_nearest":
        half = q / 2
        return (v - half, v + half)
    if rule == "truncation":
        if v > 0:
            return (v, v + q)
        if v < 0:
            return (v - q, v)
        return (-q, q)
    raise ValueError(f"Unknown rounding rule: {rule!r}")


def verify_witness_valid_for_fact(x: Fraction, v: Fraction, decimals: Any, rule: str) -> bool:
    """
    Exact forward witness verification:
      - If decimals == 'INF': x == v.
      - If rule == 'round_to_nearest': STRICT interior `abs(x - v) < q / 2`, which guarantees
        that `x` rounds unambiguously to `v` under EVERY round-to-nearest tie-breaking rule
        (half-up, half-down, half-to-even, half-away-from-zero).
      - If rule == 'truncation': exact truncation towards zero `Fraction(int(x / q)) * q == v`
        (and strictly inside the open interior of the truncation interval if non-point).
    """
    if decimals == "INF":
        return x == v
    q = fact_quantum(decimals)
    if rule == "round_to_nearest":
        return abs(x - v) < (q / 2)
    if rule == "truncation":
        # Python int(Fraction) truncates strictly towards zero for both positive and negative values
        truncated = Fraction(int(x / q), 1) * q
        return truncated == v
    raise ValueError(f"Unknown rounding rule: {rule!r}")


def _interval_center(v: Fraction, decimals: Any, rule: str) -> Fraction:
    lo, hi = fact_interval(v, decimals, rule)
    return (lo + hi) / 2


def _fmt_frac_decimal(f: Fraction, digits: int = 8) -> str:
    sign = "-" if f < 0 else ""
    af = abs(f)
    scale = 10 ** digits
    scaled = (af.numerator * scale) // af.denominator
    int_part, frac_part = divmod(scaled, scale)
    return f"{sign}{int_part}.{frac_part:0{digits}d}"


def evaluate_yoy_threshold(
    v_a: Fraction,
    d_a: Any,
    v_b: Fraction,
    d_b: Any,
    threshold_num: int,
    threshold_den: int,
    rule: str,
) -> Dict[str, Any]:
    """
    Evaluates exact YoY growth `(A - B) / B > threshold_num / threshold_den`
    <=> `threshold_den * A - (threshold_den + threshold_num) * B > 0`
    for positive prior denominator B > 0 under ONE fixed XBRL Calculations 1.1 rule.

    For 1.00% growth: threshold_num=1, threshold_den=100 => L(A, B) = 100*A - 101*B.
    For 0.00% growth: threshold_num=0, threshold_den=1   => L(A, B) = A - B.
    """
    a_lo, a_hi = fact_interval(v_a, d_a, rule)
    b_lo, b_hi = fact_interval(v_b, d_b, rule)

    if v_b <= 0 or b_lo <= 0:
        return {
            "rule": rule,
            "eligible": False,
            "exclusion_reason": "non_positive_prior_denominator_or_interval_crosses_zero",
        }

    p = threshold_num
    q = threshold_den
    c_a = q
    c_b = q + p

    def L(a: Fraction, b: Fraction) -> Fraction:
        return c_a * a - c_b * b

    l_disp = L(v_a, v_b)
    l_inf = L(a_lo, b_hi)
    l_sup = L(a_hi, b_lo)

    disp_growth = (v_a - v_b) / v_b
    min_growth = (a_lo - b_hi) / b_hi
    max_growth = (a_hi - b_lo) / b_lo

    witnesses: Optional[Dict[str, Any]] = None
    if l_disp == 0:
        status = "exact_displayed_tie"
    elif l_inf < 0 < l_sup:
        status = "strict_non_tie_flip"
        # Closed-form exact rational strict interior witnesses on BOTH sides of 0
        ac = _interval_center(v_a, d_a, rule)
        bc = _interval_center(v_b, d_b, rule)
        l_c = L(ac, bc)

        # Below witness toward (a_lo, b_hi) where L = l_inf < 0
        if l_c < 0:
            t_below = Fraction(1, 2)
        else:
            t_star = l_c / (l_c - l_inf)  # in [0, 1)
            t_below = (Fraction(1, 1) + t_star) / 2
        a_bel = (1 - t_below) * ac + t_below * a_lo
        b_bel = (1 - t_below) * bc + t_below * b_hi

        # Above witness toward (a_hi, b_lo) where L = l_sup > 0
        if l_c > 0:
            t_above = Fraction(1, 2)
        else:
            t_star = (-l_c) / (l_sup - l_c)  # in [0, 1)
            t_above = (Fraction(1, 1) + t_star) / 2
        a_abv = (1 - t_above) * ac + t_above * a_hi
        b_abv = (1 - t_above) * bc + t_above * b_lo

        # HARD PROGRAMMATIC WITNESS ASSERTIONS
        assert b_bel > 0 and b_abv > 0
        assert verify_witness_valid_for_fact(a_bel, v_a, d_a, rule)
        assert verify_witness_valid_for_fact(b_bel, v_b, d_b, rule)
        assert verify_witness_valid_for_fact(a_abv, v_a, d_a, rule)
        assert verify_witness_valid_for_fact(b_abv, v_b, d_b, rule)
        assert L(a_bel, b_bel) < 0, "Below witness failed strict inequality!"
        assert L(a_abv, b_abv) > 0, "Above witness failed strict inequality!"

        g_bel = (a_bel - b_bel) / b_bel
        g_abv = (a_abv - b_abv) / b_abv
        witnesses = {
            "witness_below_threshold": {
                "A_exact": f"{a_bel.numerator}/{a_bel.denominator}",
                "B_exact": f"{b_bel.numerator}/{b_bel.denominator}",
                "A_dec": _fmt_frac_decimal(a_bel, 4),
                "B_dec": _fmt_frac_decimal(b_bel, 4),
                "L_exact": f"{L(a_bel, b_bel).numerator}/{L(a_bel, b_bel).denominator}",
                "growth_pct_approx": _fmt_frac_decimal(g_bel * 100, 6),
                "verified_rounds_or_truncates_to_reported": True,
                "verified_strictly_below": True,
            },
            "witness_above_threshold": {
                "A_exact": f"{a_abv.numerator}/{a_abv.denominator}",
                "B_exact": f"{b_abv.numerator}/{b_abv.denominator}",
                "A_dec": _fmt_frac_decimal(a_abv, 4),
                "B_dec": _fmt_frac_decimal(b_abv, 4),
                "L_exact": f"{L(a_abv, b_abv).numerator}/{L(a_abv, b_abv).denominator}",
                "growth_pct_approx": _fmt_frac_decimal(g_abv * 100, 6),
                "verified_rounds_or_truncates_to_reported": True,
                "verified_strictly_above": True,
            },
        }
    elif l_inf == 0 or l_sup == 0:
        status = "endpoint_touch_only"
    elif l_inf > 0:
        status = "uniquely_identified_above"
    else:
        assert l_sup < 0
        status = "uniquely_identified_below"

    return {
        "rule": rule,
        "eligible": True,
        "status": status,
        "displayed_side": "tie" if l_disp == 0 else ("above" if l_disp > 0 else "below"),
        "L_displayed": f"{l_disp.numerator}/{l_disp.denominator}",
        "L_inf": f"{l_inf.numerator}/{l_inf.denominator}",
        "L_sup": f"{l_sup.numerator}/{l_sup.denominator}",
        "displayed_growth_pct": _fmt_frac_decimal(disp_growth * 100, 6),
        "min_growth_pct": _fmt_frac_decimal(min_growth * 100, 6),
        "max_growth_pct": _fmt_frac_decimal(max_growth * 100, 6),
        "witnesses": witnesses,
    }


def evaluate_gross_margin_change(
    g_t: Fraction, dg_t: Any,
    r_t: Fraction, dr_t: Any,
    g_p: Fraction, dg_p: Any,
    r_p: Fraction, dr_p: Any,
    rule: str,
) -> Dict[str, Any]:
    """
    Exact test for Change in Gross Margin: `G_t / R_t - G_{t-1} / R_{t-1} > 0`
    <=> `G_t * R_{t-1} - G_{t-1} * R_t > 0` (requiring R_t > 0 and R_{t-1} > 0 across intervals).
    """
    gt_lo, gt_hi = fact_interval(g_t, dg_t, rule)
    rt_lo, rt_hi = fact_interval(r_t, dr_t, rule)
    gp_lo, gp_hi = fact_interval(g_p, dg_p, rule)
    rp_lo, rp_hi = fact_interval(r_p, dr_p, rule)

    if r_t <= 0 or r_p <= 0 or rt_lo <= 0 or rp_lo <= 0:
        return {
            "rule": rule,
            "eligible": False,
            "exclusion_reason": "non_positive_revenue_denominator_in_gross_margin",
        }

    # Exact min/max of G/R over [g_lo, g_hi] x [r_lo, r_hi] (monotone in G and 1/R => attained at 4 corners)
    corners_t = [((g, r), g / r) for g in (gt_lo, gt_hi) for r in (rt_lo, rt_hi)]
    corners_p = [((g, r), g / r) for g in (gp_lo, gp_hi) for r in (rp_lo, rp_hi)]

    min_t_pt, min_t_val = min(corners_t, key=lambda kv: kv[1])
    max_t_pt, max_t_val = max(corners_t, key=lambda kv: kv[1])
    min_p_pt, min_p_val = min(corners_p, key=lambda kv: kv[1])
    max_p_pt, max_p_val = max(corners_p, key=lambda kv: kv[1])

    disp_diff = (g_t / r_t) - (g_p / r_p)
    inf_diff = min_t_val - max_p_val
    sup_diff = max_t_val - min_p_val

    def F(a_gt, a_rt, a_gp, a_rp) -> Fraction:
        return a_gt * a_rp - a_gp * a_rt

    witnesses = None
    if disp_diff == 0:
        status = "exact_displayed_tie"
    elif inf_diff < 0 < sup_diff:
        status = "strict_non_tie_flip"
        # Exact interior rational witness construction via dyadic approach to minimizing/maximizing corner
        c_gt = _interval_center(g_t, dg_t, rule)
        c_rt = _interval_center(r_t, dr_t, rule)
        c_gp = _interval_center(g_p, dg_p, rule)
        c_rp = _interval_center(r_p, dr_p, rule)

        def find_interior_witness(target_corner, want_negative: bool):
            t_gt, t_rt, t_gp, t_rp = target_corner
            eps = Fraction(1, 2)
            for _ in range(200):
                w_gt = eps * c_gt + (1 - eps) * t_gt
                w_rt = eps * c_rt + (1 - eps) * t_rt
                w_gp = eps * c_gp + (1 - eps) * t_gp
                w_rp = eps * c_rp + (1 - eps) * t_rp
                val = F(w_gt, w_rt, w_gp, w_rp)
                if (want_negative and val < 0) or (not want_negative and val > 0):
                    assert w_rt > 0 and w_rp > 0
                    assert verify_witness_valid_for_fact(w_gt, g_t, dg_t, rule)
                    assert verify_witness_valid_for_fact(w_rt, r_t, dr_t, rule)
                    assert verify_witness_valid_for_fact(w_gp, g_p, dg_p, rule)
                    assert verify_witness_valid_for_fact(w_rp, r_p, dr_p, rule)
                    return w_gt, w_rt, w_gp, w_rp
                eps /= 2
            raise RuntimeError("Failed to construct strict interior GM witness")

        bel = find_interior_witness((min_t_pt[0], min_t_pt[1], max_p_pt[0], max_p_pt[1]), want_negative=True)
        abv = find_interior_witness((max_t_pt[0], max_t_pt[1], min_p_pt[0], min_p_pt[1]), want_negative=False)
        witnesses = {
            "witness_below_zero": {
                "Gt_dec": _fmt_frac_decimal(bel[0], 4),
                "Rt_dec": _fmt_frac_decimal(bel[1], 4),
                "Gp_dec": _fmt_frac_decimal(bel[2], 4),
                "Rp_dec": _fmt_frac_decimal(bel[3], 4),
                "delta_gm_pp": _fmt_frac_decimal(((bel[0] / bel[1]) - (bel[2] / bel[3])) * 100, 6),
                "verified_strictly_below": True,
            },
            "witness_above_zero": {
                "Gt_dec": _fmt_frac_decimal(abv[0], 4),
                "Rt_dec": _fmt_frac_decimal(abv[1], 4),
                "Gp_dec": _fmt_frac_decimal(abv[2], 4),
                "Rp_dec": _fmt_frac_decimal(abv[3], 4),
                "delta_gm_pp": _fmt_frac_decimal(((abv[0] / abv[1]) - (abv[2] / abv[3])) * 100, 6),
                "verified_strictly_above": True,
            },
        }
    elif inf_diff == 0 or sup_diff == 0:
        status = "endpoint_touch_only"
    elif inf_diff > 0:
        status = "uniquely_identified_above"
    else:
        assert sup_diff < 0
        status = "uniquely_identified_below"

    return {
        "rule": rule,
        "eligible": True,
        "status": status,
        "displayed_side": "tie" if disp_diff == 0 else ("above" if disp_diff > 0 else "below"),
        "displayed_gm_t_pct": _fmt_frac_decimal((g_t / r_t) * 100, 6),
        "displayed_gm_prev_pct": _fmt_frac_decimal((g_p / r_p) * 100, 6),
        "displayed_delta_gm_pp": _fmt_frac_decimal(disp_diff * 100, 6),
        "min_delta_gm_pp": _fmt_frac_decimal(inf_diff * 100, 6),
        "max_delta_gm_pp": _fmt_frac_decimal(sup_diff * 100, 6),
        "witnesses": witnesses,
    }


def conservative_convention_label(res_nearest: Dict[str, Any], res_trunc: Dict[str, Any]) -> str:
    """
    Conservative summary when rounding convention (round-to-nearest vs truncation) is unstated.
    STRICTLY distinguishes same-rule strict non-tie flips from cross-rule convention disagreement.
    """
    if not res_nearest.get("eligible") or not res_trunc.get("eligible"):
        return "ineligible"
    sn = res_nearest["status"]
    st = res_trunc["status"]
    if sn == "exact_displayed_tie" or st == "exact_displayed_tie":
        return "exact_displayed_tie"
    if sn == "strict_non_tie_flip" and st == "strict_non_tie_flip":
        return "strict_non_tie_flip_under_both_rules"
    if sn == "strict_non_tie_flip":
        return "strict_non_tie_flip_round_to_nearest_only"
    if st == "strict_non_tie_flip":
        return "strict_non_tie_flip_truncation_only"
    if sn == st == "uniquely_identified_above":
        return "conservative_uniquely_identified_above"
    if sn == st == "uniquely_identified_below":
        return "conservative_uniquely_identified_below"
    if {sn, st} == {"uniquely_identified_above", "uniquely_identified_below"}:
        return "ambiguous_convention_disagreement_only_no_same_rule_flip"
    return f"boundary_or_mixed({sn}|{st})"


# ==============================================================================
# Consolidated Consecutive-FY Selection & Duplicate Conflict Check
# ==============================================================================

def resolve_duplicates_for_slot(facts_in_slot: List[Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    Zero-silent-conflict duplicate resolution for facts sharing (concept, period_start, period_end, currency, dims=[]).
      - All exact same (exact_value, decimals) -> identical duplicates, deduplicated cleanly.
      - Multiple distinct decimals (e.g. -3 in primary statement vs -6 in note):
        Checks interval overlap under BOTH round_to_nearest and truncation; if any pair has EMPTY
        intersection under EITHER rule, OR if two facts share the SAME decimals with DIFFERENT values,
        returns (None, conflict_report) -> EXPLICIT EXCLUSION!
        Otherwise selects the strictly finest-precision fact (largest integer decimals, or 'INF')
        and retains ALL duplicates in provenance.
    """
    assert len(facts_in_slot) >= 1
    if len(facts_in_slot) == 1:
        return facts_in_slot[0], {"status": "unique", "n_occurrences": 1, "all_occurrences": facts_in_slot}

    # Check if all identical (exact_value, decimals)
    uniq_vd = {(f["exact_value"], f["decimals"]) for f in facts_in_slot}
    if len(uniq_vd) == 1:
        return facts_in_slot[0], {"status": "identical_duplicates", "n_occurrences": len(facts_in_slot), "all_occurrences": facts_in_slot}

    # Check same decimals with conflicting values -> HARD CONFLICT
    by_dec: Dict[Any, set] = {}
    for f in facts_in_slot:
        by_dec.setdefault(f["decimals"], set()).add(f["exact_value"])
    for d, vals in by_dec.items():
        if len(vals) > 1:
            return None, {
                "status": "duplicate_conflict_same_decimals_different_values",
                "n_occurrences": len(facts_in_slot),
                "conflicting_decimals": d,
                "all_occurrences": facts_in_slot,
            }

    # Distinct decimals: verify pairwise interval overlap under BOTH round_to_nearest and truncation
    for rule in ("round_to_nearest", "truncation"):
        ivs = [fact_interval(f["exact_value"], f["decimals"], rule) for f in facts_in_slot]
        max_lo = max(lo for lo, _ in ivs)
        min_hi = min(hi for _, hi in ivs)
        if max_lo > min_hi:
            return None, {
                "status": f"duplicate_conflict_disjoint_intervals_under_{rule}",
                "n_occurrences": len(facts_in_slot),
                "all_occurrences": facts_in_slot,
            }

    # Pick strictly finest precision ('INF' beats any int; larger int beats smaller int)
    def prec_key(f: Dict[str, Any]) -> Tuple[int, int]:
        if f["decimals"] == "INF":
            return (1, 0)
        return (0, int(f["decimals"]))

    best = max(facts_in_slot, key=prec_key)
    return best, {
        "status": "compatible_mixed_precision_selected_finest",
        "n_occurrences": len(facts_in_slot),
        "selected_decimals": best["decimals"],
        "all_decimals_present": sorted(str(f["decimals"]) for f in facts_in_slot),
        "all_occurrences": facts_in_slot,
    }


def extract_consecutive_fy_pair(
    facts: List[Dict[str, Any]],
    target_local_name: str,
    expected_fy_end_year: Optional[int] = None,
    min_fy_days: int = 350,
    max_fy_days: int = 380,
) -> Dict[str, Any]:
    """
    Finds comparable consolidated (dimensions == []) facts of `target_local_name` for two consecutive
    full financial years (same concept, same currency, FY_t ending in `expected_fy_end_year` if specified,
    duration in [min_fy_days, max_fy_days], and prior FY_{t-1} ending exactly 1 day before FY_t start).
    NEVER silently resolves conflicts or ambiguous multi-currency/multi-period pairs.
    """
    # Filter strictly to undimensioned (consolidated default) full-FY duration monetary facts
    elig = []
    for f in facts:
        if f["local_name"] != target_local_name:
            continue
        if f["dimensions"]:
            continue
        if not f["currency"]:
            continue
        if f["period_start"] is None or f["period_end"] is None or f["duration_days"] is None:
            continue
        if not (min_fy_days <= f["duration_days"] <= max_fy_days):
            continue
        elig.append(f)

    if not elig:
        return {"ok": False, "exclusion_reason": f"no_undimensioned_full_fy_{target_local_name}_facts"}

    # Group by (currency, period_start, period_end)
    slots: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}
    for f in elig:
        key = (f["currency"], f["period_start"][:10], f["period_end"][:10])
        slots.setdefault(key, []).append(f)

    # Resolve duplicates per slot (zero silent conflict!)
    resolved: Dict[Tuple[str, str, str], Tuple[Dict[str, Any], Dict[str, Any]]] = {}
    conflicts = []
    for key, flist in slots.items():
        best, meta = resolve_duplicates_for_slot(flist)
        if best is None:
            conflicts.append({"slot": key, "conflict": meta})
        else:
            resolved[key] = (best, meta)

    if conflicts:
        return {
            "ok": False,
            "exclusion_reason": f"duplicate_conflict_in_{target_local_name}",
            "conflicts": conflicts,
        }

    # Find consecutive full-FY pairs with same currency:
    # prior.end + 1 day == current.start, and (if expected_fy_end_year) current.end[:4] == expected_fy_end_year
    pairs = []
    for (cur_c, cur_s, cur_e), (cur_f, cur_meta) in resolved.items():
        d_cur_s = dt.date.fromisoformat(cur_s)
        d_cur_e = dt.date.fromisoformat(cur_e)
        if expected_fy_end_year is not None and d_cur_e.year != expected_fy_end_year:
            continue
        expected_prev_end = (d_cur_s - dt.timedelta(days=1)).isoformat()
        for (prv_c, prv_s, prv_e), (prv_f, prv_meta) in resolved.items():
            if prv_c == cur_c and prv_e == expected_prev_end:
                pairs.append({
                    "currency": cur_c,
                    "current_fact": cur_f,
                    "current_dup_meta": cur_meta,
                    "prior_fact": prv_f,
                    "prior_dup_meta": prv_meta,
                })

    if len(pairs) == 0:
        return {
            "ok": False,
            "exclusion_reason": f"no_consecutive_fy_pair_for_{target_local_name}",
            "available_slots": sorted([list(k) for k in resolved.keys()]),
        }
    if len(pairs) > 1:
        # Check if multiple currencies or multiple 2025 full-FYs -> NEVER silently guess!
        return {
            "ok": False,
            "exclusion_reason": f"ambiguous_multiple_consecutive_pairs_for_{target_local_name}",
            "n_pairs": len(pairs),
            "pair_keys": [
                (p["currency"], p["prior_fact"]["period_start"], p["prior_fact"]["period_end"], p["current_fact"]["period_start"], p["current_fact"]["period_end"])
                for p in pairs
            ],
        }

    return {"ok": True, **pairs[0]}
