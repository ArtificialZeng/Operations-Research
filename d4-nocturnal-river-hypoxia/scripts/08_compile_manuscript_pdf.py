"""Step 8: Compile manuscript_d4_boost.md + embedded 300-DPI figures into a journal-grade PDF with strict zero-leak check."""
from __future__ import annotations

import base64
import html
import re
import subprocess
import sys
from pathlib import Path

from pypdf import PdfReader

BASE_DIR = Path(r"D:\AI_Science\antigravity\d4_boost_nocturnal_river_hypoxia_20261125")
MD_PATH = BASE_DIR / "manuscript_d4_boost.md"
HTML_PATH = BASE_DIR / "manuscript_d4_boost.html"
PDF_PATH = BASE_DIR / "manuscript_d4_boost.pdf"
EDGE_EXE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

# Rich-HTML publication captions (zero raw underscores, carets, or ASCII inequality operators)
FIGURE_BLOCKS: dict[str, tuple[str, str]] = {
    "fig1_conus_map_and_thermal_decoupling.png": (
        "Figure 1. Continental Extent and Diurnal Thermal Decoupling Across Free-Flowing U.S. Rivers (2005&ndash;2025).",
        (
            "Panel A maps clean, dam-, lock-, swamp-, salinity-, and tidal-filtered USGS continuous dissolved oxygen rivers across all 17 populated contiguous U.S. HUC-2 watershed basins, "
            "colored on a zero-centered diverging scale by within-river diurnal thermal decoupling "
            "<em>d</em>(DO<sub>min</sub> &minus; DO<sub>max</sub>)/<em>dT</em> (Year &times; Month FE + log(<em>Q</em>) + log(<em>Q</em>)<sup>2</sup>; red &lt; 0 denotes nocturnal acceleration). "
            "Panel B compares continental thermal slopes against physical Henry's Law solubility (Benson&ndash;Krause, barometric and water-vapor adjusted) across primary discharge-controlled, "
            "water-quality-controlled, ultra-strict zero-infrastructure, USACE National Inventory of Dams (NID) dam-free (&gt;5 km from &ge;500 acre-ft dams), long-record (&ge;10 yr), and pooled-panel specifications, "
            "showing finite-sample <em>t</em>(<em>G</em>&minus;1) 95% CIs clustered at HUC-2 watershed basin (thick) and State (thin) levels."
        ),
    ),
    "fig2_24h_clock_bias_and_transfer.png": (
        "Figure 2. The 24-Hour Observational Clock-Bias Curve and Out-of-Sample Transfer-Function Correction.",
        (
            "Panel A traces apparent warm-season warming sensitivity <em>d</em>DO(<em>h</em>)/<em>dT</em> across all 24 hours of Local Mean Solar Time from multi-year 15-minute USGS IV records (2021&ndash;2024; <em>N</em> = 139 rivers), "
            "contrasting the Landsat sun-synchronous overpass window (10:00&ndash;11:00 LST) and afternoon grab-sample window (13:00&ndash;16:00 local clock) against true nocturnal DO<sub>min</sub> sensitivity and Henry's Law. "
            "Panel B plots the 24-hour missed-event rate for pre-dawn hypoxia (&lt;5, &lt;4, &lt;3, and &lt;2 mg L<sup>&minus;1</sup>). "
            "Panel C validates 17-fold Leave-One-HUC2-Basin-Out spatial cross-validation mean bias reduction, RMSE reduction, warming-slope recovery, and &lt;5 mg L<sup>&minus;1</sup> hypoxia recall gains (dashed lines show raw daytime recall)."
        ),
    ),
    "fig3_compound_heatwave_drought.png": (
        "Figure 3. Asymmetric Nocturnal Collapse and Super-Additive Hypoxia Surge Under Compound Heatwave &times; Low-Flow Drought Extremes.",
        (
            "Panel A contrasts within-river Year &times; Month FE responses of DO<sub>min</sub>, DO<sub>mean</sub>, DO<sub>max</sub>, and Benson&ndash;Krause DO<sub>sat,alt</sub> across Hot-Only (<em>T</em> &ge; P<sub>90</sub>), "
            "Dry-Only (<em>Q</em> &le; P<sub>20</sub>), and Compound Hot &times; Dry regimes (<em>N</em> = 319 rivers). "
            "Panel B reports formal Hot &times; Dry interaction terms (excess beyond additivity) for solubility-adjusted biological deficit (DO<sub>min</sub> &minus; DO<sub>sat</sub>), physical DO<sub>sat</sub>, daytime DO<sub>max</sub>, "
            "and nocturnal vs. daytime hypoxia incidence (&lt;5, &lt;3, &lt;2 mg L<sup>&minus;1</sup>), with HUC-2 basin-clustered finite-sample <em>t</em>(<em>G</em>&minus;1) 95% CIs."
        ),
    ),
    "fig4_biophysical_mechanism.png": (
        "Figure 4. Biophysical Metabolic Mechanism: Split-Half Productivity, Ionic Loading, Turbidity Attenuation, and Latitude Gradients.",
        (
            "Panel A eliminates same-period mathematical coupling by predicting late-period uniform discharge-controlled thermal slopes strictly from early-period baseline diurnal DO swing "
            "(split-half out-of-sample, <em>N</em> = 271 rivers), separating daytime photosynthetic buffering (<em>d</em>DO<sub>max</sub>/<em>dT</em>) from nocturnal respiratory acceleration (<em>d</em>DO<sub>min</sub>/<em>dT</em>). "
            "Panel B stratifies discharge-controlled decoupling across specific conductance (00095), turbidity light-attenuation tertiles (63680), and latitude climate belts."
        ),
    ),
    "fig5_secular_cwa_and_uk_replication.png": (
        "Figure 5. Secular 20-Year CONUS Trend Audit (Clean Water Act Confounding) and Independent UK Environment Agency Replication.",
        (
            "Panel A presents 2005&ndash;2025 decadal trends across long-record (&ge;10 warm-season, <em>N</em> = 194) CONUS rivers stratified by river warming rate, demonstrating how Clean Water Act nutrient/BOD recovery "
            "masks average secular widening while faster-warming rivers neutralize CWA nocturnal oxygen gains and widen diurnal swings. "
            "Panel B verifies full trans-Atlantic replication across 65 independent, 2-km-deduplicated free-flowing English rivers (UK Environment Agency Hydrology API), overlaying exact within-river biological excess sensitivity "
            "<em>d</em>(DO(<em>h</em>) &minus; DO<sub>sat</sub>)/<em>dT</em> across all 24 solar hours with HUC-2 (CONUS) and 1&deg; hydrometric grid (UK) clustered <em>t</em>(<em>G</em>&minus;1) 95% CIs."
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
        (r"^\circ", "&deg;"),
        (r"^{\circ}", "&deg;"),
        (r"\left(", "("),
        (r"\right)", ")"),
        (r"\left[", "["),
        (r"\right]", "]"),
        (r"\left", ""),
        (r"\right", ""),
        (r"\quad", "&emsp;"),
        (r"\bmod", " mod "),
        (r"\exp", "exp"),
        (r"\log", "log"),
        (r"\sin", "sin"),
        (r"\cos", "cos"),
        (r"\min", "min"),
        (r"\max", "max"),
        (r"\partial", "&part;"),
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
        (r"\pi", "&pi;"),
        (r"\beta", "&beta;"),
        (r"\alpha", "&alpha;"),
        (r"\delta", "&delta;"),
        (r"\phi", "&phi;"),
        (r"\gamma", "&gamma;"),
        (r"\varepsilon", "&epsilon;"),
        (r"\epsilon", "&epsilon;"),
        (r"\tau", "&tau;"),
        (r"\rho", "&rho;"),
        (r"\mu", "&mu;"),
        (r"\Delta", "&Delta;"),
        (r"\sigma", "&sigma;"),
        (r"\eta", "&eta;"),
        (r"\lambda", "&lambda;"),
        (r"\circ", "&deg;"),
        (r"\%", "%"),
        (r"\{", "{"),
        (r"\}", "}"),
        (r"\,", "&thinsp;"),
        (r"\ ", " "),
    ]
    for old, new in replacements:
        s = s.replace(old, new)

    for sym, tag in [("_", "sub"), ("^", "sup")]:
        while f"{sym}{{" in s:
            idx = s.index(f"{sym}{{")
            inner, end = _extract_braced(s, idx + 1)
            s = s[:idx] + f"<{tag}>{inner}</{tag}>" + s[end:]
    # Handle single-character subscripts/superscripts including +, -, and entities (fixes S_+ leak!)
    s = re.sub(r"_([A-Za-z0-9+\-]+|&[a-z]+;)", r"<sub>\1</sub>", s)
    s = re.sub(r"\^([A-Za-z0-9+\-]+)", r"<sup>\1</sup>", s)
    # Replace ASCII minus inside text nodes (not HTML tags!) with non-breaking Unicode minus (&minus;) so exponents never wrap!
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

    text = re.sub(r"`([^`]+)`", lambda m: stash(f"<code>{html.escape(m.group(1))}</code>"), text)
    text = re.sub(r"\$([^$\n]+)\$", lambda m: stash(f'<span class="math">{_tex_to_html(m.group(1))}</span>'), text)
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
        # Clean HTML figure embed directive: <!-- FIGURE:fig1_...png -->
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
            body.append(f"<ol{start_attr}>{''.join(items)}</ol>")
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
        p_cls = ' class="table-caption"' if para_raw.startswith("**Table ") else (
            ' class="table-notes"' if para_raw.startswith(("*Notes:*", "*Source:*")) else ""
        )
        body.append(f"<p{p_cls}>{_inline_md(para_raw)}</p>")

    for fname in FIGURE_BLOCKS:
        if fname not in inserted_figs and (BASE_DIR / "figures" / fname).exists():
            body.append(_embed_figure_html(fname))

    css = """
    @page {
      size: letter;
      margin: 0.70in 0.70in 0.76in 0.70in;
      @top-right {
        content: "Continental Nocturnal River Hypoxia & 24-Hour Clock-Bias (D4)";
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
      font-size: 9.5pt;
      line-height: 1.43;
      color: #1a1a1a;
      max-width: 100%;
    }
    h1.paper-title {
      font-size: 15.6pt;
      line-height: 1.24;
      margin: 0 0 8pt 0;
      color: #0b2545;
      border-bottom: 1.5pt solid #0b2545;
      padding-bottom: 6pt;
    }
    h2 {
      font-size: 11.6pt;
      color: #0b2545;
      margin: 13pt 0 5pt 0;
      border-bottom: 0.6pt solid #cbd5e1;
      padding-bottom: 2pt;
      page-break-after: avoid;
    }
    h3 {
      font-size: 10pt;
      color: #1e3a5f;
      margin: 9pt 0 4pt 0;
      page-break-after: avoid;
    }
    p { margin: 0 0 5.8pt 0; text-align: justify; }
    p.table-caption {
      font-size: 8.9pt;
      margin: 9pt 0 4pt 0;
      color: #0b2545;
      text-align: left;
      page-break-after: avoid;
    }
    p.table-notes {
      font-size: 7.7pt;
      color: #475569;
      margin: 2pt 0 8pt 0;
      text-align: left;
    }
    ul, ol { margin: 3pt 0 6.5pt 16pt; padding: 0; }
    li { margin: 0 0 3.2pt 0; text-align: justify; }
    code {
      font-family: Consolas, "Courier New", monospace;
      font-size: 8.0pt;
      background: #f1f5f9;
      padding: 0.4pt 2.4pt;
      border-radius: 2pt;
    }
    hr { border: 0; border-top: 0.6pt solid #cbd5e1; margin: 9pt 0; }
    .math { font-family: "Cambria Math", Georgia, serif; font-style: italic; }
    .math .rm, .eq-block .rm { font-style: normal; }
    sup, sub { white-space: nowrap; }
    .eq-block {
      font-family: "Cambria Math", Georgia, serif;
      font-size: 9.7pt;
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
      font-size: 7.4pt;
      line-height: 1.26;
      border-top: 1.3pt solid #0f172a;
      border-bottom: 1.3pt solid #0f172a;
    }
    thead tr { border-bottom: 0.8pt solid #334155; background: #f8fafc; }
    th, td { padding: 2.9pt 3.8pt; vertical-align: top; }
    td .math, th .math { white-space: nowrap; }
    td code { white-space: nowrap; }
    tbody tr:nth-child(even) { background: #fbfdff; }
    th.left, td.left { text-align: left; }
    th.center, td.center { text-align: center; }
    th.right, td.right { text-align: right; }
    figure.pub-fig {
      margin: 9pt 0 9pt 0;
      padding: 6pt;
      border: 0.5pt solid #e2e8f0;
      background: #ffffff;
      page-break-inside: avoid;
      text-align: center;
    }
    figure.pub-fig img {
      max-width: 100%;
      max-height: 4.25in;
      height: auto;
      display: block;
      margin: 0 auto 5pt auto;
    }
    figure.pub-fig figcaption {
      font-size: 7.9pt;
      line-height: 1.32;
      color: #334155;
      text-align: left;
    }
    """
    return (
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8' />"
        f"<title>D4 Boost Manuscript</title><style>{css}</style></head>"
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
        r"\^°",
        r"\{,\}",
        r"S_\+",
        r"DO_min",
        r"DO_max",
        r"DO_sat",
        r"T_min",
        r"T_max",
        r"log\(Q\)\^2",
        r"fig[1-5]_[a-z0-9_]+\.png",
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
