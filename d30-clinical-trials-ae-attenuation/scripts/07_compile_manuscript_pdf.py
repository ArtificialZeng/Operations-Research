"""Compile manuscript_d30_boost.md + embedded 300-DPI figures into a journal-grade PDF."""
from __future__ import annotations

import base64
import html
import re
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(r"D:\AI_Science\antigravity\d30_boost_clinical_trials_20261125")
MD_PATH = BASE_DIR / "manuscript_d30_boost.md"
HTML_PATH = BASE_DIR / "manuscript_d30_boost.html"
PDF_PATH = BASE_DIR / "manuscript_d30_boost.pdf"
EDGE_EXE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

FIGURE_BLOCKS: dict[str, tuple[str, str]] = {
    "fig1_twin_trial_identification.png": (
        "Figure 1. Exact Twin-Trial Identification, Absolute MedDRA Objectivity Gradient, and Out-of-Sample Replication.",
        (
            "Panel A shows Phase-3 Same-Molecule × Same-Sponsor FE regional gradients (N = 1,282; 0→100% site-share contrast, divide by 10 for per-+10 pp effect). "
            "Panel B contrasts registered non-serious AE proportions and non-compositional absolute MedDRA SOC peak-term rates (Subjective −9.6/−10.8 pp vs. Objective −1.2/−1.0 pp) against statistically null SAEs, mortality, and within-trial risk differences (N = 1,764). "
            "Panel C verifies replication across triplet FE, Phase-2 OOS, protocol controls, terminated trials, and non-placebo MRCTs. Finite-sample t(G−1) 95% CIs."
        ),
    ),
    "fig2_binscatter_and_disease_breadth.png": (
        "Figure 2. Exact FWL Residualized Dose-Response Binscatter and Pan-Disease Generality.",
        (
            "Panel A plots exact Frisch–Waugh–Lovell decile binscatters of registered arm AE proportions (N = 1,764, 457 programs; binscatter slopes match full-model OLS to 1e−5). "
            "Panel B reports therapeutic-area-specific EE-share slopes across all 9 major MeSH disease domains (9/9 negative, 7/9 p < 0.05)."
        ),
    ),
    "fig3_post2017_regulatory_convergence.png": (
        "Figure 3. Post-2017 EU-East Convergence Lag vs. Non-EU Cross-Sectional Persistence and FDAAA 42 CFR Part 11.",
        (
            "Panel A plots era-specific cross-sectional slopes (2020–2024 Non-EU cross-sectional slope −49.37 pp, p = 0.000113). "
            "Panel B reports Twin-Trial FE implementation-lag shifts (2020–2024 EU-East +35.68 pp placebo p_WCB = 0.030; +40.10 pp active borderline p_WCB = 0.051) and joint ICH/FDAAA horse-race interactions (overlapping 2017 timelines not individually separable). "
            "Panel C documents the post-FDAAA 1.59x rise in 0%-threshold reporting (eu × freq0 p = 0.909)."
        ),
    ),
    "fig4_war2022_and_accrual_bounds.png": (
        "Figure 4. Uncensored All-Registered Russia–Ukraine War Reallocation (2017–2025) and Simplex-Valid Accrual Bounds.",
        (
            "Panel A compares uncensored all-registered MRCT participation (2017–2025, N = 6,011; Russia 34.1%→0.0% in 2025; Ukraine 22.3%→2.95%→6.10%) against the right-censored results-posted subsample (187/398→0/43). "
            "Panel B plots uncensored within-sponsor post-war site-share shifts (N = 5,362: RU/UA −3.58 pp, LatAm +1.48 pp, Asia +1.37 pp, U.S. +0.36 pp; uncensored OOS U.S. DiD +0.33, 95% CI [−0.08, +0.74], p = 0.117). "
            "Panel C bounds patient-level attenuation across accrual ratios w in [0.5, 3.0] preserving regional simplex sum = 1.0."
        ),
    ),
    "fig5_gate2_openfda_faers.png": (
        "Figure 5. Gate-2 Post-Approval FDA Labeling Supplements, Boxed Warnings, and Exploratory FAERS Audit (N = 229 Drugs).",
        (
            "Panel A shows raw pre-approval registered AE proportions vs. post-approval FDA/FAERS profiles across EE-share bins. "
            "Panel B reports full-rank adjusted t-statistics (finite-sample t_0.975(G−1) null band shaded): pre-approval registered active AEs fall −36.0 pp, while post-approval labeling supplements and boxed warnings are statistically null (exact 95% CIs and TOST bounds in Table 5); FAERS outcomes reflect exploratory spontaneous-reporting profiles only and cannot estimate true incidence rates."
        ),
    ),
}


