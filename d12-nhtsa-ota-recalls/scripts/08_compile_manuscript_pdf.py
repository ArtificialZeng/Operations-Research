"""Step 8: Compile manuscript_d12_boost.md + embedded 300-DPI figures into a journal-grade PDF
with strict zero-leak verification.
"""
from __future__ import annotations

import base64
import html
import re
import subprocess
import sys
from pathlib import Path

from pypdf import PdfReader

BASE_DIR = Path(r"D:\AI_Science\antigravity\d12_boost_nhtsa_ota_recalls_20261125")
MD_PATH = BASE_DIR / "manuscript_d12_boost.md"
HTML_PATH = BASE_DIR / "manuscript_d12_boost.html"
PDF_PATH = BASE_DIR / "manuscript_d12_boost.pdf"
EDGE_EXE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

FIGURE_BLOCKS: dict[str, tuple[str, str]] = {
    "fig1_api_audit_and_blast_radius.png": (
        "Figure 1. Public NHTSA Campaign API Endpoint Metadata Anomaly (2019&ndash;2026) and Conditional Campaign Size vs. Unconditional OEM ITT.",
        (
            "Panel A compares annual audited Pure-OTA and Hybrid-OTA vehicle recall counts against NHTSA's live public Campaign API "
            "<code>overTheAirUpdate = True</code> indicator across 1,452 queried campaigns (0 HTTP errors; 0/250 physical false negatives) alongside NHTSA's separate "
            "<em>2025 Annual Recalls Report</em> (green star: 33 OTA recalls in 2025). The public API matched audited text on 54/54 (100.0%) in 2019&ndash;2023 and "
            "31/33 (93.9%) in 2024, drifted to 4/7 (57.1%) during Jan&ndash;May 8, 2025 (final <code>True</code>: Volvo <code>25V282000</code>, 36/36 records), and returned "
            "0/68 (0.0%) <code>True</code> after May 8, 2025 (beginning May 9 with Ford <code>25V315000</code>, 44/44 <code>False</code> despite explicit OTA text). "
            "Panel B contrasts conditional within-OEM campaign-size differentials on log(1 + Affected Vehicle-Instances) (Hybrid-OTA +1.95, <em>p</em><sub>WCB</sub> = 0.006; "
            "Official API OTA +1.89, <em>p</em><sub>WCB</sub> = 0.039; Pure-OTA +1.08, <em>p</em><sub>WCB</sub> = 0.233) against distinct unconditional OEM-level estimands "
            "(TWFE ITT +0.18, <em>p</em><sub>WCB</sub> = 0.579; Sun&ndash;Abraham IW &minus;0.53, <em>p</em><sub>t</sub> = 0.470; SW &times; SDV cohort +0.26, <em>p</em><sub>WCB</sub> = 0.094)."
        ),
    ),
    "fig2_itt_event_study_and_fleet_selection.png": (
        "Figure 2. Unconditional Intent-to-Treat OEM First-OTA Event Study (TWFE &amp; Sun&ndash;Abraham Saturated IW) and Campaign-Size Distributions.",
        (
            "Panel A estimates dynamic effects around each adopting OEM's first OTA recall pooling all unconditional software recalls (OTA + Dealer-Software; "
            "TWFE <em>N</em> = 1,239, <em>G</em> = 68; Sun&ndash;Abraham saturated cohort &times; relative-time IW <em>N</em> = 1,233, <em>G</em> = 67, 7 cohorts, "
            "39 cells, reference <em>k</em> = &minus;1), confirming clean pre-trends (TWFE <em>p</em> = 0.424; SA IW <em>p</em> = 0.775) and statistically null post shifts "
            "(TWFE +0.18, <em>p</em><sub>WCB</sub> = 0.579; SA IW &minus;0.53, <em>p</em><sub>t</sub> = 0.470). Panel B overlays empirical CDFs of campaign recall size "
            "(affected vehicle-instances, log<sub>10</sub> scale), illustrating conditional size sorting where 67.3% of Hybrid-OTA recalls affect &ge;10,000 vehicle-instances "
            "vs. 38.8% of Dealer-Software."
        ),
    ),
    "fig3_maturation_and_age_decay_cliff.png": (
        "Figure 3. Official U.S. DOT Recall Maturation Curves and OTA Flattening of the Vehicle-Age Compliance-Decay Cliff.",
        (
            "Panel A traces median official DOT completion rates across six campaign-age intervals since <code>RCDATE</code> (0&ndash;3 months through &gt;24 months; "
            "shaded mature window &ge;18 months post-<code>RCDATE</code> serving as an operational proxy for six quarterly reports under 49 CFR &sect; 573.7(a); "
            "0&ndash;3m physical median reflects <em>n</em> = 9 pre-completed filings). Panel B plots mean mature (&ge;18-month) completion rates by vehicle age at recall filing, "
            "showing that Dealer-Software completion declines at &minus;3.57 pp/yr (<em>p</em><sub>WCB</sub> = 0.001, matching Physical Hardware's &minus;3.41 pp/yr slope), "
            "whereas Pure-OTA offsets 86.3% (+3.08 pp/yr, <em>p</em><sub>WCB</sub> = 0.039), Hybrid-OTA offsets 63.0% (+2.25 pp/yr, <em>p</em><sub>WCB</sub> = 0.044), "
            "and Official API OTA offsets 77.0% (+2.74 pp/yr, <em>p</em><sub>WCB</sub> = 0.002; excluding Tesla: +1.96 pp/yr, <em>p</em><sub>WCB</sub> = 0.023; Any OTA excl. Tesla: +2.37 pp/yr, <em>p</em><sub>WCB</sub> = 0.030)."
        ),
    ),
    "fig4_breakeven_frontier_and_net_exposure.png": (
        "Figure 4. Sample-Matched Break-Even Frontier and Recall-Level Unremedied Vehicle-Instance Proxy with Exact Wild Cluster Bootstrap Inference.",
        (
            "Panel A maps mature (&ge;18-month) completion rates and recall-size multipliers against the descriptive break-even frontier "
            "<em>r</em>*(<em>M</em>) = 1 &minus; (1 &minus; <em>r</em><sub>0</sub>)/<em>M</em> anchored at OTA-capable OEMs' mature Dealer-Software baseline <em>r</em><sub>0</sub> = 85.71%: "
            "Pure-OTA (<em>N</em> = 46; Tesla accounts for 98.7% of affected vehicle-instances; Non-Tesla <em>N</em> = 19 mean 99.11%) clears its frontier by +1.84 pp (99.18% vs. 97.34%), "
            "whereas Legacy Hybrid-OTA falls &minus;2.53 pp below (95.66% vs. 98.19%; pure SW-choice Hybrid-OTA &minus;2.76 pp). Panel B plots CR1 95% CIs and exact "
            "<em>B</em> = 999 Rademacher <em>p</em><sub>WCB</sub> values on mature log(1 + Unremedied Vehicle-Instance Proxy): relative to physical recalls, Pure-OTA (&minus;1.92, <em>p</em><sub>WCB</sub> = 0.065) "
            "and Hybrid-OTA (+1.42, <em>p</em><sub>WCB</sub> = 0.055) are marginally significant at 10% under WCB while their contrast (+3.33) has <em>p</em><sub>WCB</sub> = 0.007; "
            "relative to OTA-capable OEMs' dealer software, Pure-OTA is null (&minus;0.60, <em>p</em><sub>WCB</sub> = 0.401), Hybrid-OTA is +1.13 (<em>p</em><sub>WCB</sub> = 0.097), "
            "and their contrast (+1.73) has <em>p</em><sub>WCB</sub> = 0.079. Holding campaign size fixed, both Pure-OTA (&minus;2.06, <em>p</em><sub>WCB</sub> = 0.035) and Hybrid-OTA (&minus;0.67, <em>p</em><sub>WCB</sub> = 0.012) compress residuals."
        ),
    ),
    "fig5_safety_oversight_and_complaint_did.png": (
        "Figure 5. Within-OEM Safety Severity, Oversight, Repeat Cascades, and Deduplicated Consumer Complaint-Decay Event Study.",
        (
            "Panel A plots within-OEM fixed-effects differences (percentage points, CR1 95% CIs) comparing Pure-OTA and Hybrid-OTA against Dealer-Software across FMVSS noncompliance "
            "(Pure-OTA +27.8 pp, <em>p</em><sub>WCB</sub> = 0.005), formal ODI investigations (Pure-OTA &minus;12.6 pp, <em>p</em><sub>WCB</sub> = 0.090; API OTA &minus;5.6 pp, <em>p</em><sub>WCB</sub> = 0.019), "
            "acute hazard advisories, and uncensored 365- and 730-day repeat-defect cascades (nulls). Panel B displays the balanced [&minus;12m, +12m] dynamic event study linking "
            "437,886 unique deduplicated NHTSA ODI complaints (636,875 component records) to 737 software recalls (2021&ndash;2025), highlighting the pre-recall exposure ramp-up "
            "(pre-trend Wald <em>F</em>(11, 114) = 2.56, <em>p</em> = 0.006) and honest empirical nulls under both full [&minus;12, +12] and short [&minus;3, +12] windows "
            "(<em>p</em><sub>WCB</sub> &ge; 0.27)."
        ),
    ),
}


