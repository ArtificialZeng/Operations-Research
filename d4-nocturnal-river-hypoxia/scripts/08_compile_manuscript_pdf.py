"""Step 8: Compile Nature Water v4 main manuscript and Supplementary Information into journal-grade PDFs
via headless Microsoft Edge with an isolated temporary user-data-dir and strict zero-leak verification.
"""
from __future__ import annotations

import base64
import html
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from pypdf import PdfReader

BASE_DIR = Path(r"D:\AI_Science\antigravity\d4_boost_nocturnal_river_hypoxia_20261125")
EDGE_EXE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

FIGURE_BLOCKS: dict[str, tuple[str, str]] = {
    "fig1_nw_monitoring_clock_and_coverage.png": (
        "Figure 1. Real-world agency sampling clock, independent field-meter fidelity, and cross-network common-support coverage.",
        (
            "<b>a</b>, Local mean solar hour distribution of 10,019 warm-season (May&ndash;October, 2015&ndash;2024) discrete dissolved-oxygen (DO) agency field visits across 205 screened U.S. rivers in the Water Quality Portal (bars), "
            "overlaid with the 2021&ndash;2024 subdaily cohort (step line; 1,391 visits across 76 stations) and mean warm-season astronomical darkness shading. "
            "<b>b</b>, Co-located independent field-meter versus continuous USGS sonde DO readings (<i>n</i> = 1,287 pairs within &le;30 min across 76 stations; median |&Delta;<i>t</i>| = 0 min; shaded band shows &plusmn;0.20 mg L<sup>&minus;1</sup> USGS accuracy tolerance); "
            "inset compares actual agency visit detection versus pre-dawn sonde detection on the 71 matched visit dates with persistent &ge;2 h &lt;5 mg L<sup>&minus;1</sup> hypoxia. "
            "<b>c</b>, Common-support entry rates across U.S. (93.8%; 87,785 of 93,538 candidate site-nights) and English (82.2%; 27,635 of 33,612) networks stratified by native sampling cadence."
        ),
    ),
    "fig2_nw_loro_cross_network_validation.png": (
        "Figure 2. Cross-network leave-one-reading-out (LORO) nocturnal detection, first-light daylight plateau, and anti-circularity audit.",
        (
            "<b>a</b>, Primary LORO recall (&lt;5 mg L<sup>&minus;1</sup>) across six single-reading schedules on identical common-support site-nights in the U.S. (<i>n</i> = 8,462 LORO hypoxic nights; 139 sites) and England (<i>n</i> = 2,360; 65 sites), "
            "with finite-sample <i>t</i>(<i>G</i>&minus;1) 95% CIs clustered by HUC-2 basin (U.S.) or 1&deg; hydrometric grid (England). "
            "<b>b</b>, LORO recall curve from 180 min before to 120 min after geometric sunrise showing peak detection at geometric sunrise (SR + 0 min, selected out-of-sample in both networks) and a near-peak plateau in safe first-light daylight (SR + 30 min). "
            "<b>c</b>, Paired pre-dawn minus 14:30 recall gains across anti-circularity (&plusmn;30 min LORO), persistence (&ge;2 readings, &ge;2 h), sensor tolerance (&lt;4.8 mg L<sup>&minus;1</sup> buffer and independent &sigma; = 0.20 mg L<sup>&minus;1</sup> probe noise), "
            "60-min downsampling, equal-site weighting, chronic-site exclusion (&gt;50% nights hypoxic), Leave-One-Region-Out holdout, and zero-shot cross-Atlantic transfer."
        ),
    ),
    "fig3_nw_censoring_duration_and_leadtime.png": (
        "Figure 3. Nocturnal boundary censoring, duration bias diagnosis, and episodic actionable detection lead times.",
        (
            "<b>a</b>, Share of &lt;5 mg L<sup>&minus;1</sup> site-nights classified by boundary censoring inside astronomical darkness (only 14.7% U.S. and 15.3% England close at both ends; 80.1% U.S. and 76.7% England remain hypoxic past sunrise). "
            "<b>b</b>, Survival curves comparing naive closed-in-night runs (dotted; median 1.0&ndash;2.0 h), Kaplan&ndash;Meier right-censored nocturnal runs (dashed), and unbroken continuous-series episodes crossing sunrise and sunset (solid; median 13.5 h U.S., 13.0 h England). "
            "<b>c</b>, Median lead time on episodic 2&ndash;24 h actionable &lt;5 mg L<sup>&minus;1</sup> events relative to episode nadir (filled circle) and episode recovery (open diamond), contrasting post-recovery afternoon sampling, near-nadir pre-dawn/first-light grabs, and pre-nadir continuous sonde alerts."
        ),
    ),
    "fig4_nw_equal_budget_protocol_frontier.png": (
        "Figure 4. Equal-budget operational monitoring comparison, surveillance Pareto frontier, and cost-ratio decision map.",
        (
            "<b>a</b>, Distinct non-overlapping actionable episodes (&ge;2 h &lt;5 mg L<sup>&minus;1</sup>, LORO) detected per 100 daytime-visit-equivalent budget units under an identical annual budget (24 eq site<sup>&minus;1</sup> yr<sup>&minus;1</sup>; <i>m</i><sub>night</sub> = 1.75&times;, <i>K</i><sub>sonde</sub> = 40) evaluated strictly out-of-sample on post-Year-1 warm seasons across 1,000 stratified calendar schedules. "
            "<b>b</b>, Surveillance Pareto frontier plotting unit cost per distinct episode (USD, log scale, benchmark $200 daytime visit<sup>&minus;1</sup>) against share of impaired site-years flagged at least once, showing dominance of first-light grabs among grab-only protocols and top-20% risk-stratified sondes (Year-1 daytime screening) plus first-light grabs overall. "
            "<b>c</b>, Two-dimensional cost-ratio decision map across nocturnal grab cost multipliers (<i>m</i><sub>night</sub>) and annual continuous-sonde visit-equivalents (<i>K</i><sub>sonde</sub>); star marks central cost assumptions (1.75&times;, <i>K</i><sub>sonde</sub> = 40), dashed vertical line marks grab-only dark pre-dawn breakeven (<i>m</i>* = 1.53&times;), and coral sliver at <i>m</i> &approx; 1.0, <i>K</i> &gt; 240 indicates dark pre-dawn only when night surcharges vanish."
        ),
    ),
    # Archived Supplementary Figures
    "fig1_conus_map_and_thermal_decoupling.png": (
        "Figure S1. Archived continental daily-extremes thermal decoupling across 397 screened U.S. stations (2005&ndash;2025).",
        "Spatial distribution of within-station daily <i>d</i>(DO<sub>min</sub> &minus; DO<sub>max</sub>)/<i>dT</i> (Year &times; Month FE + log(<i>Q</i>) + log(<i>Q</i>)<sup>2</sup>) and specification robustness including USACE NID dam-free subsamples.",
    ),
    "fig3_compound_heatwave_drought.png": (
        "Figure S2. Archived asymmetric daily-extremes collapse under compound heatwave &times; low-flow drought regimes (<i>N</i> = 319 stations).",
        "Comparison of daily DO<sub>min</sub>, DO<sub>mean</sub>, DO<sub>max</sub>, and solubility-adjusted deficits across Hot-Only, Dry-Only, and Compound Hot &times; Dry regimes with HUC-2 clustered 95% CIs.",
    ),
    "fig4_biophysical_mechanism.png": (
        "Figure S3. Archived split-half diurnal amplitude, specific conductance, turbidity, and latitude stratification.",
        "Out-of-sample split-half prediction of late-period daily decoupling from early-period baseline diurnal DO swing (<i>N</i> = 271 stations) and water-chemistry/climate strata.",
    ),
    "fig5_secular_cwa_and_uk_replication.png": (
        "Figure S4. Archived 20-year secular trend audit (2005&ndash;2025, <i>N</i> = 194 stations) and UK daily-extremes 24-hour excess slope comparison.",
        "Clean Water Act baseline confounding stratified by warming rate (panel A) and 24-hour excess temperature sensitivity across 65 screened English stations (panel B).",
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

    for macro, pre, post in [
        (r"\text{", '<span class="rm">', "</span>"),
        (r"\mathrm{", '<span class="rm">', "</span>"),
        (r"\mathcal{", '<span class="rm">', "</span>"),
        (r"\mathbf{", "<b>", "</b>"),
    ]:
        while macro in s:
            idx = s.index(macro)
            inner, end = _extract_braced(s, idx + len(macro) - 1)
            s = s[:idx] + f"{pre}{inner}{post}" + s[end:]

    replacements = [
        (r"{,}", ","),
        (r"^\circ", "&deg;"),
        (r"^{\circ}", "&deg;"),
        (r"\times", "&times;"),
        (r"\cdot", "&middot;"),
        (r"\pm", "&plusmn;"),
        (r"\le", "&le;"),
        (r"\ge", "&ge;"),
        (r"\neq", "&ne;"),
        (r"\approx", "&approx;"),
        (r"\to", "&rarr;"),
        (r"\rightarrow", "&rarr;"),
        (r"\in", "&isin;"),
        (r"\sigma", "&sigma;"),
        (r"\mu", "&mu;"),
        (r"\tau", "&tau;"),
        (r"\lambda", "&lambda;"),
        (r"\Delta", "&Delta;"),
        (r"\log", "log"),
        (r"\min", "min"),
        (r"\max", "max"),
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
    s = re.sub(r"_([A-Za-z0-9+\-]+|&[a-z]+;)", r"<sub>\1</sub>", s)
    s = re.sub(r"\^([A-Za-z0-9+\-*]+)", r"<sup>\1</sup>", s)
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

    # Unescape markdown literal \$ BEFORE math scanning so currency doesn't trigger inline math!
    text = text.replace(r"\$", "\x00DOLLAR\x00")
    text = re.sub(r"`([^`]+)`", lambda m: stash(f"<code>{html.escape(m.group(1))}</code>"), text)
    text = re.sub(r"\$([^$\n]+)\$", lambda m: stash(f'<span class="math">{_tex_to_html(m.group(1))}</span>'), text)
    escaped = html.escape(text).replace("\x00DOLLAR\x00", "$")
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


def convert_md_to_html(md_text: str, running_header: str, doc_title: str) -> str:
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
            if fname in FIGURE_BLOCKS and fname not in inserted_figs and (BASE_DIR / "figures" / fname).exists():
                body.append(_embed_figure_html(fname))
                inserted_figs.add(fname)
            i += 1
            continue
        if stripped == "---":
            body.append("<hr />")
            i += 1
            continue
        if stripped.startswith("$$") and stripped.endswith("$$") and len(stripped) > 4:
            body.append(f'<div class="eq-block">{_tex_to_html(stripped[2:-2].strip())}</div>')
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
            col_cls = [
                "center" if (a.startswith(":") and a.endswith(":")) else ("right" if a.endswith(":") else "left")
                for a in aligns
            ]
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
                items.append(f"<li>{_inline_md(item_txt)}</li>")
            start_attr = f' start="{start_num}"' if start_num != 1 else ""
            body.append(f"<ol{start_attr}>{''.join(items)}</ol>")
            continue

        para_lines = [stripped]
        i += 1
        while i < n:
            nxt = lines[i].strip()
            if not nxt or nxt == "---" or nxt.startswith(("#", "|", "- ", "$$", "<!--")) or re.match(r"^\d+\.\s+", nxt):
                break
            para_lines.append(nxt)
            i += 1
        # Preserve intentional Markdown line breaks (two trailing spaces) for author block
        joined = ""
        for idx_p, pl in enumerate(para_lines):
            if idx_p > 0:
                joined += "<br />" if lines[i - len(para_lines) + idx_p - 1].endswith("  ") else " "
            joined += _inline_md(pl)
        para_raw = " ".join(para_lines)
        p_cls = (
            ' class="table-caption"'
            if para_raw.startswith("**Table ")
            else (' class="table-notes"' if para_raw.startswith(("*Notes:*", "*Source:*")) else (' class="author-block"' if "UCSI University" in para_raw else ""))
        )
        body.append(f"<p{p_cls}>{joined}</p>")

    css = f"""
    @page {{
      size: letter;
      margin: 0.68in 0.68in 0.74in 0.68in;
      @top-right {{
        content: "{running_header}";
        font-family: Georgia, "Times New Roman", serif;
        font-size: 7.5pt;
        color: #555;
      }}
      @bottom-center {{
        content: "Page " counter(page) " of " counter(pages);
        font-family: Georgia, "Times New Roman", serif;
        font-size: 8pt;
        color: #555;
      }}
    }}
    @page :first {{ @top-right {{ content: normal; }} }}
    body {{
      font-family: Georgia, "Times New Roman", serif;
      font-size: 9.5pt;
      line-height: 1.43;
      color: #1a1a1a;
      max-width: 100%;
    }}
    h1.paper-title {{
      font-size: 15.2pt;
      line-height: 1.24;
      margin: 0 0 7pt 0;
      color: #0b2545;
      border-bottom: 1.5pt solid #0b2545;
      padding-bottom: 5pt;
    }}
    p.author-block {{
      font-size: 9.0pt;
      line-height: 1.38;
      color: #1e293b;
      text-align: left;
      margin: 0 0 8pt 0;
    }}
    h2 {{
      font-size: 11.4pt;
      color: #0b2545;
      margin: 12pt 0 5pt 0;
      border-bottom: 0.6pt solid #cbd5e1;
      padding-bottom: 2pt;
      page-break-after: avoid;
    }}
    h3 {{
      font-size: 9.9pt;
      color: #1e3a5f;
      margin: 9pt 0 4pt 0;
      page-break-after: avoid;
    }}
    p {{ margin: 0 0 5.6pt 0; text-align: justify; }}
    p.table-caption {{
      font-size: 8.8pt;
      margin: 9pt 0 4pt 0;
      color: #0b2545;
      text-align: left;
      page-break-after: avoid;
    }}
    p.table-notes {{
      font-size: 7.5pt;
      color: #475569;
      margin: 2pt 0 8pt 0;
      text-align: left;
    }}
    ul, ol {{ margin: 3pt 0 6.5pt 16pt; padding: 0; }}
    li {{ margin: 0 0 3.0pt 0; text-align: justify; }}
    code {{
      font-family: Consolas, "Courier New", monospace;
      font-size: 7.8pt;
      background: #f1f5f9;
      padding: 0.4pt 2.2pt;
      border-radius: 2pt;
    }}
    hr {{ border: 0; border-top: 0.6pt solid #cbd5e1; margin: 8pt 0; }}
    .math {{ font-family: "Cambria Math", Georgia, serif; font-style: italic; }}
    .math .rm, .eq-block .rm {{ font-style: normal; }}
    sup, sub {{ white-space: nowrap; }}
    .eq-block {{
      font-family: "Cambria Math", Georgia, serif;
      font-size: 9.5pt;
      text-align: center;
      margin: 7pt 0;
      padding: 6pt 10pt;
      background: #f8fafc;
      border-left: 2pt solid #0b2545;
    }}
    .table-wrap {{ margin: 4pt 0 4pt 0; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 7.2pt;
      line-height: 1.25;
      border-top: 1.3pt solid #0f172a;
      border-bottom: 1.3pt solid #0f172a;
    }}
    thead {{ display: table-header-group; }}
    tr {{ page-break-inside: avoid; }}
    thead tr {{ border-bottom: 0.8pt solid #334155; background: #f8fafc; }}
    th, td {{ padding: 2.6pt 3.5pt; vertical-align: top; }}
    td .math, th .math {{ white-space: nowrap; }}
    tbody tr:nth-child(even) {{ background: #fbfdff; }}
    th.left, td.left {{ text-align: left; }}
    th.center, td.center {{ text-align: center; }}
    th.right, td.right {{ text-align: right; }}
    figure.pub-fig {{
      margin: 9pt 0 9pt 0;
      padding: 6pt;
      border: 0.5pt solid #e2e8f0;
      background: #ffffff;
      page-break-inside: avoid;
      text-align: center;
    }}
    figure.pub-fig img {{
      max-width: 100%;
      max-height: 3.95in;
      height: auto;
      display: block;
      margin: 0 auto 5pt auto;
    }}
    figure.pub-fig figcaption {{
      font-size: 7.7pt;
      line-height: 1.32;
      color: #334155;
      text-align: left;
    }}
    """
    return (
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8' />"
        f"<title>{html.escape(doc_title)}</title><style>{css}</style></head>"
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
        r"DO_min",
        r"DO_max",
        r"DO_sat",
        r"fig[1-5]_[a-z0-9_]+\.png",
        r"Track\s+[AB]",
        r"Target\s+Journal",
        r"Target\s+Venue",
        r"16(?:\.0)?[×x]",
    ]
    leaks = [pat for pat in bad_patterns if re.search(pat, full_txt)]
    return len(reader.pages), leaks


def compile_one(md_path: Path, pdf_path: Path, running_header: str, doc_title: str) -> int:
    html_path = md_path.with_suffix(".html")
    md_text = md_path.read_text(encoding="utf-8")
    html_path.write_text(convert_md_to_html(md_text, running_header, doc_title), encoding="utf-8")

    with tempfile.TemporaryDirectory(prefix="edge_pdf_") as tmp_dir:
        cmd = [
            str(EDGE_EXE),
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--user-data-dir={tmp_dir}",
            f"--print-to-pdf={pdf_path}",
            html_path.as_uri(),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=90, check=False)
    html_path.unlink(missing_ok=True)
    if res.returncode != 0 or not pdf_path.exists() or pdf_path.stat().st_size < 50_000:
        print(f"[ERROR] Edge PDF compile failed for {pdf_path.name} rc={res.returncode}: {res.stderr}", file=sys.stderr)
        return 1

    n_pages, leaks = verify_pdf_zero_leaks(pdf_path)
    if leaks:
        print(f"[ERROR] Leaked tokens in {pdf_path.name}: {leaks}", file=sys.stderr)
        return 2
    print(f"[DONE] Compiled {pdf_path.name} ({pdf_path.stat().st_size:,} bytes, {n_pages} pages, 0 leaked tokens)", flush=True)
    return 0


def main() -> int:
    if not EDGE_EXE.exists():
        print(f"[ERROR] Microsoft Edge not found at {EDGE_EXE}", file=sys.stderr)
        return 1

    main_md = BASE_DIR / "manuscript_d4_boost.md"
    main_pdf = BASE_DIR / "manuscript_d4_boost.pdf"
    nw_pdf = BASE_DIR / "manuscript_d4_nature_water.pdf"
    rc = compile_one(
        main_md,
        main_pdf,
        "Equal-budget monitoring protocols for nocturnal river hypoxia",
        "Equal-budget monitoring protocols for nocturnal river hypoxia",
    )
    if rc != 0:
        return rc
    shutil.copy2(main_pdf, nw_pdf)
    print(f"[DONE] Synced Nature Water submission copy -> {nw_pdf.name}", flush=True)

    supp_md = BASE_DIR / "supplementary_d4_nature_water.md"
    supp_pdf = BASE_DIR / "supplementary_d4_nature_water.pdf"
    if supp_md.exists():
        rc_s = compile_one(
            supp_md,
            supp_pdf,
            "Supplementary Information — Nocturnal River Hypoxia Monitoring Protocols",
            "Supplementary Information — Nocturnal River Hypoxia Monitoring Protocols",
        )
        if rc_s != 0:
            return rc_s
    return 0


if __name__ == "__main__":
    sys.exit(main())