def _extract_braced(s: str, start: int) -> tuple[str, int]:
    """Extract balanced {...} group starting at index `start` (pointing to '{')."""
    depth = 0
    i = start
    while i < len(s):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return s[start + 1 : i], i + 1
        i += 1
    return s[start + 1 :], len(s)


def _tex_to_html(expr: str) -> str:
    """Convert inline/display LaTeX expressions used in the manuscript to clean HTML typography."""
    s = expr.strip()

    # Expand balanced \underbrace{A}_{B} -> [A] (B)
    while r"\underbrace{" in s:
        idx = s.index(r"\underbrace{")
        body, nxt = _extract_braced(s, idx + len(r"\underbrace"))
        sub_txt = ""
        if nxt < len(s) and s[nxt] == "_":
            if nxt + 1 < len(s) and s[nxt + 1] == "{":
                sub_txt, nxt = _extract_braced(s, nxt + 1)
            else:
                sub_txt, nxt = s[nxt + 1 : nxt + 2], nxt + 2
        repl = f"[{body}]<sub>{sub_txt}</sub>" if sub_txt else f"[{body}]"
        s = s[:idx] + repl + s[nxt:]

    # Expand balanced \frac{A}{B} -> (A) / (B)
    while r"\frac{" in s:
        idx = s.index(r"\frac{")
        num, nxt = _extract_braced(s, idx + len(r"\frac"))
        den, end = _extract_braced(s, nxt) if nxt < len(s) and s[nxt] == "{" else ("", nxt)
        s = s[:idx] + f"({num}) / ({den})" + s[end:]

    # Expand balanced \text{...}, \hat{...}, \bar{...}, \overline{...}, \tilde{...}, \mathbf{...}, \boldsymbol{...}
    macro_wrappers = [
        (r"\text{", '<span class="rm">', "</span>"),
        (r"\mathbf{", "<b>", "</b>"),
        (r"\boldsymbol{", "<b>", "</b>"),
        (r"\hat{", "", "&#770;"),
        (r"\bar{", "", "&#772;"),
        (r"\overline{", "", "&#772;"),
        (r"\tilde{", "", "&#771;"),
    ]
    for macro, pre, post in macro_wrappers:
        while macro in s:
            idx = s.index(macro)
            inner, end = _extract_braced(s, idx + len(macro) - 1)
            s = s[:idx] + f"{pre}{inner}{post}" + s[end:]

    replacements = [
        (r"\sum", "&Sigma;"),
        (r"\neq", "&ne;"),
        (r"\approx", "&approx;"),
        (r"\equiv", "&equiv;"),
        (r"\to", "&rarr;"),
        (r"\in", "&isin;"),
        (r"\theta", "&theta;"),
        (r"\pi", "&pi;"),
        (r"\beta", "&beta;"),
        (r"\alpha", "&alpha;"),
        (r"\delta", "&delta;"),
        (r"\phi", "&phi;"),
        (r"\gamma", "&gamma;"),
        (r"\varepsilon", "&epsilon;"),
        (r"\Delta", "&Delta;"),
        (r"\sigma", "&sigma;"),
        (r"\eta", "&eta;"),
        (r"\lambda", "&lambda;"),
        (r"\%", "%"),
        (r"\{", "{"),
        (r"\}", "}"),
        (r"\,", "&thinsp;"),
        (r"\ ", " "),
    ]
    for old, new in replacements:
        s = s.replace(old, new)

    # Balanced _{...} and ^{...}
    for sym, tag in [("_", "sub"), ("^", "sup")]:
        while f"{sym}{{" in s:
            idx = s.index(f"{sym}{{")
            inner, end = _extract_braced(s, idx + 1)
            s = s[:idx] + f"<{tag}>{inner}</{tag}>" + s[end:]
    s = re.sub(r"_([A-Za-z0-9]+|&[a-z]+;)", r"<sub>\1</sub>", s)
    s = re.sub(r"\^([A-Za-z0-9]+)", r"<sup>\1</sup>", s)
    return s