def _extract_braced(s: str, start: int) -> tuple[str, int]:
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
    s = expr.strip()

    while r"\frac{" in s:
        idx = s.index(r"\frac{")
        num, nxt = _extract_braced(s, idx + len(r"\frac"))
        den, end = _extract_braced(s, nxt) if nxt < len(s) and s[nxt] == "{" else ("", nxt)
        s = s[:idx] + f"({num}) / ({den})" + s[end:]

    macro_wrappers = [
        (r"\text{", '<span class="rm">', "</span>"),
        (r"\mathrm{", '<span class="rm">', "</span>"),
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
        (r"{,}", ","),
        (r"\qquad", "&emsp;&emsp;"),
        (r"\quad", "&emsp;"),
        (r"\iff", "&hArr;"),
        (r"\gg", "&gg;"),
        (r"\ll", "&ll;"),
        (r"\mid", " | "),
        (r"\left(", "("),
        (r"\right)", ")"),
        (r"\left[", "["),
        (r"\right]", "]"),
        (r"\left", ""),
        (r"\right", ""),
        (r"\exp", "exp"),
        (r"\log", "log"),
        (r"\min", "min"),
        (r"\max", "max"),
        (r"\sum", "&Sigma;"),
        (r"\times", "&times;"),
        (r"\cdot", "&middot;"),
        (r"\pm", "&plusmn;"),
        (r"\le", "&le;"),
        (r"\ge", "&ge;"),
        (r"\neq", "&ne;"),
        (r"\approx", "&approx;"),
        (r"\equiv", "&equiv;"),
        (r"\to", "&rarr;"),
        (r"\in", "&isin;"),
        (r"\theta", "&theta;"),
        (r"\beta", "&beta;"),
        (r"\alpha", "&alpha;"),
        (r"\delta", "&delta;"),
        (r"\phi", "&phi;"),
        (r"\psi", "&psi;"),
        (r"\gamma", "&gamma;"),
        (r"\varepsilon", "&epsilon;"),
        (r"\epsilon", "&epsilon;"),
        (r"\tau", "&tau;"),
        (r"\rho", "&rho;"),
        (r"\mu", "&mu;"),
        (r"\Delta", "&Delta;"),
        (r"\sigma", "&sigma;"),
        (r"\lambda", "&lambda;"),
        (r"\ell", "&#8467;"),
        (r"\%", "%"),
        (r"\{", "{"),
        (r"\}", "}"),
        (r"\,", "&thinsp;"),
        (r"\ ", " "),
    ]
    for old, new in replacements:
        s = s.replace(old, new)

    # Convert braced subscripts/superscripts first (loop to catch nested braces cleanly)
    for _ in range(3):
        for sym, tag in [("_", "sub"), ("^", "sup")]:
            while f"{sym}{{" in s:
                idx = s.index(f"{sym}{{")
                inner, end = _extract_braced(s, idx + 1)
                s = s[:idx] + f"<{tag}>{inner}</{tag}>" + s[end:]

    s = re.sub(r"_([A-Za-z0-9+\-]+|&[a-z]+;)", r"<sub>\1</sub>", s)
    s = re.sub(r"\^([A-Za-z0-9+\-*]+)", r"<sup>\1</sup>", s)

    # Replace ASCII minus inside text nodes with non-breaking Unicode minus
    parts = re.split(r"(<[^>]+>)", s)
    for i in range(0, len(parts), 2):
        parts[i] = parts[i].replace("-", "&minus;")
    return "".join(parts)