def _inline_md(text: str) -> str:
    """Render inline markdown (code spans, inline math, bold+italic, bold, italic)."""
    tokens: list[str] = []

    def stash(html_frag: str) -> str:
        idx = len(tokens)
        tokens.append(html_frag)
        return f"\x00TOK{idx}\x00"

    # Inline code first so backticks protect raw characters
    text = re.sub(
        r"`([^`]+)`",
        lambda m: stash(f"<code>{html.escape(m.group(1))}</code>"),
        text,
    )
    # Inline math $...$
    text = re.sub(
        r"\$([^$\n]+)\$",
        lambda m: stash(f'<span class="math">{_tex_to_html(m.group(1))}</span>'),
        text,
    )
    escaped = html.escape(text)
    # Bold+italic ***...*** first, then **...** (allowing inner single *italics*), then *...*
    escaped = re.sub(r"\*\*\*([^*]+?)\*\*\*", r"<strong><em>\1</em></strong>", escaped)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<em>\1</em>", escaped)
    for i, frag in enumerate(tokens):
        escaped = escaped.replace(f"\x00TOK{i}\x00", frag)
    return escaped


def _embed_figure_html(fname: str) -> str:
    img_path = BASE_DIR / "figures" / fname
    b64 = base64.b64encode(img_path.read_bytes()).decode("ascii")
    title, caption = FIGURE_BLOCKS[fname]
    return (
        f'<figure class="pub-fig">'
        f'<img src="data:image/png;base64,{b64}" alt="{html.escape(title)}" />'
        f"<figcaption><strong>{html.escape(title)}</strong> {html.escape(caption)}</figcaption>"
        f"</figure>"
    )


def convert_md_to_html(md_text: str) -> str:
    lines = md_text.splitlines()
    body: list[str] = []
    inserted_figs: set[str] = set()
    i = 0
    n = len(lines)

    while i < n:
        ln = lines[i]
        stripped = ln.strip()

        if not stripped:
            i += 1
            continue

        if stripped == "---":
            body.append("<hr />")
            i += 1
            continue

        # Display math $$...$$
        if stripped.startswith("$$") and stripped.endswith("$$") and len(stripped) > 4:
            expr = stripped[2:-2].strip()
            body.append(f'<div class="eq-block">{_tex_to_html(expr)}</div>')
            i += 1
            continue

        # Headings
        m_h = re.match(r"^(#{1,3})\s+(.*)$", stripped)
        if m_h:
            lvl = len(m_h.group(1))
            cls = ' class="paper-title"' if lvl == 1 else ""
            body.append(f"<h{lvl}{cls}>{_inline_md(m_h.group(2))}</h{lvl}>")
            i += 1
            continue

        # Pipe table
        if stripped.startswith("|") and i + 1 < n and lines[i + 1].strip().startswith("|---") or (
            stripped.startswith("|") and i + 1 < n and re.match(r"^\|\s*:?---", lines[i + 1].strip())
        ):
            tbl_lines = [stripped]
            i += 1
            while i < n and lines[i].strip().startswith("|"):
                tbl_lines.append(lines[i].strip())
                i += 1
            headers = [c.strip() for c in tbl_lines[0].strip("|").split("|")]
            aligns = [c.strip() for c in tbl_lines[1].strip("|").split("|")]
            col_cls = []
            for a in aligns:
                if a.startswith(":") and a.endswith(":"):
                    col_cls.append("center")
                elif a.endswith(":"):
                    col_cls.append("right")
                else:
                    col_cls.append("left")
            th_html = "".join(
                f'<th class="{col_cls[idx] if idx < len(col_cls) else "left"}">{_inline_md(h)}</th>'
                for idx, h in enumerate(headers)
            )
            rows_html = []
            for rln in tbl_lines[2:]:
                cells = [c.strip() for c in rln.strip("|").split("|")]
                tds = "".join(
                    f'<td class="{col_cls[idx] if idx < len(col_cls) else "left"}">{_inline_md(c)}</td>'
                    for idx, c in enumerate(cells)
                )
                rows_html.append(f"<tr>{tds}</tr>")
            body.append(
                f'<div class="table-wrap"><table><thead><tr>{th_html}</tr></thead>'
                f'<tbody>{"".join(rows_html)}</tbody></table></div>'
            )
            continue

        # Unordered list
        if stripped.startswith("- "):
            items = []
            while i < n and lines[i].strip().startswith("- "):
                items.append(f"<li>{_inline_md(lines[i].strip()[2:])}</li>")
                i += 1
            body.append(f"<ul>{''.join(items)}</ul>")
            continue

        # Ordered list (preserve explicit start number & nested sub-bullets!)
        m_ol = re.match(r"^(\d+)\.\s+", stripped)
        if m_ol:
            start_num = int(m_ol.group(1))
            items = []
            while i < n and re.match(r"^\d+\.\s+", lines[i].strip()):
                item_txt = re.sub(r"^\d+\.\s+", "", lines[i].strip())
                i += 1
                sub_items = []
                while i < n and re.match(r"^\s{2,}-\s+", lines[i]):
                    sub_items.append(f"<li>{_inline_md(lines[i].strip()[2:])}</li>")
                    i += 1
                sub_html = f"<ul>{''.join(sub_items)}</ul>" if sub_items else ""
                items.append(f"<li>{_inline_md(item_txt)}{sub_html}</li>")
            start_attr = f' start="{start_num}"' if start_num != 1 else ""
            body.append(f"<ol{start_attr}>{''.join(items)}</ol>")
            continue

        # Paragraph (group consecutive plain lines)
        para_lines = [stripped]
        i += 1
        while i < n:
            nxt = lines[i].strip()
            if (
                not nxt
                or nxt == "---"
                or nxt.startswith(("#", "|", "- ", "$$"))
                or re.match(r"^\d+\.\s+", nxt)
            ):
                break
            para_lines.append(nxt)
            i += 1
        para_raw = " ".join(para_lines)
        p_cls = ' class="table-caption"' if para_raw.startswith("**Table ") else (
            ' class="table-notes"' if para_raw.startswith(("*Notes:*", "*Source:*")) else ""
        )
        body.append(f"<p{p_cls}>{_inline_md(para_raw)}</p>")

        # Auto-embed any figure referenced for the first time in this paragraph
        for fname in FIGURE_BLOCKS:
            if fname in para_raw and fname not in inserted_figs:
                body.append(_embed_figure_html(fname))
                inserted_figs.add(fname)

    # Append any remaining figures not triggered inline
    for fname in FIGURE_BLOCKS:
        if fname not in inserted_figs:
            body.append(_embed_figure_html(fname))

    css = """
    @page {
      size: letter;
      margin: 0.72in 0.72in 0.78in 0.72in;
      @top-right {
        content: "Geographic Non-Serious AE Reporting & Regulatory Dynamics (D30 v2)";
        font-family: Georgia, "Times New Roman", serif;
        font-size: 7.5pt;
        color: #555;
      }
      @bottom-center {
        content: "Page " counter(page) " of " counter(pages);
        font-family: Georgia, "Times New Roman", serif;
        font-size: 8pt;
        color: #555;
      }
    }
    @page :first { @top-right { content: normal; } }
    body {
      font-family: Georgia, "Times New Roman", serif;
      font-size: 9.6pt;
      line-height: 1.44;
      color: #1a1a1a;
      max-width: 100%;
    }
    h1.paper-title {
      font-size: 16.5pt;
      line-height: 1.24;
      margin: 0 0 8pt 0;
      color: #0b2545;
      border-bottom: 1.5pt solid #0b2545;
      padding-bottom: 6pt;
    }
    h2 {
      font-size: 12pt;
      color: #0b2545;
      margin: 14pt 0 5pt 0;
      border-bottom: 0.6pt solid #cbd5e1;
      padding-bottom: 2pt;
      page-break-after: avoid;
    }
    h3 {
      font-size: 10.2pt;
      color: #1e3a5f;
      margin: 10pt 0 4pt 0;
      page-break-after: avoid;
    }
    p { margin: 0 0 6pt 0; text-align: justify; }
    p.table-caption {
      font-size: 9pt;
      margin: 10pt 0 4pt 0;
      color: #0b2545;
      text-align: left;
      page-break-after: avoid;
    }
    p.table-notes {
      font-size: 7.8pt;
      color: #475569;
      margin: 2pt 0 8pt 0;
      text-align: left;
    }
    ul, ol { margin: 3pt 0 7pt 16pt; padding: 0; }
    li { margin: 0 0 3.5pt 0; text-align: justify; }
    code {
      font-family: Consolas, "Courier New", monospace;
      font-size: 8.3pt;
      background: #f1f5f9;
      padding: 0.5pt 2.5pt;
      border-radius: 2pt;
    }
    hr { border: 0; border-top: 0.6pt solid #cbd5e1; margin: 10pt 0; }
    .math { font-family: "Cambria Math", Georgia, serif; font-style: italic; }
    .math .rm, .eq-block .rm { font-style: normal; }
    .eq-block {
      font-family: "Cambria Math", Georgia, serif;
      font-size: 9.8pt;
      text-align: center;
      margin: 8pt 0;
      padding: 6pt 10pt;
      background: #f8fafc;
      border-left: 2pt solid #0b2545;
    }
    .table-wrap { margin: 4pt 0 4pt 0; page-break-inside: avoid; }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 7.7pt;
      line-height: 1.28;
      border-top: 1.3pt solid #0f172a;
      border-bottom: 1.3pt solid #0f172a;
    }
    thead tr { border-bottom: 0.8pt solid #334155; background: #f8fafc; }
    th, td { padding: 3.2pt 4pt; vertical-align: top; }
    td code { white-space: nowrap; }
    tbody tr:nth-child(even) { background: #fbfdff; }
    th.left, td.left { text-align: left; }
    th.center, td.center { text-align: center; }
    th.right, td.right { text-align: right; }
    figure.pub-fig {
      margin: 10pt 0 10pt 0;
      padding: 6pt;
      border: 0.5pt solid #e2e8f0;
      background: #ffffff;
      page-break-inside: avoid;
      text-align: center;
    }
    figure.pub-fig img {
      max-width: 100%;
      max-height: 4.3in;
      height: auto;
      display: block;
      margin: 0 auto 5pt auto;
    }
    figure.pub-fig figcaption {
      font-size: 8pt;
      line-height: 1.32;
      color: #334155;
      text-align: left;
    }
    """
    return (
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8' />"
        f"<title>D30 Boost Manuscript</title><style>{css}</style></head>"
        f"<body>{''.join(body)}</body></html>"
    )


def main() -> int:
    md_text = MD_PATH.read_text(encoding="utf-8")
    html_doc = convert_md_to_html(md_text)
    HTML_PATH.write_text(html_doc, encoding="utf-8")

    if not EDGE_EXE.exists():
        print(f"[ERROR] Microsoft Edge not found at {EDGE_EXE}", file=sys.stderr)
        return 1

    cmd = [
        str(EDGE_EXE),
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={PDF_PATH}",
        HTML_PATH.as_uri(),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
    if res.returncode != 0 or not PDF_PATH.exists() or PDF_PATH.stat().st_size < 50_000:
        print(f"[ERROR] Edge PDF compile failed rc={res.returncode}: {res.stderr}", file=sys.stderr)
        return 1

    # Remove intermediate HTML to keep root directory spotless
    HTML_PATH.unlink(missing_ok=True)
    print(f"[DONE] Compiled {PDF_PATH} ({PDF_PATH.stat().st_size:,} bytes)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