def _inline_md(text: str) -> str:
    tokens: list[str] = []

    def stash(html_frag: str) -> str:
        idx = len(tokens)
        tokens.append(html_frag)
        return f"\x00TOK{idx}\x00"

    # Protect escaped dollar signs (e.g. \$75) BEFORE math parsing!
    text = text.replace(r"\$", "\x00DOLLAR\x00")
    text = re.sub(r"`([^`]+)`", lambda m: stash(f"<code>{html.escape(m.group(1))}</code>"), text)
    text = re.sub(r"\$([^$\n]+)\$", lambda m: stash(f'<span class="math">{_tex_to_html(m.group(1))}</span>'), text)
    text = text.replace("\x00DOLLAR\x00", "$")

    escaped = html.escape(text)
    escaped = re.sub(r"\*\*\*([^*]+?)\*\*\*", r"<strong><em>\1</em></strong>", escaped)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<em>\1</em>", escaped)
    for i, frag in enumerate(tokens):
        escaped = escaped.replace(f"\x00TOK{i}\x00", frag)
    return escaped


def _embed_figure_html(fname: str) -> str:
    img_path = BASE_DIR / "figures" / fname
    b64 = base64.b64encode(img_path.read_bytes()).decode("ascii")
    title_html, caption_html = FIGURE_BLOCKS[fname]
    alt_txt = re.sub(r"<[^>]+>", "", title_html)
    return (
        f'<figure class="pub-fig">'
        f'<img src="data:image/png;base64,{b64}" alt="{html.escape(alt_txt)}" />'
        f"<figcaption><strong>{title_html}</strong> {caption_html}</figcaption>"
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
        m_fig = re.match(r"^<!--\s*FIGURE:([A-Za-z0-9_.\-]+)\s*-->$", stripped)
        if m_fig:
            fname = m_fig.group(1)
            if fname in FIGURE_BLOCKS and fname not in inserted_figs:
                body.append(_embed_figure_html(fname))
                inserted_figs.add(fname)
            i += 1
            continue
        if stripped == "---":
            body.append("<hr />")
            i += 1
            continue
        if stripped.startswith("$$") and stripped.endswith("$$") and len(stripped) > 4:
            expr = stripped[2:-2].strip()
            body.append(f'<div class="eq-block">{_tex_to_html(expr)}</div>')
            i += 1
            continue

        m_h = re.match(r"^(#{1,3})\s+(.*)$", stripped)
        if m_h:
            lvl = len(m_h.group(1))
            cls = ' class="paper-title"' if lvl == 1 else ""
            body.append(f"<h{lvl}{cls}>{_inline_md(m_h.group(2))}</h{lvl}>")
            i += 1
            continue

        if stripped.startswith("|") and i + 1 < n and re.match(r"^\|\s*:?---", lines[i + 1].strip()):
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

        if stripped.startswith("- "):
            items = []
            while i < n and lines[i].strip().startswith("- "):
                items.append(f"<li>{_inline_md(lines[i].strip()[2:])}</li>")
                i += 1
            body.append(f"<ul>{''.join(items)}</ul>")
            continue

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
            is_refs = bool(body and "<h2>References</h2>" in body[-1])
            cls_attr = ' class="refs-list"' if is_refs else ""
            body.append(f"<ol{cls_attr}{start_attr}>{''.join(items)}</ol>")
            continue

        para_lines = [stripped]
        i += 1
        while i < n:
            nxt = lines[i].strip()
            if (
                not nxt
                or nxt == "---"
                or nxt.startswith(("#", "|", "- ", "$$", "<!--"))
                or re.match(r"^\d+\.\s+", nxt)
            ):
                break
            para_lines.append(nxt)
            i += 1
        para_raw = " ".join(para_lines)
        p_cls = (
            ' class="table-caption"'
            if para_raw.startswith("**Table ")
            else (' class="table-notes"' if para_raw.startswith(("*Notes:*", "*Source:*")) else "")
        )
        body.append(f"<p{p_cls}>{_inline_md(para_raw)}</p>")

    for fname in FIGURE_BLOCKS:
        if fname not in inserted_figs and (BASE_DIR / "figures" / fname).exists():
            body.append(_embed_figure_html(fname))

    css = """
    @page {
      size: letter;
      margin: 0.68in 0.68in 0.74in 0.68in;
      @top-right {
        content: "The Software-Defined Vehicle Recall Paradox (D12)";
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
      font-size: 9.4pt;
      line-height: 1.43;
      color: #1a1a1a;
      max-width: 100%;
    }
    h1.paper-title {
      font-size: 14.8pt;
      line-height: 1.24;
      margin: 0 0 8pt 0;
      color: #0b2545;
      border-bottom: 1.5pt solid #0b2545;
      padding-bottom: 6pt;
    }
    h2 {
      font-size: 11.4pt;
      color: #0b2545;
      margin: 12pt 0 5pt 0;
      border-bottom: 0.6pt solid #cbd5e1;
      padding-bottom: 2pt;
      page-break-after: avoid;
    }
    h3 {
      font-size: 9.9pt;
      color: #1e3a5f;
      margin: 9pt 0 4pt 0;
      page-break-after: avoid;
    }
    p { margin: 0 0 5.6pt 0; text-align: justify; }
    p.table-caption {
      font-size: 8.6pt;
      margin: 7pt 0 3pt 0;
      color: #0b2545;
      text-align: left;
      break-inside: avoid;
      page-break-inside: avoid;
      break-after: avoid;
      page-break-after: avoid;
    }
    p.table-notes {
      font-size: 7.6pt;
      color: #475569;
      margin: 2pt 0 8pt 0;
      text-align: left;
    }
    ul, ol { margin: 3pt 0 6pt 16pt; padding: 0; }
    li { margin: 0 0 3.0pt 0; text-align: justify; }
    ol.refs-list li { text-align: left; font-size: 8.6pt; line-height: 1.35; break-inside: avoid; page-break-inside: avoid; }
    code {
      font-family: Consolas, "Courier New", monospace;
      font-size: 7.8pt;
      background: #f1f5f9;
      padding: 0.4pt 2.2pt;
      border-radius: 2pt;
    }
    hr { border: 0; border-top: 0.6pt solid #cbd5e1; margin: 8pt 0; }
    .math { font-family: "Cambria Math", Georgia, serif; font-style: italic; }
    .math .rm, .eq-block .rm { font-style: normal; }
    sup, sub { white-space: nowrap; }
    .eq-block {
      font-family: "Cambria Math", Georgia, serif;
      font-size: 9.6pt;
      text-align: center;
      margin: 7pt 0;
      padding: 6pt 10pt;
      background: #f8fafc;
      border-left: 2pt solid #0b2545;
    }
    .table-wrap { margin: 4pt 0 4pt 0; page-break-inside: avoid; }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 6.85pt;
      line-height: 1.18;
      border-top: 1.3pt solid #0f172a;
      border-bottom: 1.3pt solid #0f172a;
    }
    thead tr { border-bottom: 0.8pt solid #334155; background: #f8fafc; }
    th, td { padding: 1.9pt 2.8pt; vertical-align: top; }
    td .math, th .math { white-space: nowrap; }
    td code { white-space: nowrap; }
    tbody tr:nth-child(even) { background: #fbfdff; }
    th.left, td.left { text-align: left; }
    th.center, td.center { text-align: center; }
    th.right, td.right { text-align: right; }
    figure.pub-fig {
      margin: 8pt 0 8pt 0;
      padding: 5.5pt;
      border: 0.5pt solid #e2e8f0;
      background: #ffffff;
      page-break-inside: avoid;
      text-align: center;
    }
    figure.pub-fig img {
      max-width: 100%;
      max-height: 4.15in;
      height: auto;
      display: block;
      margin: 0 auto 5pt auto;
    }
    figure.pub-fig figcaption {
      font-size: 7.8pt;
      line-height: 1.31;
      color: #334155;
      text-align: left;
    }
    """
    return (
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8' />"
        f"<title>D12 Boost Manuscript</title><style>{css}</style></head>"
        f"<body>{''.join(body)}</body></html>"
    )


def verify_pdf_zero_leaks(pdf_path: Path) -> tuple[int, list[str]]:
    reader = PdfReader(str(pdf_path))
    full_txt = "\n".join((p.extract_text() or "") for p in reader.pages)
    bad_patterns = [
        r"\\[A-Za-z]+",
        r"\$\$",
        r"\*\*",
        r"\|---",
        r"\{,\}",
        r"\\text\{",
        r"\\mathbf\{",
        r"\\frac\{",
        r"\bp_WCB\b",
        r"\bp_t\b",
        r"\^[0-9A-Za-z{]",
        r"fig[1-5]_[a-z0-9_]+\.png",
        r"<!--",
    ]
    leaks = []
    for pat in bad_patterns:
        if re.search(pat, full_txt):
            leaks.append(pat)
    return len(reader.pages), leaks


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
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=90, check=False)
    if res.returncode != 0 or not PDF_PATH.exists() or PDF_PATH.stat().st_size < 50_000:
        print(f"[ERROR] Edge PDF compile failed rc={res.returncode}: {res.stderr}", file=sys.stderr)
        return 1

    n_pages, leaks = verify_pdf_zero_leaks(PDF_PATH)
    HTML_PATH.unlink(missing_ok=True)
    if leaks:
        print(f"[ERROR] Leaked LaTeX/Markdown/ASCII tokens found in PDF: {leaks}", file=sys.stderr)
        return 2
    print(f"[DONE] Compiled {PDF_PATH} ({PDF_PATH.stat().st_size:,} bytes, {n_pages} pages, 0 leaked tokens)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
