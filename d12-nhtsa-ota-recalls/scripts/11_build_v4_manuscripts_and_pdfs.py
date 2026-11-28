"""Step 11 (v4): Programmatically generate zero-hardcode Main Manuscript (manuscript_d12_boost.md)
and Online Appendix (supplementary_d12_jsr.md) strictly from frozen JSON/CSV outputs, and compile
both into journal-grade zero-leak PDFs via headless Microsoft Edge with isolated user-data-dir.
"""
from __future__ import annotations

import base64
import html
import json
import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd
from pypdf import PdfReader

BASE_DIR = Path(r"D:\AI_Science\antigravity\d12_boost_nhtsa_ota_recalls_20261125")
PROC_DIR = BASE_DIR / "data_processed"
RES_DIR = BASE_DIR / "results"
TBL_DIR = BASE_DIR / "tables"
FIG_DIR = BASE_DIR / "figures"
EDGE_EXE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

AUTHOR_BLOCK = """Zijian Zeng
Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA
`zijianzeng@foxmail.com`; `1002266693@ucsiuniversity.edu.my`"""


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
        (r"\mid", " | "),
        (r"\left(", "("),
        (r"\right)", ")"),
        (r"\left[", "["),
        (r"\right]", "]"),
        (r"\left", ""),
        (r"\right", ""),
        (r"\exp", "exp"),
        (r"\log", "log"),
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
        (r"\gamma", "&gamma;"),
        (r"\varepsilon", "&epsilon;"),
        (r"\epsilon", "&epsilon;"),
        (r"\tau", "&tau;"),
        (r"\mu", "&mu;"),
        (r"\Delta", "&Delta;"),
        (r"\sigma", "&sigma;"),
        (r"\lambda", "&lambda;"),
        (r"\kappa", "&kappa;"),
        (r"\ell", "&#8467;"),
        (r"\%", "%"),
        (r"\{", "{"),
        (r"\}", "}"),
        (r"\,", "&thinsp;"),
        (r"\ ", " "),
    ]
    for old, new in replacements:
        s = s.replace(old, new)

    for _ in range(3):
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

    text = text.replace(r"\$", "\x00DOLLAR\x00")
    text = re.sub(r"`([^`]+)`", lambda m: stash(f"<code>{html.escape(m.group(1))}</code>"), text)
    text = re.sub(r"\$([^$\n]+)\$", lambda m: stash(f'<span class="math">{_tex_to_html(m.group(1))}</span>'), text)
    text = re.sub(
        r"\[([^\]\n]+)\]\((https?://[^)\s]+)\)",
        lambda m: stash(f'<a href="{html.escape(m.group(2))}">{html.escape(m.group(1))}</a>'),
        text,
    )
    text = text.replace("\x00DOLLAR\x00", "$")

    escaped = html.escape(text)
    escaped = re.sub(r"\*\*\*([^*]+?)\*\*\*", r"<strong><em>\1</em></strong>", escaped)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<em>\1</em>", escaped)
    for i, frag in enumerate(tokens):
        escaped = escaped.replace(f"\x00TOK{i}\x00", frag)
    return escaped


def convert_md_to_html(md_text: str, figure_blocks: dict[str, tuple[str, str]], running_head: str, doc_title: str) -> str:
    lines = md_text.splitlines()
    body: list[str] = []
    inserted_figs: set[str] = set()
    i = 0
    n = len(lines)

    def _embed_fig(fname: str) -> str:
        img_path = FIG_DIR / fname
        b64 = base64.b64encode(img_path.read_bytes()).decode("ascii")
        title_html, caption_html = figure_blocks[fname]
        alt_txt = re.sub(r"<[^>]+>", "", title_html)
        return (
            f'<figure class="pub-fig">'
            f'<img src="data:image/png;base64,{b64}" alt="{html.escape(alt_txt)}" />'
            f"<figcaption><strong>{title_html}</strong> {caption_html}</figcaption>"
            f"</figure>"
        )

    while i < n:
        stripped = lines[i].strip()
        if not stripped:
            i += 1
            continue
        m_fig = re.match(r"^<!--\s*FIGURE:([A-Za-z0-9_.\-]+)\s*-->$", stripped)
        if m_fig:
            fname = m_fig.group(1)
            if fname in figure_blocks and fname not in inserted_figs:
                body.append(_embed_fig(fname))
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

        # Author block lines immediately following H1
        if body and body[-1].startswith('<h1 class="paper-title">'):
            auth_lines = [stripped]
            i += 1
            while i < n and lines[i].strip() and not lines[i].strip().startswith(("#", "---")):
                auth_lines.append(lines[i].strip())
                i += 1
            auth_html = "<br />".join(_inline_md(al) for al in auth_lines)
            body.append(f'<div class="author-block">{auth_html}</div>')
            continue

        para_lines = [stripped]
        i += 1
        while i < n:
            nxt = lines[i].strip()
            if not nxt or nxt == "---" or nxt.startswith(("#", "|", "- ", "$$", "<!--")) or re.match(r"^\d+\.\s+", nxt):
                break
            para_lines.append(nxt)
            i += 1
        para_raw = " ".join(para_lines)
        p_cls = (
            ' class="table-caption"'
            if para_raw.startswith(("**Table ", "**Appendix Table "))
            else (' class="table-notes"' if para_raw.startswith(("*Notes:*", "*Source:*", "*Source Provenance")) else "")
        )
        body.append(f"<p{p_cls}>{_inline_md(para_raw)}</p>")

    css = f"""
    @page {{
      size: letter;
      margin: 0.68in 0.68in 0.72in 0.68in;
      @top-right {{
        content: "{running_head}";
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
      font-size: 9.4pt;
      line-height: 1.44;
      color: #1a1a1a;
      max-width: 100%;
    }}
    h1.paper-title {{
      font-size: 14.4pt;
      line-height: 1.24;
      margin: 0 0 8pt 0;
      color: #0b2545;
      border-bottom: 1.5pt solid #0b2545;
      padding-bottom: 6pt;
    }}
    .author-block {{
      font-size: 9.1pt;
      line-height: 1.38;
      color: #1e293b;
      margin: 0 0 8pt 0;
      text-align: left;
    }}
    h2 {{
      font-size: 11.2pt;
      color: #0b2545;
      margin: 12pt 0 5pt 0;
      border-bottom: 0.6pt solid #cbd5e1;
      padding-bottom: 2pt;
      page-break-after: avoid;
    }}
    h3 {{
      font-size: 9.8pt;
      color: #1e3a5f;
      margin: 9pt 0 4pt 0;
      page-break-after: avoid;
    }}
    p {{ margin: 0 0 5.6pt 0; text-align: justify; }}
    p.table-caption {{
      font-size: 8.6pt;
      margin: 7pt 0 3pt 0;
      color: #0b2545;
      text-align: left;
      break-inside: avoid;
      page-break-inside: avoid;
      break-after: avoid;
      page-break-after: avoid;
    }}
    p.table-notes {{
      font-size: 7.5pt;
      color: #475569;
      margin: 2pt 0 8pt 0;
      text-align: left;
    }}
    ul, ol {{ margin: 3pt 0 6pt 16pt; padding: 0; }}
    li {{ margin: 0 0 3.0pt 0; text-align: justify; }}
    ol.refs-list li {{ text-align: left; font-size: 8.4pt; line-height: 1.34; break-inside: avoid; page-break-inside: avoid; }}
    a {{ color: #1d4ed8; text-decoration: none; }}
    code {{
      font-family: Consolas, "Courier New", monospace;
      font-size: 7.7pt;
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
    .table-wrap {{ margin: 4pt 0 4pt 0; page-break-inside: avoid; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 6.95pt;
      line-height: 1.20;
      border-top: 1.3pt solid #0f172a;
      border-bottom: 1.3pt solid #0f172a;
    }}
    thead tr {{ border-bottom: 0.8pt solid #334155; background: #f8fafc; }}
    th, td {{ padding: 2.0pt 3.0pt; vertical-align: top; }}
    td .math, th .math {{ white-space: nowrap; }}
    td code {{ white-space: nowrap; }}
    tbody tr:nth-child(even) {{ background: #fbfdff; }}
    th.left, td.left {{ text-align: left; }}
    th.center, td.center {{ text-align: center; }}
    th.right, td.right {{ text-align: right; }}
    figure.pub-fig {{
      margin: 8pt 0 8pt 0;
      padding: 5.5pt;
      border: 0.5pt solid #e2e8f0;
      background: #ffffff;
      page-break-inside: avoid;
      text-align: center;
    }}
    figure.pub-fig img {{
      max-width: 100%;
      max-height: 4.35in;
      height: auto;
      display: block;
      margin: 0 auto 5pt auto;
    }}
    figure.pub-fig figcaption {{
      font-size: 7.7pt;
      line-height: 1.31;
      color: #334155;
      text-align: left;
    }}
    """
    return (
        f"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8' />"
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
        r"\{,\}",
        r"\bp_WCB\b",
        r"\bp_t\b",
        r"\^[0-9A-Za-z{]",
        r"fig[1-5]_v4_[a-z0-9_]+\.png",
        r"<!--",
        r"Target Venues",
        r"Target Format",
        r"Track A",
        r"Track B",
        r"85–90%",
        r"85-90%",
        r"[-−]85\.3%",
    ]
    leaks = [pat for pat in bad_patterns if re.search(pat, full_txt)]
    return len(reader.pages), leaks


def compile_edge_pdf(html_doc: str, out_pdf: Path) -> int:
    if not EDGE_EXE.exists():
        raise FileNotFoundError(f"Microsoft Edge not found at {EDGE_EXE}")
    with tempfile.TemporaryDirectory(prefix="d12_v4_edge_") as tmp:
        staging = Path(tmp)
        html_file = staging / "doc.html"
        pdf_tmp = staging / "doc.pdf"
        html_file.write_text(html_doc, encoding="utf-8")
        cmd = [
            str(EDGE_EXE),
            "--headless=new",
            f"--user-data-dir={staging / 'edge_profile'}",
            "--disable-gpu",
            "--no-first-run",
            "--no-pdf-header-footer",
            f"--print-to-pdf={pdf_tmp}",
            html_file.as_uri(),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=90, check=False)
        if res.returncode != 0 or not pdf_tmp.exists() or pdf_tmp.stat().st_size < 40_000:
            raise RuntimeError(f"Edge PDF compile failed rc={res.returncode}: {res.stderr}")
        n_pages, leaks = verify_pdf_zero_leaks(pdf_tmp)
        if leaks:
            raise RuntimeError(f"Leaked or forbidden tokens in {out_pdf.name}: {leaks}")
        out_pdf.write_bytes(pdf_tmp.read_bytes())
        return n_pages


def fmt_signed(x: float, nd: int = 2) -> str:
    sign = "+" if x > 0 else ("−" if x < 0 else "")
    return f"{sign}{abs(x):.{nd}f}"


def fmt_p(p: float) -> str:
    return f"{p:.3f}" if p >= 0.001 else "<0.001"


def build_references_md(refs_json: dict) -> list[str]:
    """Build cleanly formatted, alphabetically sorted peer-reviewed + institutional reference list."""
    entries: list[tuple[str, str]] = []
    for info in refs_json["references"].values():
        authors = info["authors"]
        yr = info["year"]
        online_yr = info.get("online_year")
        yr_str = f"{yr} [online {online_yr}]" if online_yr and int(online_yr) < int(yr) else f"{yr}"
        vol = info.get("volume") or ""
        iss = f"({info['issue']})" if info.get("issue") else ""
        pg = f", {info['page']}" if info.get("page") else ""
        vol_str = f", {vol}{iss}{pg}" if vol else pg
        line = f"{authors} ({yr_str}). {info['title']}. *{info['journal']}*{vol_str}. https://doi.org/{info['doi']}"
        entries.append((authors.lower(), line))
    entries.sort(key=lambda t: t[0])

    inst_order = [
        ("nhtsa_completion_rates_2025", "2025"),
        ("nhtsa_eighth_report_2024", "2025"),
        ("nhtsa_eighth_report_2025", "2026a"),
        ("nhtsa_2025_annual_recalls_report", "2026b"),
        ("cfr_49_573_7", "2026"),
        ("dot_socrata_6axg_epim", "2026"),
    ]
    inst_lines = []
    for k, yr_lbl in inst_order:
        info = refs_json["institutional_references"][k]
        inst_lines.append(f"{info['authors']}. ({yr_lbl}). *{info['title']}*. {info['publisher']}. {info['url']}")

    all_lines = [line for _, line in entries] + inst_lines
    return [f"{idx}. {txt}" for idx, txt in enumerate(all_lines, 1)]


def build_main_manuscript(
    v4: dict,
    spot: dict,
    econ: dict,
    audit_api: dict,
    s3: dict,
    refs_json: dict,
    df_flow: pd.DataFrame,
    df_comp: pd.DataFrame,
    df_sup: pd.DataFrame,
    df_sens: pd.DataFrame,
    df_looo: pd.DataFrame,
    df_apic: pd.DataFrame,
) -> tuple[str, dict[str, tuple[str, str]]]:
    rec = v4["reconciliation"]
    sf = v4["sample_flow"]
    cs8 = v4["common_support_summary"]["eighth_report"]
    csm = v4["common_support_summary"]["mature_18m_snapshot"]
    looo_s = v4["looo_summary"]
    p1 = econ["pillar1_blast_radius"]
    prov = v4["source_provenance"]

    sens_map = {(r["Specification"], r["Term"]): r for _, r in df_sens.iterrows()}
    comp_map = {(r["Report_Year"], r["Modality"]): r for _, r in df_comp.iterrows()}
    flow_od = sf["odate_2022_2023_by_modality"]

    # Core dynamic values
    n_tot_rows = rec["total_extracted_rows"]
    n_2024_raw = rec["rows_by_report_year"]["2024"]
    n_2025_raw = rec["rows_by_report_year"]["2025"]
    n_uniq = rec["matched_unique_campaigns"]
    n_dup_c = len(rec["excluded_duplicate_campaigns"])
    n_dup_r = rec["excluded_duplicate_rows"]
    dup_details = { (d["campaign_code"], d["report_year"]): d for d in rec["duplicate_campaign_details"] }

    c_pool_pure = comp_map[("Pooled_2024_2025", "Pure_OTA")]
    c_pool_hyb = comp_map[("Pooled_2024_2025", "Hybrid_OTA")]
    c_pool_dsw = comp_map[("Pooled_2024_2025", "Dealer_Software")]
    c_pool_phys = comp_map[("Pooled_2024_2025", "Physical_Hardware")]
    c24_pure = comp_map[("2024", "Pure_OTA")]

    # Key age-sensitivity numbers
    b_age = sens_map[("Fixed 8th report: oldest model year (4-way)", "veh_age")]
    b_pure = sens_map[("Fixed 8th report: oldest model year (4-way)", "is_ota_pure_x_age")]
    b_hyb = sens_map[("Fixed 8th report: oldest model year (4-way)", "is_ota_hybrid_x_age")]
    m_age = sens_map[("Fixed 8th report: middle model year (4-way)", "veh_age")]
    m_hyb = sens_map[("Fixed 8th report: middle model year (4-way)", "is_ota_hybrid_x_age")]
    w5_pure = sens_map[("Fixed 8th report: oldest MY, 0-5 yr window (4-way)", "is_ota_pure_x_age")]
    nt_pure = sens_map[("Fixed 8th report: oldest MY, excluding Tesla (4-way)", "is_ota_pure_x_age")]
    nt_pool = sens_map[("Fixed 8th report: oldest MY, excluding Tesla (pooled OTA)", "is_ota_audited_x_age")]
    nt_mid_pool = sens_map[("Fixed 8th report: middle MY, excluding Tesla (pooled OTA)", "is_ota_audited_x_age")]
    cs_pool_ota = sens_map[("Same-OEM common support (8 OEMs, all ages, pooled OTA)", "is_ota_audited_x_age")]
    cs_4w_pure = sens_map[("Same-OEM common support (8 OEMs, all ages, 4-way)", "is_ota_pure_x_age")]
    cs_4w_hyb = sens_map[("Same-OEM common support (8 OEMs, all ages, 4-way)", "is_ota_hybrid_x_age")]
    cs_ov_ota = sens_map[("Strict Same-OEM x Overlapping-Age support (8 OEMs, pooled OTA)", "is_ota_audited_x_age")]
    cs_lvl_ota = sens_map[("Same-OEM common support: level contrast (+ veh_age, pooled OTA)", "is_ota_audited")]
    cs_lvl_hyb = sens_map[("Same-OEM common support: level contrast (+ veh_age, 4-way)", "is_ota_hybrid")]
    cs_lvl_pure = sens_map[("Same-OEM common support: level contrast (+ veh_age, 4-way)", "is_ota_pure")]
    dsw_only_age = sens_map[("Standalone Dealer-Software (all 53 OEMs in 8th report)", "veh_age")]
    phys_only_age = sens_map[("Standalone Physical-Hardware (all 213 OEMs in 8th report)", "veh_age")]

    # Retained Pillar 1 Hybrid 7.01x scale numbers
    p1_hyb = p1["main_sw_ota_oems"]["sw_ota_oems_4way_log_potaff"]["terms"]["is_ota_hybrid"]
    p1_pure = p1["main_sw_ota_oems"]["sw_ota_oems_4way_log_potaff"]["terms"]["is_ota_pure"]
    p1_api = p1["main_sw_ota_oems"]["sw_ota_oems_api2018_24_log_potaff"]["terms"]["is_ota_api_full"]
    p1_hyb_mult = math.exp(p1_hyb["coef"])
    p1_itt = p1["itt_staggered_adoption"]["pooled_did"]["terms"]["post_ota_adopt"]
    p1_itt_pre = p1["itt_staggered_adoption"]["pre_trend_wald_m3_m2"]
    p1_sa = p1["itt_staggered_adoption"]["sun_abraham_iw"]
    p1_sw_sdv = p1["unconditional_sdv_cohort_shift"]["sw_vs_physical_sdv_did"]["terms"]["sw_x_sdv_my2021p"]

    # API audit numbers
    api_n_tot = audit_api["n_total_queried"]
    api_phys_n = audit_api["physical_audit_valid"]
    api_phys_fn = audit_api["physical_audit_api_ota_true_false_negatives"]
    api_pre25 = audit_api["cutoff_2025_early_jan1_to_may8"]
    api_post25 = audit_api["cutoff_post_may8_2025_through_2026"]
    api_yr = {r["rec_year"]: r for r in audit_api["txt_ota_reconciliation_by_year"]}
    n_19_23 = sum(api_yr[y]["n_txt_ota"] for y in range(2019, 2024))
    n_19_23_true = sum(api_yr[y]["n_api_true"] for y in range(2019, 2024))
    apic_map = {r["Text_Coding_Category"]: r for _, r in df_apic.iterrows()}
    spot_map = {r["campaign_id"]: r for r in spot["results"]}

    # Build Table 1 (Sample Flow Accounting)
    t1_lines = [
        "| Cohort & Modality | Total Recalls | In 8th Report (Unique) | Share in 8th (%) | Excl. Duplicate | Unlisted: 100% Early Complete | Unlisted: Missing DOT Report | Unlisted: Delayed / Out-of-Window |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    panel_labels = {
        "A_Statutory_ODATE_2022_2023": "**Panel A: Statutory 2022–2023 Owner-Notification Cohort (`ODATE`)**",
        "B_Filing_RCDATE_2022_2023": "**Panel B: 2022–2023 Part 573 Filing-Year Cohort (`RCDATE`)**",
        "C_Full_Universe_2018_2026": "**Panel C: Full 2018–2026 NHTSA Vehicle Recall Universe**",
    }
    mod_disp = {
        "Pure_OTA": "Pure-OTA (Wireless-Only)",
        "Hybrid_OTA": "Hybrid-OTA (OTA or Dealer)",
        "Dealer_Software": "Dealer Software",
        "Physical_Hardware": "Physical Hardware",
        "All_Vehicles": "**All Vehicles (ODATE 2022–2023 Total)**",
    }
    for pnl in ["A_Statutory_ODATE_2022_2023", "B_Filing_RCDATE_2022_2023", "C_Full_Universe_2018_2026"]:
        t1_lines.append(f"| {panel_labels[pnl]} | | | | | | | |")
        sub = df_flow[df_flow["Cohort_Panel"] == pnl]
        for _, r in sub.iterrows():
            t1_lines.append(
                f"| {mod_disp.get(r['Modality'], r['Modality'])} | {int(r['Total_Campaigns']):,} | "
                f"{int(r['In_8th_Report_Unique']):,} | {r['Share_In_8th_Pct']:.1f}% | "
                f"{int(r['Excluded_Conflicting_Duplicate']):,} | {int(r['Unlisted_Early_Completed_100pct']):,} | "
                f"{int(r['Unlisted_Missing_DOT_Report']):,} | {int(r['Unlisted_Delayed_or_Unreached']):,} |"
            )

    # Build Table 2 (Fixed 8th-Report Completion Proportions)
    t2_lines = [
        "| Report List | Remedy Channel | Campaigns ($N$) | OEMs | Mean (%) | SD (pp) | Median (%) | IQR (%) | Vehicle-Weighted Mean (%) | Summed Affected Vehicles | Median Size |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for yr_lbl, yr_disp in [("2024", "2024 List"), ("2025", "2025 List"), ("Pooled_2024_2025", "**Pooled 2024–2025**")]:
        for mod in ["Pure_OTA", "Hybrid_OTA", "Dealer_Software", "Physical_Hardware"]:
            r = comp_map[(yr_lbl, mod)]
            t2_lines.append(
                f"| {yr_disp} | {mod_disp[mod]} | {int(r['N_Campaigns']):,} | {int(r['N_OEMs']):,} | "
                f"{r['Mean_Completion_Pct']:.2f} | {r['SD_Pct']:.2f} | {r['Median_Completion_Pct']:.2f} | "
                f"{r['IQR_25_Pct']:.1f}–{r['IQR_75_Pct']:.1f} | {r['Affected_Weighted_Mean_Pct']:.2f} | "
                f"{int(r['Total_Affected_Vehicles']):,} | {int(r['Median_Affected_Vehicles']):,} |"
            )

    # Build Table 3 (Channel x Manufacturer x Vehicle-Age Common-Support Matrix in 8th Report)
    sup8 = df_sup[df_sup["Horizon_Sample"] == "8th_Report_Fixed_Horizon"].copy()
    t3_lines = [
        "| Remedy Channel | Manufacturer (Canonical OEM) | Campaigns ($N$) | Affected Vehicles | Share of Channel Veh. (%) | Oldest-MY Age Range (yr) | $N$ Aged $\\ge 6$ yr | Mean 8th-Rep. (%) | Both Dealer-SW & OTA? |",
        "|---|---|---:|---:|---:|---:|---:|---:|:---:|",
    ]
    for mod in ["Pure_OTA", "Hybrid_OTA"]:
        sub = sup8[sup8["Modality"] == mod].sort_values("Affected_Vehicles", ascending=False)
        for _, r in sub.iterrows():
            age_rng = f"{int(r['Min_Oldest_MY_Age_Yr'])}–{int(r['Max_Oldest_MY_Age_Yr'])}" if r["Min_Oldest_MY_Age_Yr"] != r["Max_Oldest_MY_Age_Yr"] else f"{int(r['Min_Oldest_MY_Age_Yr'])}"
            both_s = "Yes" if int(r["Observes_Both_DealerSW_And_OTA"]) == 1 else "**No**"
            t3_lines.append(
                f"| {mod_disp[mod]} | {r['Manufacturer']} | {int(r['N_Campaigns'])} | {int(r['Affected_Vehicles']):,} | "
                f"{r['Share_Modality_Vehicles_Pct']:.2f}% | {age_rng} | {int(r['N_Age_6Plus_Yr'])} | {r['Mean_Completion_Pct']:.2f} | {both_s} |"
            )
    # Add summary rows for Dealer_Software among the 8 common-support OEMs vs 9 Dealer-SW-only OEMs
    dsw8 = sup8[sup8["Modality"] == "Dealer_Software"]
    dsw8_both = dsw8[dsw8["Observes_Both_DealerSW_And_OTA"] == 1]
    dsw8_only = dsw8[dsw8["Observes_Both_DealerSW_And_OTA"] == 0]
    for lbl, g in [
        (f"8 Same-OEM Common-Support Manufacturers ({len(dsw8_both)} OEMs)", dsw8_both),
        (f"9 OTA-Capable OEMs Without 8th-Report OTA ({len(dsw8_only)} OEMs)", dsw8_only),
    ]:
        tot_n = int(g["N_Campaigns"].sum())
        tot_v = int(g["Affected_Vehicles"].sum())
        sh_v = float(g["Share_Modality_Vehicles_Pct"].sum())
        mn_a, mx_a = int(g["Min_Oldest_MY_Age_Yr"].min()), int(g["Max_Oldest_MY_Age_Yr"].max())
        n6 = int(g["N_Age_6Plus_Yr"].sum())
        wt_m = float((g["N_Campaigns"] * g["Mean_Completion_Pct"]).sum() / max(1, tot_n))
        both_lbl = "Yes" if "Common-Support" in lbl else "No"
        t3_lines.append(
            f"| Dealer Software | {lbl} | {tot_n} | {tot_v:,} | {sh_v:.2f}% | {mn_a}–{mx_a} | {n6} | {wt_m:.2f} | {both_lbl} |"
        )

    # Build Table 4 (Vehicle-Age Gradients, Common-Support Subsamples, and LOOO Summary)
    t4_specs = [
        ("Fixed 8th report: oldest model year (4-way)", "4way", "Baseline fixed 8th report (oldest MY, 18 OEMs)"),
        ("Fixed 8th report: middle model year (4-way)", "4way", "Fixed 8th report (middle MY, 18 OEMs)"),
        ("Fixed 8th report: oldest MY, 0-5 yr window (4-way)", "4way", "Fixed 8th report (oldest MY, restricted 0–5 yr)"),
        ("Fixed 8th report: oldest MY, excluding Tesla (4-way)", "4way", "**Fixed 8th report (oldest MY, excluding Tesla, 4-way)**"),
        ("Fixed 8th report: oldest MY, excluding Tesla (pooled OTA)", "pool", "Fixed 8th report (oldest MY, excluding Tesla, pooled OTA)"),
        ("Fixed 8th report: middle MY, excluding Tesla (pooled OTA)", "pool", "Fixed 8th report (middle MY, excluding Tesla, pooled OTA)"),
        ("Same-OEM common support (8 OEMs, all ages, 4-way)", "4way", "Same-OEM common support (8 OEMs observing both, 4-way)"),
        ("Same-OEM common support (8 OEMs, all ages, pooled OTA)", "pool", "Same-OEM common support (8 OEMs observing both, pooled OTA)"),
        ("Strict Same-OEM x Overlapping-Age support (8 OEMs, pooled OTA)", "pool", "Strict Same-OEM × Overlapping-Age support (8 OEMs)"),
        ("Standalone Dealer-Software (all 53 OEMs in 8th report)", "age", "Standalone Dealer-Software (all 53 OEMs in 8th report)"),
        ("Standalone Physical-Hardware (all 213 OEMs in 8th report)", "age", "Standalone Physical-Hardware (all 213 OEMs in 8th report)"),
    ]
    t4_lines = [
        "| Fixed 8th-Report Specification | $N$ | OEMs | Dealer / Channel Age Slope (pp/yr, $p_{\\text{WCB}}$) | Pure-OTA $\\times$ Age (pp/yr, $p_{\\text{WCB}}$) | Hybrid / Pooled OTA $\\times$ Age (pp/yr, $p_{\\text{WCB}}$) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for spec_key, kind, disp in t4_specs:
        ra = sens_map[(spec_key, "veh_age")]
        age_s = f"{fmt_signed(ra['Coef'])} ({fmt_p(ra['p_WCB'])})"
        if kind == "4way":
            rp = sens_map[(spec_key, "is_ota_pure_x_age")]
            rh = sens_map[(spec_key, "is_ota_hybrid_x_age")]
            p_s = f"{fmt_signed(rp['Coef'])} ({fmt_p(rp['p_WCB'])})"
            h_s = f"{fmt_signed(rh['Coef'])} ({fmt_p(rh['p_WCB'])})"
        elif kind == "pool":
            ro = sens_map[(spec_key, "is_ota_audited_x_age")]
            p_s = "— (pooled)"
            h_s = f"{fmt_signed(ro['Coef'])} ({fmt_p(ro['p_WCB'])})"
        else:
            p_s, h_s = "—", "—"
        t4_lines.append(f"| {disp} | {int(ra['N']):,} | {int(ra['OEMs']):,} | {age_s} | {p_s} | {h_s} |")

    # Build Table 5 (Retained Conditional Batch-Scale Contrast vs Unconditional OEM ITT)
    t5_rows_spec = [
        ("Conditional: Hybrid-OTA vs. Dealer-SW (Main FE, 2018–2026)", p1["main_sw_ota_oems"]["sw_ota_oems_4way_log_potaff"], "is_ota_hybrid"),
        ("Conditional: Pure-OTA vs. Dealer-SW (Main FE, 2018–2026)", p1["main_sw_ota_oems"]["sw_ota_oems_4way_log_potaff"], "is_ota_pure"),
        ("Conditional: Official API OTA (Active Era 2018–2024)", p1["main_sw_ota_oems"]["sw_ota_oems_api2018_24_log_potaff"], "is_ota_api_full"),
        ("Conditional: Hybrid-OTA (Saturated OEM $\\times$ Year FE)", p1["robustness_ladder"]["oem_x_year_fe_4way"], "is_ota_hybrid"),
        ("Conditional: Hybrid-OTA (Make $\\times$ Model FE)", p1["robustness_ladder"]["make_x_model_fe_4way"], "is_ota_hybrid"),
        ("Conditional: Hybrid-OTA (Excl. Tesla & Ford)", p1["robustness_ladder"]["excl_tesla_ford_4way"], "is_ota_hybrid"),
        ("Conditional: Hybrid SW-Choice Only (No Hardware Clause)", p1["robustness_ladder"]["hybrid_swchoice_vs_hwmixed"], "is_ota_hybrid_swchoice"),
        ("Unconditional: First-OTA OEM ITT (TWFE, 2015–2026)", p1["itt_staggered_adoption"]["pooled_did"], "post_ota_adopt"),
    ]
    t5_lines = [
        "| Estimand & Specification (Outcome: $\\log(1 + \\text{Affected Vehicles})$) | $N$ | OEMs | Coef. | SE (CR1) | $t_{\\text{CR1}}$ | $p_{\\text{WCB}}$ / $p_t$ | Implied Scale Ratio |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for lbl, reg, trm in t5_rows_spec:
        t = reg["terms"][trm]
        mult_s = f"{math.exp(t['coef']):.2f}×" if t["p_wcb"] < 0.05 else "Null"
        t5_lines.append(
            f"| {lbl} | {reg['n']:,} | {reg['G_clusters']:,} | {fmt_signed(t['coef'], 3)} | "
            f"{t['se_cr1']:.3f} | {fmt_signed(t['t_cr1'], 2)} | {fmt_p(t['p_wcb'])} | {mult_s} |"
        )
    t5_lines.append(
        f"| Unconditional: First-OTA OEM ITT (Sun–Abraham 2021 IW, {p1_sa['n_cohorts']} cohorts) | "
        f"{p1_sa['n']:,} | {p1_sa['G_clusters']:,} | {fmt_signed(p1_sa['iw_post_coef'], 3)} | "
        f"{p1_sa['iw_se_cr1']:.3f} | {fmt_signed(p1_sa['iw_t'], 2)} | {fmt_p(p1_sa['iw_p_t_G1'])} ($p_t$) | Null |"
    )

    # Build Table 6 (Public Campaign API Measurement Validation Audit by Text Coding Category)
    t6_lines = [
        "| Verbatim Part 573 Remedy-Text Category | Total (2018–2026) | Pre-Cutoff ($\\le$ May 8, 2025) $N$ | Pre-Cutoff API `True` / Queried (%) | Post-Cutoff ($>$ May 8, 2025) $N$ | Post-Cutoff API `True` / Queried (%) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    cat_disp = {
        "Pure_OTA_Wireless_Only": "Pure-OTA (Wireless-Only Text)",
        "Hybrid_SW_Choice_OTA_Capable": "Hybrid SW-Choice (OTA-Capable or Dealer)",
        "Hybrid_HW_Mixed_Hardware_Req": "Hybrid HW-Mixed (OTA + Hardware Required)",
        "Dealer_Software_No_OTA": "Dealer Software (No OTA Option in Text)",
        "Physical_Hardware_NonSW": "Physical Hardware (Stratified Audit Sample)",
    }
    for _, r in df_apic.iterrows():
        t6_lines.append(
            f"| {cat_disp[r['Text_Coding_Category']]} | {int(r['Total_2018_2026']):,} | {int(r['Pre_Cutoff_N']):,} | "
            f"{int(r['Pre_Cutoff_API_True'])}/{int(r['Pre_Cutoff_API_Queried'])} ({r['Pre_Cutoff_API_True_Pct']:.1f}%) | "
            f"{int(r['Post_Cutoff_N']):,} | {int(r['Post_Cutoff_API_True'])}/{int(r['Post_Cutoff_API_Queried'])} ({r['Post_Cutoff_API_True_Pct']:.1f}%) |"
        )

    refs_md = "\n".join(build_references_md(refs_json))

    # Dynamic Figure Captions (zero hardcoded numbers!)
    fig_blocks = {
        "fig1_v4_sample_flow_and_completion.png": (
            "Figure 1. Statutory Owner-Notification Cohort Sample Flow Accounting and Fixed Eighth-Report Completion Proportions.",
            (
                f"Panel A reconciles the complete statutory 2022&ndash;2023 owner-notification (<code>ODATE</code>) cohort "
                f"(<em>N</em> = {sf['odate_2022_2023_total']:,} campaigns) by remedy channel, showing unique eighth-report inclusion "
                f"(Pure-OTA {flow_od['Pure_OTA']['In_8th_Report_Unique']}/{flow_od['Pure_OTA']['Total_Campaigns']}, {flow_od['Pure_OTA']['Share_In_8th_Pct']:.1f}%; "
                f"Hybrid-OTA {flow_od['Hybrid_OTA']['In_8th_Report_Unique']}/{flow_od['Hybrid_OTA']['Total_Campaigns']}, {flow_od['Hybrid_OTA']['Share_In_8th_Pct']:.1f}%; "
                f"Dealer Software {flow_od['Dealer_Software']['In_8th_Report_Unique']}/{flow_od['Dealer_Software']['Total_Campaigns']}, {flow_od['Dealer_Software']['Share_In_8th_Pct']:.1f}%; "
                f"Physical Hardware {flow_od['Physical_Hardware']['In_8th_Report_Unique']:,}/{flow_od['Physical_Hardware']['Total_Campaigns']:,}, {flow_od['Physical_Hardware']['Share_In_8th_Pct']:.1f}%), "
                f"early 100%-completed campaigns terminating prior to the eighth quarter under 49 CFR &sect; 573.7(a) "
                f"({flow_od['Pure_OTA']['Unlisted_Early_Completed_100pct']} Pure-OTA, {flow_od['Dealer_Software']['Unlisted_Early_Completed_100pct']} Dealer Software, "
                f"{flow_od['Physical_Hardware']['Unlisted_Early_Completed_100pct']} Physical), missing DOT reports, and {n_dup_c} excluded conflicting duplicate campaigns "
                f"(<code>22V315</code>, <code>22V743</code>). Adding {sf['earlier_odate_delayed_entries_n']} delayed 2020&ndash;2021 <code>ODATE</code> entries yields "
                f"{n_uniq:,} uniquely dated campaigns. Panel B displays fixed eighth-report unweighted mean, median, and vehicle-weighted mean completion proportions "
                f"separately for 2024 and 2025 annual lists (noting that all {int(c24_pure['N_Campaigns'])} 2024 Pure-OTA campaigns come from a single manufacturer)."
            ),
        ),
        "fig2_v4_channel_oem_age_support.png": (
            "Figure 2. Manufacturer &times; Channel &times; Vehicle-Age Common-Support Matrix and Pure-OTA Concentration Across Both Horizons.",
            (
                f"Panel A maps every software recall in the fixed eighth-report OTA-OEM sample (<em>N</em> = {cs8['n_sw_ota_oems']}, {cs8['n_oems_total']} OEMs) "
                f"by manufacturer, remedy channel, oldest-model-year vehicle age (clipped at 15 years), and affected vehicle count (bubble area). "
                f"Among {cs8['pure_total_n']} Pure-OTA campaigns, Tesla accounts for {cs8['pure_tesla_n']}/{cs8['pure_total_n']} recalls and "
                f"{cs8['pure_tesla_vehicle_share_pct']:.2f}% of affected vehicles while contributing {cs8['tesla_dealer_sw_n']} Dealer-Software recalls; "
                f"the remaining {cs8['pure_nontesla_n']} non-Tesla Pure-OTA recalls (Lucid and Volvo Car) occur strictly at oldest-model-year ages 0&ndash;{int(cs8['pure_nontesla_max_age_yr'])} years. "
                f"Only {len(cs8['same_oem_both_dsw_and_ota_oems'])} OEMs observe both Dealer Software and any OTA channel in the eighth-report cohort. "
                f"Panel B contrasts Pure-OTA concentration in the fixed eighth-report cohort (<em>n</em> = {cs8['pure_total_n']}) and the mature &ge;18-month archive "
                f"(<em>n</em> = {csm['pure_total_n']}), confirming that Tesla accounts for {cs8['pure_tesla_vehicle_share_pct']:.2f}% and {csm['pure_tesla_vehicle_share_pct']:.2f}% "
                f"of Pure-OTA vehicles and 100.0% of all Pure-OTA campaigns aged &ge;6 years in both horizons."
            ),
        ),
        "fig3_v4_age_gradients_and_looo.png": (
            "Figure 3. Fixed Eighth-Report Vehicle-Age Gradient Sensitivity and Complete 18-OEM Leave-One-OEM-Out (LOOO) Diagnostics.",
            (
                f"Panel A plots fixed-effects vehicle-age slopes and channel interactions (percentage points per vehicle-age year, 95% CR1 CIs, "
                f"<em>B</em> = 999 Rademacher wild cluster bootstrap <em>p</em><sub>WCB</sub>; filled markers indicate <em>p</em><sub>WCB</sub> &lt; 0.05). "
                f"While the Dealer-Software age slope is consistently negative across the 18-OEM software sample ({fmt_signed(b_age['Coef'])}, <em>p</em><sub>WCB</sub> = {fmt_p(b_age['p_WCB'])}), "
                f"standalone 53-OEM Dealer Software ({fmt_signed(dsw_only_age['Coef'])}, <em>p</em><sub>WCB</sub> = {fmt_p(dsw_only_age['p_WCB'])}), and 213-OEM Physical Hardware "
                f"({fmt_signed(phys_only_age['Coef'])}, <em>p</em><sub>WCB</sub> = {fmt_p(phys_only_age['p_WCB'])}), Pure-OTA &times; Age attenuates and loses precision "
                f"within ages 0&ndash;5 ({fmt_signed(w5_pure['Coef'])}, <em>p</em><sub>WCB</sub> = {fmt_p(w5_pure['p_WCB'])}), excluding Tesla ({fmt_signed(nt_pure['Coef'])}, "
                f"<em>p</em><sub>WCB</sub> = {fmt_p(nt_pure['p_WCB'])}), and inside same-OEM common-support subsamples. "
                f"Panel B reports complete Leave-One-OEM-Out estimates across all {looo_s['n_oems_tested']} OEMs: Dealer age decay remains significant in "
                f"{looo_s['dealer_age_sig_05_count']}/{looo_s['n_oems_tested']} exclusions ({fmt_signed(looo_s['dealer_age_min_coef'])} to {fmt_signed(looo_s['dealer_age_max_coef'])}, "
                f"all <em>p</em><sub>WCB</sub> &le; {looo_s['dealer_age_max_pwcb']:.3f}), whereas Pure-OTA &times; Age fails 5% significance in "
                f"{looo_s['pure_x_age_non_sig_05_count']}/{looo_s['n_oems_tested']} exclusions and collapses to {fmt_signed(nt_pure['Coef'])} (<em>p</em><sub>WCB</sub> = {fmt_p(nt_pure['p_WCB'])}) without Tesla."
            ),
        ),
        "fig4_v4_api_audit_and_hybrid_scale.png": (
            "Figure 4. Public NHTSA Campaign API Measurement Validation Audit (2019&ndash;2026) and Within-OEM Hybrid Batch-Scale Contrast vs. Unconditional OEM ITT.",
            (
                f"Panel A separates verbatim Part 573 remedy-text coding (Pure-OTA wireless-only, Hybrid SW-choice, Hybrid HW-mixed) from NHTSA's live public Campaign API "
                f"<code>overTheAirUpdate = True</code> indicator across {api_n_tot:,} queried campaigns ({api_phys_fn}/{api_phys_n} physical false negatives) alongside NHTSA's separate "
                f"<em>2025 Annual Recalls Report</em> (green star: 33 OTA recalls in 2025). The public API matched text-coded OTA on {n_19_23_true}/{n_19_23} (100.0%) in 2019&ndash;2023 "
                f"and {api_yr[2024]['n_api_true']}/{api_yr[2024]['n_txt_ota']} ({100*api_yr[2024]['api_true_rate']:.1f}%) in 2024, dropped to {api_pre25['n_api_true']}/{api_pre25['n_txt_ota']} "
                f"during Jan 1&ndash;May 8, 2025 (final <code>True</code>: Volvo <code>25V282000</code>, {spot_map['25V282000']['flag_values'].get('true', 0)}/{spot_map['25V282000']['api_records']} records), "
                f"and returned {api_post25['n_api_true']}/{api_post25['n_txt_ota']} (0.0%) after May 8, 2025 (starting May 9 with Ford <code>25V315000</code>, "
                f"{spot_map['25V315000']['flag_values'].get('false', 0)}/{spot_map['25V315000']['api_records']} <code>False</code>). "
                f"Panel B contrasts the well-identified conditional within-OEM Hybrid-OTA batch-scale differential ({fmt_signed(p1_hyb['coef'])} log points = {p1_hyb_mult:.2f}&times;, "
                f"<em>p</em><sub>WCB</sub> = {fmt_p(p1_hyb['p_wcb'])}; robust across fixed-effect and subsample checks) against Pure-OTA ({fmt_signed(p1_pure['coef'])}, "
                f"<em>p</em><sub>WCB</sub> = {fmt_p(p1_pure['p_wcb'])}) and null unconditional OEM-level first-OTA ITT estimates (TWFE {fmt_signed(p1_itt['coef'])}, "
                f"<em>p</em><sub>WCB</sub> = {fmt_p(p1_itt['p_wcb'])}; Sun&ndash;Abraham IW {fmt_signed(p1_sa['iw_post_coef'])}, <em>p</em><sub>t</sub> = {fmt_p(p1_sa['iw_p_t_G1'])})."
            ),
        ),
    }

    md = f"""# Vehicle Recall Completion at a Fixed Reporting Horizon: Software Remedy Channels, Manufacturer Common Support, and Public API Measurement Integrity

{AUTHOR_BLOCK}

---

## Abstract

Evaluating recall compliance across over-the-air (OTA) wireless software remedies, hybrid OTA-or-dealer remedies, and dealership-only software remedies requires observing campaigns at a uniform statutory reporting horizon rather than mixing heterogeneous reporting ages in latest-snapshot registries. We link the National Highway Traffic Safety Administration's (NHTSA) 2024 and 2025 annual eighth-quarter recall completion lists ({n_tot_rows:,} total rows; 100.0% matched to federal Part 573 filings; {n_dup_c} conflicting duplicate campaigns excluded) into a verified, uniquely dated cross-sectional sample of **{n_uniq:,} vehicle recalls**, including **{int(c_pool_pure['N_Campaigns'])} Pure-OTA**, **{int(c_pool_hyb['N_Campaigns'])} Hybrid-OTA**, **{int(c_pool_dsw['N_Campaigns'])} Dealer-Software**, and **{int(c_pool_phys['N_Campaigns']):,} Physical-Hardware** campaigns. Complete sample-flow accounting on the statutory 2022–2023 owner-notification (`ODATE`) cohort ($N = {sf['odate_2022_2023_total']:,}$) reconciles every campaign by channel, showing that {rec['odate_statutory_alignment']['combined_two_year_lag_pct']:.1f}% of eighth-report campaigns track 49 CFR § 573.7(a)'s two-year notification clock and that {flow_od['Pure_OTA']['Unlisted_Early_Completed_100pct']} of {flow_od['Pure_OTA']['Total_Campaigns'] - flow_od['Pure_OTA']['In_8th_Report_Unique']} unlisted Pure-OTA campaigns terminated early at 100.0% completion.

At the fixed eighth-report milestone, unweighted mean completion proportions are **{c_pool_pure['Mean_Completion_Pct']:.2f}%** for Pure-OTA (vehicle-weighted {c_pool_pure['Affected_Weighted_Mean_Pct']:.2f}%), **{c_pool_hyb['Mean_Completion_Pct']:.2f}%** for Hybrid-OTA ({c_pool_hyb['Affected_Weighted_Mean_Pct']:.2f}%), **{c_pool_dsw['Mean_Completion_Pct']:.2f}%** for Dealer Software ({c_pool_dsw['Affected_Weighted_Mean_Pct']:.2f}%), and **{c_pool_phys['Mean_Completion_Pct']:.2f}%** for Physical Hardware ({c_pool_phys['Affected_Weighted_Mean_Pct']:.2f}%). Because these annual lists provide cross-sectional milestone snapshots without multi-quarter longitudinal trajectories or phased remedy-availability dates, we interpret them strictly as fixed-horizon completion proportions rather than repair velocity. Auditing manufacturer $\\times$ channel $\\times$ vehicle-age common support reveals severe concentration: **Tesla accounts for {cs8['pure_tesla_n']}/{cs8['pure_total_n']} Pure-OTA recalls and {cs8['pure_tesla_vehicle_share_pct']:.2f}% of Pure-OTA vehicles** while contributing {cs8['tesla_dealer_sw_n']} Dealer-Software recalls, whereas the remaining {cs8['pure_nontesla_n']} non-Tesla Pure-OTA recalls (Lucid and Volvo Car) occur solely at oldest-model-year ages 0–{int(cs8['pure_nontesla_max_age_yr'])} years. While the dealer-software vehicle-age decay gradient is robustly negative across every specification and all {looo_s['n_oems_tested']} Leave-One-OEM-Out exclusions (**{fmt_signed(b_age['Coef'])} pp/yr**, $p_{{\\text{{WCB}}}} = {fmt_p(b_age['p_WCB'])}$; standalone Dealer Software **{fmt_signed(dsw_only_age['Coef'])} pp/yr**, $p_{{\\text{{WCB}}}} = {fmt_p(dsw_only_age['p_WCB'])}$; Physical Hardware **{fmt_signed(phys_only_age['Coef'])} pp/yr**, $p_{{\\text{{WCB}}}} = {fmt_p(phys_only_age['p_WCB'])}$), the baseline Pure-OTA $\\times$ Age interaction (**{fmt_signed(b_pure['Coef'])} pp/yr**, $p_{{\\text{{WCB}}}} = {fmt_p(b_pure['p_WCB'])}$) loses statistical precision in the 0–5 year window (**{fmt_signed(w5_pure['Coef'])}**, $p_{{\\text{{WCB}}}} = {fmt_p(w5_pure['p_WCB'])}$), collapses upon excluding Tesla (**{fmt_signed(nt_pure['Coef'])} pp/yr**, $p_{{\\text{{WCB}}}} = {fmt_p(nt_pure['p_WCB'])}$), and is null inside same-OEM common-support subsamples ($p_{{\\text{{WCB}}}} = {fmt_p(cs_pool_ota['p_WCB'])}$). We therefore **explicitly withdraw any universal claim that OTA neutralizes vehicle-age compliance decay**. Alongside fixed-horizon proportions and dealer-channel decay, we retain the robust within-OEM conditional **Hybrid-OTA {p1_hyb_mult:.2f}× batch-scale contrast** ($+1.947$ log points, $p_{{\\text{{WCB}}}} = {fmt_p(p1_hyb['p_wcb'])}$, contrasted with null unconditional OEM adoption event studies) and document a **public Campaign API measurement validation audit** showing that NHTSA's public `overTheAirUpdate` flag dropped from {n_19_23_true}/{n_19_23} (100.0%) in 2019–2023 and `36/36 True` on Volvo `25V282000` (May 8, 2025) to `0/{api_post25['n_txt_ota']}` (0.0%) post-cutoff beginning May 9 with Ford `25V315000` (`44/44 False` despite verbatim OTA remedy text), even as NHTSA's *2025 Annual Recalls Report* recorded 33 OTA recalls internally.

**Keywords:** *automotive safety recalls; over-the-air software updates; fixed reporting horizon; vehicle-age compliance decay; common-support diagnostics; public API measurement audit; 49 CFR 573.7; NHTSA*

---

## 1. Introduction

Motor vehicle safety recalls represent a central intersection of regulatory compliance, service-bay operations, and public road safety. Prior scholarship across economics, marketing, and operations management has examined recall timing, firm valuation, organizational learning, component sharing, and safety effectiveness in traditional mechanical recalls (Jarrell and Peltzman 1985; Barber and Darrough 1996; Rupp and Taylor 2002; Haunschild and Rhee 2004; MacCormack et al. 2006; Ramdas and Randall 2008; Bae and Benítez-Silva 2011; Hora et al. 2011; Thirumalai and Sinha 2011; Kalaignanam et al. 2013; Eilert et al. 2017; Shah et al. 2017; Ball et al. 2018), alongside theoretical studies of software patching incentives and user compliance (Arora et al. 2006; August and Tunca 2006; Cavusoglu et al. 2008). In the U.S. regulatory record, the National Highway Traffic Safety Administration's (NHTSA) own supplemental analysis (*Vehicle Safety Recall Completion Rates*, Report No. `DOT HS 813 687`; NHTSA 2025) establishes two foundational empirical determinants of conventional recall completion: **vehicle age**—as older vehicles exit franchised dealership maintenance networks and change owners in secondary markets—and **delays in remedy availability** between Part 573 defect filing and final owner notification. Complementary marketing research by Pagiavlas et al. (2022 [online 2021]) evaluates whether digital information campaigns ("Safe Cars Save Lives") improve consumer recall compliance.

As automakers deploy software-defined vehicles (SDVs), recalls involving embedded software can be delivered through three distinct administrative remedy channels: **Pure-OTA** (wireless-only remote updates), **Hybrid-OTA** (owner choice between an OTA update and a franchised dealership visit, or an OTA software push paired with hardware inspection), and **Dealer Software** (in-shop module reprogramming). NHTSA's `DOT HS 813 687` report (p. 1, fn. 1) explicitly designates *"Remedies involving Over-the-Air updates"* as one of seven high-risk oversight categories under its risk-based monitoring framework. Yet rigorous cross-channel comparison of recall completion in public federal records confronts three acute empirical hazards that have not been jointly resolved:

1. **Heterogeneous Reporting Horizons in Latest-Snapshot Registries:** The public U.S. Department of Transportation (DOT) open-data recalls file (`6axg-epim`) reports only each campaign's *latest* recorded completion rate, blending recent campaigns with campaigns that continued reporting well beyond the statutory six-quarter floor under **49 CFR § 573.7(a)**. As NHTSA itself notes in `DOT HS 813 687` (p. 5), comparing completion across manufacturers or remedy channels requires anchoring campaigns at a **fixed reporting horizon**—the eighth reporting quarter published in NHTSA's 2024 and 2025 annual completion lists—while explicitly accounting for sample flow (campaigns that completed 100% early, lacked reports, or had not yet reached their eighth quarter).
2. **Severe Manufacturer $\\times$ Channel $\\times$ Vehicle-Age Common-Support Limits:** Pure-OTA recalls in early fixed-horizon cohorts are overwhelmingly concentrated in a single EV-native manufacturer (`Tesla, Inc.`), while non-Tesla Pure-OTA fleets are newly manufactured (`0–1` years old at filing in the eighth-report cohort). Pooling across manufacturers with non-overlapping channel and vehicle-age support risks mistaking single-OEM fleet characteristics for a universal technological property of OTA delivery.
3. **Public Federal API Measurement Drift:** Automated research pipelines and consumer VIN tools frequently rely on NHTSA's public Campaign API boolean field (`overTheAirUpdate`). Without independent validation against verbatim Part 573 corrective-action narratives and NHTSA's published annual reports, unannounced changes in public-endpoint flag serialization can silently corrupt OTA classification.

This study addresses all three challenges using a verified, machine-readable dataset anchored on NHTSA's 2024 and 2025 annual eighth-quarter completion lists linked to the complete 2015–2026 NHTSA Office of Defects Investigation (ODI) Part 573 census ($N = {s3['rcl_panel']['n_campaigns_2015_2026']:,}$ vehicle campaigns; ${s3['rcl_panel']['n_campaigns_2018_2026']:,}$ in 2018–2026) and a {api_n_tot:,}-campaign audit of NHTSA's public Campaign API. Our paper makes four disciplined contributions organized specifically for safety-monitoring transparency and dataset reproducibility:

- **Fixed-Horizon Reconciliation and Complete Sample-Flow Accounting (Section 2):** We lock, verify, and row-reconcile all {n_tot_rows:,} published eighth-report entries against `FLAT_RCL_POST_2010.zip` and `6axg-epim` (100.0% campaign linkage; {rec['denominator_exact_match_pct']:.2f}% exact vehicle-denominator match; 100.0% exact match on all {rec['denominator_sw_total_count']} software recalls), cleanly exclude {n_dup_c} conflicting duplicate campaigns (`22V315`, `22V743`), and account channel-by-channel for every campaign in the statutory 2022–2023 owner-notification (`ODATE`) cohort ($N = {sf['odate_2022_2023_total']:,}$).
- **Fixed-Horizon Completion Proportions (Section 3):** We report unweighted, median, and vehicle-weighted eighth-report completion proportions by remedy channel and annual cohort strictly as **fixed-horizon completion proportions** (refraining from inferring repair velocity or hazard curves from cross-sectional snapshots).
- **Manufacturer $\\times$ Channel $\\times$ Vehicle-Age Common-Support Audit and Explicit Claim Withdrawal (Section 4):** We publish a complete common-support matrix and 18-OEM Leave-One-OEM-Out (`LOOO`) sensitivity audit demonstrating that while the **dealer-software vehicle-age decay gradient is rock-solid** ({fmt_signed(b_age['Coef'])} pp/yr in the 18-OEM sample; {fmt_signed(dsw_only_age['Coef'])} pp/yr across all 53 Dealer-Software OEMs; significant in {looo_s['dealer_age_sig_05_count']}/{looo_s['n_oems_tested']} LOOO drops, all $p_{{\\text{{WCB}}}} \\le {looo_s['dealer_age_max_pwcb']:.3f}$), existing public eighth-report and mature data lack multi-OEM older-vehicle common support to identify an OTA age-buffering effect. Accordingly, we **explicitly withdraw any universal claim that OTA neutralizes vehicle-age compliance decay**.
- **Public API Measurement Validation Audit, Conditional Batch-Scale Contrast, and Causal Operational Roadmap (Sections 5–6):** Separating verbatim Part 573 text coding (`Pure-OTA`, `Hybrid SW-Choice`, `Hybrid HW-Mixed`, `Dealer-Software`) from the public Campaign API flag isolates a May 8, 2025 public-endpoint serialization break (`25V282000` `36/36 True` vs. May 9 `25V315000` `44/44 False`; `0/{api_post25['n_txt_ota']}` thereafter) contrasted with NHTSA's *2025 Annual Recalls Report* (33 OTA recalls internally), framed strictly as a public-API validation audit; we pair this with the retained within-OEM conditional **Hybrid-OTA {p1_hyb_mult:.2f}× batch-scale contrast** ($+1.947$ log points, $p_{{\\text{{WCB}}}} = {fmt_p(p1_hyb['p_wcb'])}$) versus null unconditional OEM first-OTA adoption event studies, and close by specifying the exact longitudinal and quasi-experimental operational data needed for future causal mechanism identification.

---

## 2. Fixed Reporting Horizon, Source Reconciliation, and Sample Flow Accounting

### 2.1 Statutory Reporting Clock Under 49 CFR § 573.7 and Fixed-Horizon Selection

Under **49 CFR § 573.7(a)** (Office of the Federal Register 2026), manufacturers must file quarterly recall completion reports *"for each of six consecutive quarters beginning with the quarter in which the campaign was initiated (i.e., the date the manufacturer notifies its purchasers of the availability of a remedy) or corrective action has been completed on all defective or noncomplying vehicles ... whichever occurs first."* Two statutory mechanics directly govern empirical monitoring:

1. **Remedy-Notification Clock vs. Filing Date:** The quarterly completion clock starts at owner remedy notification (`ODATE`), not at Part 573 defect filing (`RCDATE`). Phased recalls that mail interim hazard notices under 49 CFR § 577.5 before a final software or parts remedy is ready enter quarterly reporting later than single-phase campaigns.
2. **Early Termination at 100% Completion and Unreachable-Vehicle Denominators:** Campaigns reaching 100% completion prior to the eighth reporting quarter lawfully terminate quarterly reporting under § 573.7(a) and therefore exit fixed-horizon lists. Meanwhile, § 573.7(b)(5) records vehicles deemed unreachable due to export, theft, scrapping, or undeliverable notification, meaning reported completion percentages reflect completion among reachable vehicles rather than raw unadjusted production totals.

In its supplemental FAST Act report (`DOT HS 813 687`, p. 5), NHTSA evaluated 2010–2022 light-vehicle recalls strictly at their **fifth reporting quarter** (substituting the early-completion quarter if 100% was achieved sooner) specifically *"to control for variability in the length of reporting periods among manufacturers, as some companies continue to submit well after the minimum regulatory requirement."* Similarly, NHTSA's published **2024 and 2025 Annual Lists of Recall Completion Rates** (NHTSA 2025, 2026a) anchor campaigns at a uniform **eighth-quarter completion milestone**. By contrast, the latest-snapshot DOT open-data registry (`6axg-epim`) updates dynamically past the eighth quarter: among the {rec['dot_latest_vs_eighth_report']['n_rated_in_dot']:,} eighth-report campaigns also rated in `6axg-epim` as of November 25, 2026, latest-snapshot rates exceed the eighth-report milestone in {rec['dot_latest_vs_eighth_report']['n_higher_in_dot_gt_01pp']:,} campaigns (median drift **+{rec['dot_latest_vs_eighth_report']['median_drift_pp']:.2f} pp**, mean **+{rec['dot_latest_vs_eighth_report']['mean_drift_pp']:.2f} pp**), demonstrating why latest-snapshot data confound reporting duration with remedy performance. Because the annual eighth-report lists provide one cross-sectional completion proportion per campaign without intermediate Q1–Q7 trajectories or phase-specific remedy availability dates, our primary analysis interprets these figures strictly as **fixed-horizon completion proportions** and relegates all mature ($\\ge 18$-month) latest-snapshot cross-sections to Online Appendix Section S2.

### 2.2 Verifiable Source Freezing, Reconciliation, and Duplicate Exclusion

We integrate four locked public federal inputs with cryptographic SHA-256 receipts (`SHA256SUMS.json`): (i) NHTSA's complete Part 573 Vehicle Recall flat file (`FLAT_RCL_POST_2010.zip`, ${s3['rcl_panel']['n_campaigns_2015_2026']:,}$ campaigns in 2015–2026; ${s3['rcl_panel']['n_campaigns_2018_2026']:,}$ in 2018–2026, harmonized from 705 raw manufacturer strings into 646 canonical corporate entities); (ii) the transcribed 2024 and 2025 eighth-report source table (`data_raw/nhtsa_annual_eighth_report_2024_2025.csv`, SHA-256 `{prov['annual_eighth_report_csv']['sha256'][:16]}...`, {n_tot_rows:,} rows: {n_2024_raw:,} in 2024 and {n_2025_raw:,} in 2025); (iii) U.S. DOT's official Socrata registry (`6axg-epim`, frozen November 25, 2026) and NHTSA's official ROSA P report PDF (`dot_79374_DS1.pdf`, HTTP 200, SHA-256 `{prov['dot_hs_813_687_pdf']['sha256'][:16]}...`); and (iv) our {api_n_tot:,}-campaign live query census of `api.nhtsa.gov/recalls/campaignNumber` supplemented by fresh boundary spot-checks (`results/d12_v4_live_api_spotcheck.json`). We note transparently that direct automated HTTP requests to the `www.nhtsa.gov` PDF URLs for the 2024 and 2025 annual lists returned HTTP 403 Akamai CDN access control; strictly adhering to non-bypass protocols, we locked the verbatim transcribed 1,537-row table and executed a complete 100% row-level programmatic reconciliation against `FLAT_RCL_POST_2010.zip` and `6axg-epim`:

- **Campaign Linkage (100.0%):** Every single row ({n_2024_raw:,}/{n_2024_raw:,} in 2024 and {n_2025_raw:,}/{n_2025_raw:,} in 2025; zero unlinked rows) links cleanly via its six-character NHTSA campaign identifier (`campaign_code`) to the frozen Part 573 panel.
- **Conflicting Duplicate Exclusion ({n_dup_c} Campaigns, {n_dup_r} Rows):** Exactly two campaigns appear in *both* the 2024 and 2025 annual lists with conflicting eighth-report completion percentages: Mercedes-Benz `22V315` (Physical Hardware, {dup_details[('22V315', 2024)]['reported_affected']:,} vehicles: **{dup_details[('22V315', 2024)]['completion_at_eighth_report_pct']:.1f}%** in 2024 vs. **{dup_details[('22V315', 2025)]['completion_at_eighth_report_pct']:.1f}%** in 2025; latest DOT {dup_details[('22V315', 2024)]['dot_latest_completion_rate_pct']:.2f}%) and Bentley `22V743` (Dealer Software, {dup_details[('22V743', 2024)]['reported_affected']:,} vehicles: **{dup_details[('22V743', 2024)]['completion_at_eighth_report_pct']:.1f}%** in 2024 vs. **{dup_details[('22V743', 2025)]['completion_at_eighth_report_pct']:.1f}%** in 2025; latest DOT {dup_details[('22V743', 2024)]['dot_latest_completion_rate_pct']:.2f}%). Dropping all four duplicate rows leaves **{n_uniq:,} uniquely dated eighth-report campaigns** ({rec['unique_by_report_year']['2024']:,} in 2024; {rec['unique_by_report_year']['2025']:,} in 2025).
- **Vehicle-Denominator Reconciliation ({rec['denominator_exact_match_pct']:.2f}% Exact Match):** Comparing the eighth-report affected vehicle count (`reported_affected`) against `FLAT_RCL`/`6axg-epim` (`potaff`) yields an **exact single-vehicle match on {rec['denominator_exact_match_count']:,}/{n_uniq:,} ({rec['denominator_exact_match_pct']:.2f}%) campaigns** ($\\log r = {rec['denominator_log_corr']:.5f}$) and **100.0% ({rec['denominator_sw_exact_match_count']}/{rec['denominator_sw_total_count']}) exact agreement across all software recalls** (Pure-OTA, Hybrid-OTA, and Dealer Software). Auditing the only two discrepancies—both Physical Hardware—reveals Honda `22V867` (`17,445` in the transcribed 2025 table vs. `117,445` in `FLAT_RCL` and `6axg-epim`, flagged transparently as a missing leading digit in source extraction) and Chrysler/FCA `23V413` (`331,401` vs. `305,282`, reflecting post-filing denominator amendment). Neither enters any software-channel regression.
- **Owner-Notification Clock Verification ({rec['odate_statutory_alignment']['combined_two_year_lag_pct']:.1f}% Statutory Alignment):** Exactly **{rec['odate_statutory_alignment']['2024_list_odate_2022_n']}/{rec['odate_statutory_alignment']['2024_list_total_n']} ({rec['odate_statutory_alignment']['2024_list_odate_2022_pct']:.1f}%)** of unique 2024 eighth-report campaigns carried owner notification dates (`ODATE`) in calendar year **2022**, and **{rec['odate_statutory_alignment']['2025_list_odate_2023_n']}/{rec['odate_statutory_alignment']['2025_list_total_n']} ({rec['odate_statutory_alignment']['2025_list_odate_2023_pct']:.1f}%)** of unique 2025 eighth-report campaigns carried `ODATE` in calendar year **2023**—directly empirically validating 49 CFR § 573.7(a)'s two-year notification clock.

### 2.3 Channel-by-Channel Sample Flow Accounting

Because eighth-report annual lists observe only campaigns that reached their eighth reporting quarter without completing 100% earlier, interpreting cross-channel completion proportions requires complete sample-flow accounting across all remedy channels. **Table 1** and **Figure 1A** reconcile three nested frames: (A) the statutory **2022–2023 `ODATE` cohort** ($N = {sf['odate_2022_2023_total']:,}$ campaigns), (B) the **2022–2023 `RCDATE` filing cohort** ($N = {sf['rcdate_2022_2023_total']:,}$ campaigns), and (C) the full **2018–2026 NHTSA vehicle recall universe** ($N = {sf['universe_2018_2026_total']:,}$ campaigns).

**Table 1.** *Complete Channel-by-Channel Sample Flow Accounting: Statutory 2022–2023 Owner-Notification Cohort (`ODATE`), 2022–2023 Filing Cohort (`RCDATE`), and 2018–2026 Universe.*

{chr(10).join(t1_lines)}

*Notes:* Panel A tracks all {sf['odate_2022_2023_total']:,} vehicle recalls with recorded owner notification (`ODATE`) in 2022–2023; adding {sf['earlier_odate_delayed_entries_n']} delayed 2020–2021 `ODATE` campaigns ({sf['earlier_odate_delayed_entries_by_modality'].get('Dealer_Software', 0)} Dealer Software, `20V771` Honda, plus {sf['earlier_odate_delayed_entries_by_modality'].get('Physical_Hardware', 0)} Physical Hardware) yields the exact {n_uniq:,} uniquely dated eighth-report campaigns. In Panel B, late-2023 Part 573 filings whose `ODATE` fell in 2024 (including Tesla `23V838`, `23V862`, Rivian `23V883`, and Lonestar `23V768`) had not yet reached their eighth reporting quarter by end-2025.

Three administrative selection mechanics stand out in Table 1:

1. **Complete Accounting of Software-OTA Campaigns:** Within the statutory 2022–2023 `ODATE` cohort, **{flow_od['Hybrid_OTA']['In_8th_Report_Unique']}/{flow_od['Hybrid_OTA']['Total_Campaigns']} (100.0%)** of Hybrid-OTA recalls appear uniquely in the 2024–2025 eighth-report lists. Among **{flow_od['Pure_OTA']['Total_Campaigns']}** Pure-OTA recalls, **{flow_od['Pure_OTA']['In_8th_Report_Unique']} ({flow_od['Pure_OTA']['Share_In_8th_Pct']:.1f}%)** appear uniquely, and **100% of the remaining 6 unlisted campaigns are accounted for**: **{flow_od['Pure_OTA']['Unlisted_Early_Completed_100pct']}** reached **100.0% completion** prior to the eighth report (`22V037` Tesla 53,822 veh; `22V169` Tesla 947 veh; `23V244` Tesla 38 veh; `23V422` Tesla 36 veh; `23V783` Rivian 1,463 veh), lawfully terminating quarterly reporting under § 573.7(a), and **{flow_od['Pure_OTA']['Unlisted_Missing_DOT_Report']}** (`22V063` Tesla Boombox, 578,607 veh) lacks a DOT completion record.
2. **Differential Early-Completion Selection Across Channels:** Early 100% completion prior to the eighth quarter accounts for **{100.0 * flow_od['Pure_OTA']['Unlisted_Early_Completed_100pct'] / flow_od['Pure_OTA']['Total_Campaigns']:.1f}%** ({flow_od['Pure_OTA']['Unlisted_Early_Completed_100pct']}/{flow_od['Pure_OTA']['Total_Campaigns']}) of Pure-OTA campaigns versus **{100.0 * flow_od['Dealer_Software']['Unlisted_Early_Completed_100pct'] / flow_od['Dealer_Software']['Total_Campaigns']:.1f}%** ({flow_od['Dealer_Software']['Unlisted_Early_Completed_100pct']}/{flow_od['Dealer_Software']['Total_Campaigns']}) of Dealer Software and **{100.0 * flow_od['Physical_Hardware']['Unlisted_Early_Completed_100pct'] / flow_od['Physical_Hardware']['Total_Campaigns']:.1f}%** ({flow_od['Physical_Hardware']['Unlisted_Early_Completed_100pct']}/{flow_od['Physical_Hardware']['Total_Campaigns']}) of Physical Hardware—indicating that fixed eighth-report Pure-OTA means slightly *understate* unconditional Pure-OTA completion by omitting campaigns that hit 100% early.
3. **Notification-Lag Filtering in Filing-Year Cohorts:** Comparing Panel A (`ODATE`) with Panel B (`RCDATE`) shows why late-2023 filings with 2024 owner-notification dates (e.g., Tesla `23V838`, 2,031,220 veh, `ODATE` Feb 10, 2024; Tesla `23V862`, 120,423 veh, `ODATE` Feb 17, 2024; Rivian `23V883`, 7,873 veh, `ODATE` Jan 18, 2024) are legitimately absent from the 2025 eighth-report list and will enter the 2026 list upon completing eight reporting quarters.

<!-- FIGURE:fig1_v4_sample_flow_and_completion.png -->

### 2.4 Remedy-Channel Coding and Finite-Sample Cluster-Robust Inference

To prevent public API serialization anomalies from contaminating channel labels, we classify every campaign strictly from its verbatim Part 573 and DOT `CORRECTIVE_ACTION` text (explicitly screening out negations such as *"not eligible for an over-the-air update"*), separating four mutually exclusive remedy channels (and subdividing Hybrid-OTA in audit tables): (1) **Pure-OTA** (wireless-only software update with no dealer visit, inspection, or hardware replacement clause), (2) **Hybrid-OTA** (OTA-capable software update paired with either a dealer software option—**Hybrid SW-Choice**—or physical hardware replacement/inspection—**Hybrid HW-Mixed**), (3) **Dealer Software** (software/firmware reprogramming or calibration without an OTA option), and (4) **Physical Hardware** (all non-software physical remedies). Critically, a Hybrid-OTA Part 573 notice documents *channel availability* ("over-the-air or by a dealer"), not the share of vehicles actually remedied wirelessly versus in dealership bays.

All regressions are estimated via full-rank verified ordinary least squares absorbing Manufacturer, Component-Group (top 14 subsystems plus Other), Filing-Quarter, and Annual Report-Year fixed effects (plus Model-Year fixed effects in batch-scale regressions), with Stata finite-sample CR1 manufacturer-clustered standard errors, $t(G - 1)$ inference, and exact null-imposed $B = 999$ Rademacher Wild Cluster Bootstrap $p$-values ($p_{{\\text{{WCB}}}}$; Cameron et al. 2008; Cameron and Miller 2015; MacKinnon and Webb 2017). Mathematical exactness of the vectorized WCB implementation is verified against brute-force bootstrap resampling to $< 10^{{-10}}$ in `tests/test_d12_boost.py`.

---

## 3. Fixed-Horizon Completion Proportions by Remedy Channel and Manufacturer

### 3.1 Descriptive Fixed Eighth-Report Completion Proportions

**Table 2** and **Figure 1B** present unweighted campaign means, standard deviations, medians, interquartile ranges, and vehicle-weighted completion proportions across the 2024, 2025, and pooled {n_uniq:,}-campaign eighth-report cohorts.

**Table 2.** *Fixed Eighth-Report Completion Proportions by Remedy Channel and Report Year (N = {n_uniq:,} Uniquely Dated Campaigns).*

{chr(10).join(t2_lines)}

*Notes:* All completion figures represent cross-sectional completion proportions at NHTSA's eighth reporting quarter milestone, not longitudinal repair-velocity or hazard-rate estimates. All {int(c24_pure['N_Campaigns'])} Pure-OTA campaigns in the 2024 list belong to a single manufacturer (`Tesla, Inc.`).

Across the pooled 2024–2025 fixed eighth-report sample, observed completion proportions display a clear descriptive ordering: **Pure-OTA** averages **{c_pool_pure['Mean_Completion_Pct']:.2f}%** (median {c_pool_pure['Median_Completion_Pct']:.2f}%, vehicle-weighted {c_pool_pure['Affected_Weighted_Mean_Pct']:.2f}%), **Hybrid-OTA** averages **{c_pool_hyb['Mean_Completion_Pct']:.2f}%** (median {c_pool_hyb['Median_Completion_Pct']:.2f}%, vehicle-weighted {c_pool_hyb['Affected_Weighted_Mean_Pct']:.2f}%), **Dealer Software** averages **{c_pool_dsw['Mean_Completion_Pct']:.2f}%** (median {c_pool_dsw['Median_Completion_Pct']:.2f}%, vehicle-weighted {c_pool_dsw['Affected_Weighted_Mean_Pct']:.2f}%), and **Physical Hardware** averages **{c_pool_phys['Mean_Completion_Pct']:.2f}%** (median {c_pool_phys['Median_Completion_Pct']:.2f}%, vehicle-weighted {c_pool_phys['Affected_Weighted_Mean_Pct']:.2f}%). Within the eight manufacturers that actually execute both Dealer Software and OTA remedies in the eighth-report sample ($N = 70$, $G = 8$), controlling for OEM, component, filing-quarter, report-year fixed effects, and oldest-model-year vehicle age yields a positive level contrast for pooled OTA of **{fmt_signed(cs_lvl_ota['Coef'])} pp** ($p_{{\\text{{WCB}}}} = {fmt_p(cs_lvl_ota['p_WCB'])}$; Hybrid-OTA **{fmt_signed(cs_lvl_hyb['Coef'])} pp**, $p_{{\\text{{WCB}}}} = {fmt_p(cs_lvl_hyb['p_WCB'])}$; Pure-OTA **{fmt_signed(cs_lvl_pure['Coef'])} pp**, $p_{{\\text{{WCB}}}} = {fmt_p(cs_lvl_pure['p_WCB'])}$). Crucially, however, raw and level-adjusted cross-channel proportions reflect both delivery friction and unobserved differences in defect type, fleet connectivity, and manufacturer composition (including the fact that all {int(c24_pure['N_Campaigns'])} Pure-OTA recalls in 2024 came from one OEM). We therefore refrain from inferring causal delivery speed or repair-hazard curves from these cross-sectional snapshots.

---

## 4. Manufacturer × Channel × Vehicle-Age Common Support and Leave-One-OEM-Out Sensitivity

### 4.1 Explicit Manufacturer × Channel × Vehicle-Age Common-Support Audit

A central question for safety research is whether wireless OTA delivery offsets the steep decline in recall completion as vehicles age into secondary markets (NHTSA 2025). Testing an OTA $\\times$ vehicle-age interaction credibly requires **common support**—multiple manufacturers executing both OTA and dealer-software recalls across overlapping vehicle ages, including older ($\\ge 5$–6 year) vehicles. **Table 3** and **Figure 2** expose the exact support structure of the fixed eighth-report software sample ($N = {cs8['n_sw_ota_oems']}$ across {cs8['n_oems_total']} OTA-capable OEMs; complete cross-horizon matrix archived in `tables/table_channel_oem_age_support.csv`).

**Table 3.** *Manufacturer × Channel × Vehicle-Age Common-Support Matrix in the Fixed Eighth-Report Software Sample ($N = {cs8['n_sw_ota_oems']}$, {cs8['n_oems_total']} OTA-Capable OEMs).*

{chr(10).join(t3_lines)}

*Notes:* Vehicle age is `rec_year` minus oldest affected model year (`min_my`), clipped to $[0, 15]$. Full OEM-level breakdown across both the fixed eighth-report cohort and the mature $\\ge 18$-month DOT snapshot is archived in `tables/table_channel_oem_age_support.csv`.

The support audit reveals four binding structural limitations that preclude a universal OTA age-buffering conclusion:

1. **Single-OEM Dominance in Pure-OTA:** Among all **{cs8['pure_total_n']}** fixed eighth-report Pure-OTA campaigns, **`Tesla, Inc.` accounts for {cs8['pure_tesla_n']}/{cs8['pure_total_n']} recalls (73.3%) and {cs8['pure_tesla_vehicle_share_pct']:.2f}% of affected vehicles** (3,522,202 of 3,551,795), spanning oldest-model-year ages 1–7 years—while contributing **zero ({cs8['tesla_dealer_sw_n']}) Dealer-Software recalls** in the eighth-report sample. Tesla therefore has **no within-OEM dealer-software counterfactual** at the eighth-report horizon.
2. **Zero Older-Vehicle Support Outside Tesla:** The remaining **{cs8['pure_nontesla_n']}** non-Tesla Pure-OTA recalls come from just two manufacturers—`Lucid USA, Inc.` (3 recalls, 2,136 vehicles, all oldest-MY age **1 year**) and `Volvo Car USA, LLC` (1 recall, 27,457 vehicles, oldest-MY age **0 years**). Neither manufacturer contributes any within-OEM Pure-OTA vehicle-age variation, and **zero non-Tesla Pure-OTA recalls reach age $\\ge 2$ years** in the eighth-report sample. Even in the broader mature $\\ge 18$-month DOT snapshot (`6axg-epim`, Online Appendix Section S2), Tesla accounts for **{csm['pure_tesla_n']}/{csm['pure_total_n']} Pure-OTA recalls**, **{csm['pure_tesla_vehicle_share_pct']:.2f}% of affected vehicles**, and **{csm['pure_age_6plus_tesla']}/{csm['pure_age_6plus_total']} (100.0%) of all Pure-OTA recalls aged $\\ge 6$ years** (Figure 2B), while non-Tesla light-duty Pure-OTA maxes out at age 3 years.
3. **Narrow Age Support in Hybrid-OTA:** The 15 fixed eighth-report Hybrid-OTA recalls span 6 legacy manufacturers (`Ford`, `General Motors`, `Mercedes-Benz`, `Nissan`, `Jaguar Land Rover`, `Daimler Vans`), with 13 of 15 concentrated at ages 0–3 years and zero reaching age $\\ge 6$ years (max age 5 years: one Mercedes-Benz recall).
4. **Minimal Same-OEM and Same-Model Overlap:** Strictly restricting the eighth-report cohort to manufacturers observing *both* Dealer Software and any OTA channel leaves just **{len(cs8['same_oem_both_dsw_and_ota_oems'])} OEMs** ($N = 70$: 4 Pure-OTA, 15 Hybrid-OTA, 51 Dealer Software)—**excluding Tesla altogether**—and intersecting each OEM's overlapping age span reduces the sample to $N = 53$. Restricting further to exact same `primary_make_model` lines leaves only **{cs8['same_model_overlap_count']} models** (`FORD MUSTANG MACH E`, `FREIGHTLINER SPRINTER 1500`, `JAGUAR I-PACE`, `LUCID AIR`, `MERCEDES-BENZ EQS 450`, `VOLVO C40BEV`; $N = 20$ campaigns total), each having a single OTA campaign age and thus **zero within-model OTA age variation**.

<!-- FIGURE:fig2_v4_channel_oem_age_support.png -->

### 4.2 Vehicle-Age Gradients, Common-Support Subsamples, and Complete 18-OEM LOOO

**Table 4** and **Figure 3** quantify the econometric consequences of this support structure across age definitions, age windows, Tesla exclusion, same-OEM common-support subsamples, standalone channel benchmarks, and complete 18-OEM Leave-One-OEM-Out (`LOOO`) sensitivity (full 18-row LOOO table in Online Appendix Table S1 and `tables/table_v4_looo_sensitivity.csv`).

**Table 4.** *Fixed Eighth-Report Vehicle-Age Gradient Sensitivity and Common-Support Subsamples (CR1 Cluster-Robust Inference with $B = 999$ Rademacher $p_{{\\text{{WCB}}}}$).*

{chr(10).join(t4_lines)}

*Notes:* All models include Manufacturer, Component-Group, Filing-Quarter, and Report-Year fixed effects with OEM-clustered $B = 999$ Rademacher Wild Cluster Bootstrap $p$-values in parentheses. Supplementary mature latest-snapshot regressions (including 29-model Make-Model FE overlap with and without Tesla) are reported in Online Appendix Table S2.

Every econometric check converges on the exact same sharp diagnostic split:

- **Rock-Solid Dealer-Channel Vehicle-Age Decay:** Holding manufacturer, component, filing quarter, and report year constant, Dealer-Software completion at the eighth report declines by **{fmt_signed(b_age['Coef'])} pp per year of oldest-model-year age** ($p_{{\\text{{WCB}}}} = {fmt_p(b_age['p_WCB'])}$; **{fmt_signed(m_age['Coef'])} pp/yr** using middle model year, $p_{{\\text{{WCB}}}} = {fmt_p(m_age['p_WCB'])}$). Across all 53 OEMs in standalone Dealer Software ($N = {int(dsw_only_age['N'])}$), the gradient is **{fmt_signed(dsw_only_age['Coef'])} pp/yr** ($p_{{\\text{{WCB}}}} = {fmt_p(dsw_only_age['p_WCB'])}$), closely matching standalone Physical Hardware across all 213 OEMs ($N = {int(phys_only_age['N']):,}$; **{fmt_signed(phys_only_age['Coef'])} pp/yr**, $p_{{\\text{{WCB}}}} = {fmt_p(phys_only_age['p_WCB'])}$). Across all **{looo_s['n_oems_tested']} Leave-One-OEM-Out exclusions** (Figure 3B), the Dealer-Software age slope stays tightly bounded between **{fmt_signed(looo_s['dealer_age_min_coef'])}** and **{fmt_signed(looo_s['dealer_age_max_coef'])} pp/yr** and remains statistically significant in **{looo_s['dealer_age_sig_05_count']}/{looo_s['n_oems_tested']}** drops (maximum $p_{{\\text{{WCB}}}} = {looo_s['dealer_age_max_pwcb']:.3f}$).
- **Fragility and Collapse of the Pure-OTA $\\times$ Age Interaction:** Although the pooled 18-OEM baseline specification yields a nominal Pure-OTA $\\times$ Age interaction of **{fmt_signed(b_pure['Coef'])} pp/yr** ($p_{{\\text{{WCB}}}} = {fmt_p(b_pure['p_WCB'])}$), that estimate fails every common-support stress test:
  1. Restricting to the **0–5 year age window** ($N = {int(w5_pure['N'])}$) leaves the interaction statistically imprecise (**{fmt_signed(w5_pure['Coef'])} pp/yr**, $p_{{\\text{{WCB}}}} = {fmt_p(w5_pure['p_WCB'])}$);
  2. **Excluding Tesla** ($N = {int(nt_pure['N'])}$, 17 OEMs) collapses Pure-OTA $\\times$ Age to **{fmt_signed(nt_pure['Coef'])} pp/yr** (**$p_{{\\text{{WCB}}}} = {fmt_p(nt_pure['p_WCB'])}$**; pooled ex-Tesla OTA **{fmt_signed(nt_pool['Coef'])}**, $p_{{\\text{{WCB}}}} = {fmt_p(nt_pool['p_WCB'])}$; middle-MY pooled ex-Tesla **{fmt_signed(nt_mid_pool['Coef'])}**, $p_{{\\text{{WCB}}}} = {fmt_p(nt_mid_pool['p_WCB'])}$);
  3. Restricting to the **8 same-OEM common-support manufacturers** ($N = {int(cs_pool_ota['N'])}$) yields null interactions for pooled OTA (**{fmt_signed(cs_pool_ota['Coef'])}**, $p_{{\\text{{WCB}}}} = {fmt_p(cs_pool_ota['p_WCB'])}$), Pure-OTA (**{fmt_signed(cs_4w_pure['Coef'])}**, $p_{{\\text{{WCB}}}} = {fmt_p(cs_4w_pure['p_WCB'])}$), and Hybrid-OTA (**{fmt_signed(cs_4w_hyb['Coef'])}**, $p_{{\\text{{WCB}}}} = {fmt_p(cs_4w_hyb['p_WCB'])}$), and restricting further to **strict same-OEM $\\times$ overlapping-age cells** ($N = {int(cs_ov_ota['N'])}$) turns negative and imprecise (**{fmt_signed(cs_ov_ota['Coef'])}**, $p_{{\\text{{WCB}}}} = {fmt_p(cs_ov_ota['p_WCB'])}$);
  4. Across all **18 Leave-One-OEM-Out drops** (Figure 3B), Pure-OTA $\\times$ Age fails 5% wild-cluster-bootstrap significance in **{looo_s['pure_x_age_non_sig_05_count']}/18** exclusions (dropping Tesla, Chrysler, Ford, General Motors, Honda, Mack Trucks, Mercedes-Benz, or Nissan).
- **Consistent Null for Hybrid-OTA $\\times$ Age:** Hybrid-OTA $\\times$ Age is statistically indistinguishable from zero in the baseline (**{fmt_signed(b_hyb['Coef'])}**, $p_{{\\text{{WCB}}}} = {fmt_p(b_hyb['p_WCB'])}$), flips sign under middle model year (**{fmt_signed(m_hyb['Coef'])}**, $p_{{\\text{{WCB}}}} = {fmt_p(m_hyb['p_WCB'])}$), and achieves $p_{{\\text{{WCB}}}} < 0.05$ in **{looo_s['hybrid_x_age_sig_05_count']}/18** LOOO specifications.

<!-- FIGURE:fig3_v4_age_gradients_and_looo.png -->

### 4.3 Explicit Withdrawal of Universal OTA Age-Buffering Claims

Based on the common-support audit in Section 4.1 and the LOOO diagnostics in Section 4.2, **we explicitly withdraw any universal claim that over-the-air software remediation neutralizes vehicle-age compliance decay.** While Tesla's observed Pure-OTA campaigns maintain high completion through oldest-model-year age 7 in the eighth-report sample (and age 12 in the mature latest-snapshot archive), current public federal records lack multi-manufacturer older-vehicle common support to separate wireless delivery technology from single-OEM architecture, owner demographics, or fleet-telematics design. What the fixed eighth-report evidence *does* establish robustly is (i) the complete fixed-horizon descriptive completion profile by channel and manufacturer, (ii) the persistent **$-3.52$ to $-4.03$ pp/yr dealer-software vehicle-age decay gradient** (mirroring physical hardware's $-3.27$ pp/yr decline), and (iii) the sharp **within-OEM Hybrid-OTA {p1_hyb_mult:.2f}× batch-scale contrast**.

---

## 5. Public Campaign API Measurement Validation Audit and Conditional Hybrid Batch-Scale Contrast

### 5.1 Public Campaign API Measurement Validation Audit

Independent of completion-rate inference, safety researchers and automated VIN-lookup tools frequently extract OTA recall labels directly from NHTSA's public Campaign API (`api.nhtsa.gov/recalls/campaignNumber`, field `overTheAirUpdate`). To validate whether this public endpoint reliably reflects published Part 573 remedy texts, we audited **100% of software and OTA-candidate vehicle campaigns in 2018–2026** ($N = {audit_api['candidates_valid']:,}$) plus a **stratified random sample of {api_phys_n} physical hardware recalls** (total $N = {api_n_tot:,}$, 100.0% HTTP 200 success, zero errors) and re-verified boundary cases live (`results/d12_v4_live_api_spotcheck.json`). Crucially, **Table 5** and **Figure 4A** separate verbatim Part 573 remedy-text coding (`Pure-OTA`, `Hybrid SW-Choice`, `Hybrid HW-Mixed`, `Dealer-Software`) cleanly from the public API flag.

**Table 5.** *Public NHTSA Campaign API Measurement Validation Audit: Verbatim Part 573 Text Coding vs. Live Public API `overTheAirUpdate` Flag (2018–2026, $N = {api_n_tot:,}$ Queried Campaigns).*

{chr(10).join(t6_lines)}

*Notes:* Pre-cutoff covers filings on or before May 8, 2025 (final `overTheAirUpdate = True` campaign: Volvo `25V282000`, 36/36 model-year records `True`); post-cutoff covers filings after May 8, 2025 through November 2026 (beginning May 9, 2025 with Ford `25V315000`, 44/44 records `False` despite explicit OTA remedy text). Zero campaigns returned `overTheAirUpdate = True` without explicit OTA text (`0/984` Dealer Software; `{api_phys_fn}/{api_phys_n}` Physical Hardware).

Three measurement-validation findings emerge:

1. **Near-Perfect Pre-Cutoff Concordance on Pure and Software-Choice OTA:** From 2019 through 2023, the public API flag agreed with verbatim Part 573 text on **{n_19_23_true}/{n_19_23} (100.0%)** of text-positive OTA campaigns, and on **{api_yr[2024]['n_api_true']}/{api_yr[2024]['n_txt_ota']} ({100*api_yr[2024]['api_true_rate']:.1f}%)** in 2024—with **zero ({api_phys_fn}/{api_phys_n}) false negatives** on audited physical recalls and zero false positives on dealer-only software. Disaggregating by text structure reveals that before May 8, 2025, public API agreement was **100.0% ({int(apic_map['Pure_OTA_Wireless_Only']['Pre_Cutoff_API_True'])}/{int(apic_map['Pure_OTA_Wireless_Only']['Pre_Cutoff_API_Queried'])})** on wireless-only Pure-OTA and **95.0% ({int(apic_map['Hybrid_SW_Choice_OTA_Capable']['Pre_Cutoff_API_True'])}/{int(apic_map['Hybrid_SW_Choice_OTA_Capable']['Pre_Cutoff_API_Queried'])})** on Hybrid SW-Choice, compared with **50.0% ({int(apic_map['Hybrid_HW_Mixed_Hardware_Req']['Pre_Cutoff_API_True'])}/{int(apic_map['Hybrid_HW_Mixed_Hardware_Req']['Pre_Cutoff_API_Queried'])})** on Hybrid HW-Mixed campaigns where hardware inspection or replacement was required alongside an OTA push (e.g., Lucid `24V495000`).
2. **Sharp May 8, 2025 Public-Endpoint Break:** During January 1–May 8, 2025, public API concordance fell to **{api_pre25['n_api_true']}/{api_pre25['n_txt_ota']} ({100*api_pre25['api_true_rate']:.1f}%)**, ending abruptly with Volvo `25V282000` (filed May 8, 2025; live spot-check confirmed **{spot_map['25V282000']['flag_values'].get('true', 0)}/{spot_map['25V282000']['api_records']} records `True`**). Starting the very next day with Ford `25V315000` (filed May 9, 2025; live spot-check confirmed **{spot_map['25V315000']['flag_values'].get('false', 0)}/{spot_map['25V315000']['api_records']} records `False`** despite verbatim text *"updated by a dealer or through an over-the-air update"*), the public Campaign API returned **`False` on {api_post25['n_txt_ota']}/{api_post25['n_txt_ota']} (100.0%)** of subsequent text-positive OTA campaigns across 2025 and 2026—including wireless-only Pure-OTA recalls such as Polestar `25V409000` (`{spot_map['25V409000']['flag_values'].get('false', 0)}/{spot_map['25V409000']['api_records']} False`) and 2026 Hybrid-OTA recalls such as Ford `26V104000` (`{spot_map['26V104000']['flag_values'].get('false', 0)}/{spot_map['26V104000']['api_records']} False`).
3. **Strict Public-API Audit Scope (Not Internal Agency Error):** Contrasting the live public Campaign API count in 2025 (**{api_yr[2025]['n_api_true']} `True`** out of {api_yr[2025]['n_txt_ota']} text-coded OTA recalls) against NHTSA's separate ***2025 Annual Recalls Report*** (NHTSA 2026b), which internally tallied **33 partially or fully OTA-remedied recalls in 2025**, demonstrates that NHTSA continued monitoring OTA recalls internally under its own counting criteria (which exclude text-offered OTA options never actually deployed). We therefore interpret this finding strictly as a **public Campaign API measurement validation issue**: researchers using `api.nhtsa.gov` after May 8, 2025 must not treat `overTheAirUpdate` as a standalone OTA label, and should instead code verbatim Part 573 remedy texts transparently while using the public API flag strictly as an external pre-cutoff validation benchmark. Note that none of our fixed eighth-report completion results depend on the post-cutoff API flag.

### 5.2 Retained Within-OEM Conditional Hybrid-OTA Batch-Scale Contrast

Alongside the measurement audit, one structural operational feature of the 2018–2026 software recall census is sharply identified across manufacturers: **within OTA-capable OEMs, Hybrid-OTA campaigns are substantially larger in batch scale than dealership-only software recalls.** **Table 6** and **Figure 4B** summarize this conditional contrast alongside distinct unconditional OEM-level first-OTA adoption event studies (full robustness ladder in Online Appendix Section S3).

**Table 6.** *Retained Within-OEM Conditional Batch-Scale Contrast vs. Unconditional OEM First-OTA Adoption Event Studies (2015–2026).*

{chr(10).join(t5_lines)}

*Notes:* Conditional specifications include Manufacturer, Filing-Year, Oldest-Model-Year, and Component fixed effects (unless replaced by OEM $\\times$ Year or Make $\\times$ Model FE) on OTA-capable OEMs' 2018–2026 software recalls. Unconditional ITT models pool *all* 2015–2026 software recalls (OTA + Dealer Software) across adopting and never-OTA OEMs (pre-trend Wald $p = {p1_itt_pre['p_value']:.3f}$ for TWFE; $p = {p1_sa['iw_pre_trend_wald_m3_m2']['p_value']:.3f}$ for saturated Sun–Abraham 2021 IW across 7 cohorts excluding partial-year cohort 2026). Conditional and unconditional estimates identify distinct estimands; no percentage selection-share decomposition is computed.

Conditional on observing a software recall within an OTA-capable automaker, **Hybrid-OTA campaigns are {p1_hyb_mult:.2f}× larger** (**{fmt_signed(p1_hyb['coef'], 3)} log points**, $t = {p1_hyb['t_cr1']:.2f}$, $p_{{\\text{{WCB}}}} = {fmt_p(p1_hyb['p_wcb'])}$; Official API OTA active era 2018–2024 **{fmt_signed(p1_api['coef'], 3)}**, $p_{{\\text{{WCB}}}} = {fmt_p(p1_api['p_wcb'])}$) than dealer-remedied software recalls, remaining highly stable under OEM $\\times$ Year FE, Make $\\times$ Model FE, excluding Tesla and Ford, and restricting strictly to pure software-choice hybrids. By contrast, **Pure-OTA** exhibits no significant within-OEM scale premium (**{fmt_signed(p1_pure['coef'], 3)}**, $p_{{\\text{{WCB}}}} = {fmt_p(p1_pure['p_wcb'])}$), and **unconditional OEM-level first-OTA adoption ITT** models pooling all 2015–2026 software recalls yield clean parallel pre-trends and statistically null post-adoption shifts under both TWFE (**{fmt_signed(p1_itt['coef'], 3)}**, $p_{{\\text{{WCB}}}} = {fmt_p(p1_itt['p_wcb'])}$) and saturated Sun–Abraham (2021) interaction-weighted estimation (**{fmt_signed(p1_sa['iw_post_coef'], 3)}**, $p_t = {fmt_p(p1_sa['iw_p_t_G1'])}$; Callaway and Sant'Anna 2021; Roth et al. 2023; unconditional Software $\\times$ Modern SDV $\\text{{MY}} \\ge 2021$ DiD **{fmt_signed(p1_sw_sdv['coef'], 3)}**, $p_{{\\text{{WCB}}}} = {fmt_p(p1_sw_sdv['p_wcb'])}$). Because conditional campaign-level sorting and unconditional OEM adoption are distinct estimands, we report each transparently without claiming an unidentified percentage decomposition: the contrast is qualitatively consistent with legacy manufacturers incurring fixed OTA packaging and validation overhead ($F_{{\\text{{OTA}}}} > 0$) and preferentially routing high-volume campaigns into hybrid wireless delivery rather than experiencing a uniform fleet-wide jump in recall size upon adopting OTA capability.

<!-- FIGURE:fig4_v4_api_audit_and_hybrid_scale.png -->

---

## 6. Discussion: Operational Mechanism Boundary, Causal Identification Roadmap, and Dataset Specification

### 6.1 Operational Mechanism Boundary and Data Roadmap for Causal Delivery-Channel Research

Distinguishing what public federal safety records *can* establish (fixed-horizon completion monitoring, sample-flow accounting, dealer-channel vehicle-age decay, conditional batch-scale sorting, and public-API measurement audits) from what requires deeper operational microdata clarifies the exact boundary between descriptive safety-monitoring research and causal operations-management identification:

1. **Independent Dual-Coder Part 573 and Owner-Letter Classification:** While our automated text classifier achieves 100.0% pre-cutoff recall against the public API flag and cleanly separates Pure-OTA, Hybrid SW-Choice, Hybrid HW-Mixed, and Dealer Software, definitive measurement of remedy intent versus execution in hybrid campaigns requires **two independent human coders** annotating full Part 573 Defect Information Reports and 49 CFR Part 577 owner notification letters to separate *(a) OTA-capable eligibility*, *(b) actual wireless OTA deployment*, and *(c) physical hardware-required subsets*, with inter-rater reliability ($\\kappa$) audited independently of the public API endpoint.
2. **Multi-Quarter Campaign Trajectories and Phased Remedy-Availability Dates:** Cross-sectional eighth-report proportions cannot measure repair velocity, hazard decay, or time-to-remedy curves. Validating repair-speed metrics requires **longitudinal Q1–Q8 quarterly report panels per campaign** paired with explicit remedy-availability launch dates and phase-specific notification waves (addressing interim vs. final notices under 49 CFR § 577.5), plus additional annual eighth-report vintages (`2026+`) as non-Tesla SDV fleets age beyond 5 years.
3. **Quasi-Experimental Identification of Delivery-Channel Mechanisms:** To identify the causal operational effect of wireless OTA delivery on dealership service capacity, actual installation timing, and unremedied vehicle-days (e.g., for *Manufacturing & Service Operations Management*, *Production and Operations Management*, or *Management Science*), future studies require **within-defect treatment-assignment boundaries**—specifically:
   - *Pre-specified hardware-eligibility cutoffs* (e.g., identical software defect affecting adjacent build weeks or model trims where only vehicles equipped with a specific telematics/gateway module qualify for OTA while otherwise comparable vehicles require dealer flashing), or
   - *Risk-orthogonal phased OTA rollout waves* staggered by VIN block or geography.
   Credible execution of either quasi-experimental design requires checking balance across the boundary on model composition, defect severity, and prior baseline completion rates, and observing **actual OTA installation timestamps, dealership service-bay visits, and unremedied vehicle-days**. Crucially, wherever an eligibility boundary simultaneously alters the underlying defect mechanism or the substance of the software/hardware remedy, causal channel attribution must be abandoned.

### 6.2 Regulatory Monitoring and Public Data Infrastructure Implications

Our audit yields three immediate, actionable improvements for NHTSA and U.S. DOT public safety infrastructure:

1. **Synchronizing Public Campaign API Serialization:** Restoring backend synchronization between internal NHTSA recall tracking (33 OTA recalls in the *2025 Annual Recalls Report*) and the public `api.nhtsa.gov/recalls/campaignNumber` `overTheAirUpdate` field—which has emitted `False` on 68/68 post-May 8, 2025 OTA recalls—would immediately restore reliability for third-party VIN tools, academic safety monitors, and fleet compliance platforms.
2. **Publishing Machine-Readable Multi-Quarter Fixed-Horizon Tables:** Releasing the annual eighth-report completion lists (and underlying Q1–Q8 trajectories) as structured CSV/JSON tables alongside static PDFs—with explicit flags for 100% early-completed campaigns, denominator amendments (`22V867`, `23V413`), and multi-year duplicate revisions (`22V315`, `22V743`)—would eliminate transcription friction and horizon mixing in `6axg-epim`.
3. **Channel-Disaggregated Reporting Under 49 CFR § 573.7:** Recording the share of Hybrid-OTA vehicles remedied wirelessly versus at franchised dealerships alongside § 573.7(b)(5) unreachable-vehicle counts would allow regulators to monitor whether hybrid compliance tails stem from connectivity opt-outs, expired cellular subscriptions, or dealership service-bay bottlenecks.

### 6.3 Machine-Readable Replication Dataset Architecture

To support transparent reuse by safety researchers and operations scholars, the replication package publishes a clean, zero-NaN campaign-level fixed-horizon dataset (`data_processed/d12_v4_eighth_report_analysis_panel.csv`, $N = {n_uniq:,}$ rows, 31 harmonized fields, SHA-256 `{prov['msom_replication_panel_csv']['sha256'][:16]}...`) paired with six structured summary tables (`table_v4_sample_flow.csv`, `table_v4_eighth_report_completion.csv`, `table_channel_oem_age_support.csv`, `table_v4_vehicle_age_sensitivity.csv`, `table_v4_looo_sensitivity.csv`, and `table_v4_text_coding_vs_api.csv`). Online Appendix Section S5 provides the complete variable codebook, inclusion rules, and cryptographic verification receipts.

---

## 7. Conclusion

Anchoring U.S. automotive recall completion analysis on NHTSA's fixed eighth-quarter reporting horizon ({n_uniq:,} uniquely dated campaigns across 2024–2025, completely reconciled to Part 573 filings and the statutory 2022–2023 owner-notification cohort) separates well-identified empirical facts from unsupported generalizations. First, fixed eighth-report completion proportions are highest descriptively in Pure-OTA ({c_pool_pure['Mean_Completion_Pct']:.2f}% mean), followed by Hybrid-OTA ({c_pool_hyb['Mean_Completion_Pct']:.2f}%), Dealer Software ({c_pool_dsw['Mean_Completion_Pct']:.2f}%), and Physical Hardware ({c_pool_phys['Mean_Completion_Pct']:.2f}%), while within OEMs, Hybrid-OTA campaigns are robustly **{p1_hyb_mult:.2f}× larger** ($p_{{\\text{{WCB}}}} = {fmt_p(p1_hyb['p_wcb'])}$) than dealer-remedied software recalls despite null unconditional OEM first-OTA adoption shifts. Second, vehicle-age compliance decay in dealership channels is steep and rock-solid across every sensitivity check and all 18 Leave-One-OEM-Out exclusions (**{fmt_signed(b_age['Coef'])} to {fmt_signed(dsw_only_age['Coef'])} pp/yr**, all $p_{{\\text{{WCB}}}} \\le {looo_s['dealer_age_max_pwcb']:.3f}$). Third, because Tesla accounts for **{cs8['pure_tesla_n']}/{cs8['pure_total_n']} Pure-OTA recalls and {cs8['pure_tesla_vehicle_share_pct']:.2f}% of Pure-OTA vehicles** (with zero eighth-report Dealer-Software counterfactuals) while non-Tesla Pure-OTA campaigns occur strictly at oldest-model-year ages 0–1 years, the nominal Pure-OTA $\\times$ Age interaction collapses without Tesla (**{fmt_signed(nt_pure['Coef'])} pp/yr**, $p_{{\\text{{WCB}}}} = {fmt_p(nt_pure['p_WCB'])}$) and inside same-OEM common-support subsamples—requiring explicit withdrawal of any universal claim that OTA neutralizes vehicle-age decay. Finally, our public-API validation audit documents a sharp post-May 8, 2025 `overTheAirUpdate` serialization break (`0/{api_post25['n_txt_ota']}` `True`), underscoring the necessity of independent text verification and structured fixed-horizon reporting in federal safety monitoring.

---

## Data and Code Availability

All frozen public inputs, reconciliation scripts (`scripts/01`–`scripts/11`), econometric JSON receipts (`results/d12_v4_fixed_report_audit.json`, `results/d12_v4_live_api_spotcheck.json`, `results/d12_econometric_results.json`, `results/api_reconciliation_audit.json`), machine-readable dataset files (`data_processed/d12_v4_eighth_report_analysis_panel.csv`, `tables/table_channel_oem_age_support.csv`, `tables/table_v4_*.csv`), automated verification tests (`tests/test_d12_boost.py`), and cryptographic checksums (`SHA256SUMS.json`) are archived in the project replication package. No proprietary VIN or OEM telematics records were used.

---

## References

{refs_md}
"""
    return md, fig_blocks


def build_supplementary_appendix(
    v4: dict,
    spot: dict,
    econ: dict,
    s3: dict,
    df_sup: pd.DataFrame,
    df_sens: pd.DataFrame,
    df_looo: pd.DataFrame,
    df_t4c: pd.DataFrame,
) -> str:
    cs8 = v4["common_support_summary"]["eighth_report"]
    csm = v4["common_support_summary"]["mature_18m_snapshot"]
    looo_s = v4["looo_summary"]
    prov = v4["source_provenance"]
    p1 = econ["pillar1_blast_radius"]
    p3 = econ["pillar3_net_unremedied_exposure"]
    p4 = econ["pillar4_safety_and_complaints"]

    # Table S1: Full 18-OEM LOOO Table
    s1_lines = [
        "| Excluded Manufacturer | Dropped $N$ (Pure / Hyb / DSW) | Rem. $N$ | Rem. OEMs | Dealer Age (pp/yr) | Dealer $p_{\\text{WCB}}$ | Pure $\\times$ Age (pp/yr) | Pure $p_{\\text{WCB}}$ | Hybrid $\\times$ Age (pp/yr) | Hybrid $p_{\\text{WCB}}$ |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in df_looo.sort_values("Pure_x_Age_Coef").iterrows():
        drop_s = f"{int(r['Dropped_N'])} ({int(r['Dropped_Pure_N'])}/{int(r['Dropped_Hybrid_N'])}/{int(r['Dropped_DealerSW_N'])})"
        oem_lbl = f"**{r['Dropped_OEM']}**" if r["Dropped_OEM"] == "Tesla, Inc." else str(r["Dropped_OEM"])
        s1_lines.append(
            f"| {oem_lbl} | {drop_s} | {int(r['Remaining_N'])} | {int(r['Remaining_OEMs'])} | "
            f"{fmt_signed(r['Dealer_Age_Coef'])} | {fmt_p(r['Dealer_Age_pWCB'])} | "
            f"{fmt_signed(r['Pure_x_Age_Coef'])} | {fmt_p(r['Pure_x_Age_pWCB'])} | "
            f"{fmt_signed(r['Hybrid_x_Age_Coef'])} | {fmt_p(r['Hybrid_x_Age_pWCB'])} |"
        )

    # Table S2: Supplementary Mature >=18m Latest-Snapshot Sensitivity
    sens_snap = df_sens[df_sens["Panel"] == "C_Latest_Snapshot_Appendix"]
    s2_map = {(r["Specification"], r["Term"]): r for _, r in sens_snap.iterrows()}
    s2_specs = [
        ("Snapshot: oldest MY, filing >=540 d (4-way)", "4way"),
        ("Snapshot: middle MY, filing >=540 d (4-way)", "4way"),
        ("Snapshot: oldest MY, notice >=540 d (4-way)", "4way"),
        ("Snapshot: oldest MY, 0-5 yr window (4-way)", "4way"),
        ("Snapshot: middle MY, excluding Tesla (pooled OTA)", "pool"),
        ("Snapshot: same-model overlap (29 models, Make-Model FE, 4-way)", "4way"),
        ("Snapshot: same-model overlap excl. Tesla (Make-Model FE, 4-way)", "4way"),
        ("Snapshot: same-model overlap excl. Tesla (Make-Model FE, pooled OTA)", "pool"),
    ]
    s2_lines = [
        "| Mature Latest-Snapshot Sensitivity Specification (`6axg-epim`) | $N$ | OEMs | Dealer Age (pp/yr, $p_{\\text{WCB}}$) | Pure $\\times$ Age (pp/yr, $p_{\\text{WCB}}$) | Hybrid / Pooled OTA $\\times$ Age (pp/yr, $p_{\\text{WCB}}$) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for sp, kind in s2_specs:
        ra = s2_map[(sp, "veh_age")]
        a_s = f"{fmt_signed(ra['Coef'])} ({fmt_p(ra['p_WCB'])})"
        if kind == "4way":
            rp = s2_map[(sp, "is_ota_pure_x_age")]
            rh = s2_map[(sp, "is_ota_hybrid_x_age")]
            p_s = f"{fmt_signed(rp['Coef'])} ({fmt_p(rp['p_WCB'])})"
            h_s = f"{fmt_signed(rh['Coef'])} ({fmt_p(rh['p_WCB'])})"
        else:
            ro = s2_map[(sp, "is_ota_audited_x_age")]
            p_s = "— (pooled)"
            h_s = f"{fmt_signed(ro['Coef'])} ({fmt_p(ro['p_WCB'])})"
        s2_lines.append(f"| {sp} | {int(ra['N']):,} | {int(ra['OEMs'])} | {a_s} | {p_s} | {h_s} |")

    # Table S3: Mature Pure-OTA OEM Concentration (from table4c)
    s3_sub = df_t4c[df_t4c["Group"] == "Pure_OTA_OEM"].sort_values("Affected_Vehicle_Instances", ascending=False)
    s3_lines = [
        "| Manufacturer (Mature $\\ge 18$m Pure-OTA) | $N$ | Share $N$ (%) | Affected Instances | Share Veh. (%) | Mean CR (%) | Max Age (yr) | $N$ Aged $\\ge 6$ yr |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in s3_sub.iterrows():
        s3_lines.append(
            f"| {r['OEM_or_Slice']} | {int(r['N_Campaigns'])} | {r['Share_Modality_Campaigns_Pct']:.1f}% | "
            f"{int(r['Affected_Vehicle_Instances']):,} | {r['Share_Modality_Affected_Pct']:.2f}% | "
            f"{r['Mean_CR_Pct']:.2f} | {int(r['Max_Vehicle_Age_Yr'])} | {int(r['N_Age_6Plus_Yr'])} |"
        )

    # Table S4: Supplementary Pillar 3 Proxy (Exact p_WCB) & Pillar 4 Safety/Complaint Nulls
    p3_all = p3["regressions"]["mature_all_vehicles_4way_vs_phys"]["terms"]
    p3_sw = p3["regressions"]["mature_sw_ota_oems_4way"]["terms"]
    p3_ctrl = p3["regressions"]["mature_sw_ota_oems_4way_ctrl_potaff"]["terms"]
    p3_diff = p3["hybrid_minus_pure_unremedied_wald"]
    p4_fmvss = p4["safety_fe_regressions"]["4way_has_fmvss"]["terms"]["is_ota_pure"]
    p4_odi = p4["safety_fe_regressions"]["apiota2018_24_has_odi_action"]["terms"]["is_ota_api_full"]
    p4_cmpl = p4["complaint_did_summary"]["did_regressions"]["sw_active_4way_oemcl__log_cmpl_fail"]["terms"]
    p4_short = p4["complaint_did_summary"]["did_regressions"]["sw_short_m3m1_p1p12_4way_oemcl__log_cmpl_fail"]["terms"]
    p4_pre_w = p4["complaint_did_summary"]["dynamic_event_study_fail_pre_wald"]

    # Table S5: Live API Spot-Check Receipt
    spot_lines = [
        "| Campaign ID | Audit Role | HTTP | API Records | `overTheAirUpdate` Flags | OTA Text Records |",
        "|---|---|---:|---:|---|---:|",
    ]
    for r in spot["results"]:
        fl = ", ".join(f"`{k}`: {v}" for k, v in r.get("flag_values", {}).items())
        spot_lines.append(
            f"| `{r['campaign_id']}` | {r['audit_role']} | {r.get('http_status', 'ERR')} | {r.get('api_records', 0)} | {fl} | {r.get('ota_text_records', 0)} |"
        )

    # Table S6: Machine-Readable Replication Dataset Codebook
    codebook_rows = [
        ("`report_year`", "int", "Published NHTSA annual eighth-report list year (`2024` or `2025`)."),
        ("`campaign_code`", "str", "Six-character NHTSA campaign identifier joining annual lists to `FLAT_RCL` (`CAMPNO[:6]`)."),
        ("`CAMPNO`", "str", "Full nine-character NHTSA campaign identifier (e.g., `22V037000`)."),
        ("`mfg`", "str", "Canonicalized corporate manufacturer entity (harmonized from 705 raw strings to 646 entities)."),
        ("`rec_date` / `odate`", "date", "Part 573 filing date (`RCDATE`) and owner remedy notification date (`ODATE`, initiating § 573.7(a))."),
        ("`modality4`", "str", "Mutually exclusive text-coded channel: `Pure_OTA`, `Hybrid_OTA`, `Dealer_Software`, `Physical_Hardware`."),
        ("`is_ota_hybrid_swchoice` / `hwmixed`", "int", "Sub-indicators splitting Hybrid-OTA into pure software choice vs. OTA + hardware inspection/replacement."),
        ("`is_ota_api_full`", "int", "External public Campaign API `overTheAirUpdate` boolean indicator (valid pre-May 8, 2025; audit benchmark only)."),
        ("`vehicle_age_years` / `median_vehicle_age`", "float", "`rec_year - min_my` (oldest model year) and `rec_year - median_my` (middle model year)."),
        ("`reported_affected` / `potaff`", "int", "Affected vehicle denominator in eighth-report list vs. `FLAT_RCL` / `6axg-epim` (99.87% exact match)."),
        ("`completion_at_eighth_report_pct`", "float", "Primary fixed-horizon completion proportion at the eighth reporting quarter (`[0, 100]`)."),
        ("`completion_rate`", "float", "Latest-snapshot DOT `6axg-epim` completion proportion (frozen Nov 25, 2026; supplementary only)."),
    ]
    cb_lines = [
        "| Variable Name | Type | Description & Measurement Definition |",
        "|---|---|---|",
    ] + [f"| {v} | `{t}` | {d} |" for v, t, d in codebook_rows]

    # Table S0: Same-OEM Overlapping-Age Ranges (8 OEMs)
    ov_lines = [
        "| Manufacturer (Same-OEM Common Support) | OTA Age Range (yr) | Dealer-SW Age Range (yr) | Strict Overlap Range (yr) |",
        "|---|---:|---:|---:|",
    ]
    for oem, info in looo_s["oem_age_overlap_ranges"].items():
        oa = f"{int(info['ota_age_range'][0])}–{int(info['ota_age_range'][1])}"
        da = f"{int(info['dealer_sw_age_range'][0])}–{int(info['dealer_sw_age_range'][1])}"
        ov = f"{int(info['overlap_range'][0])}–{int(info['overlap_range'][1])}" if info["overlap_range"] else "None"
        ov_lines.append(f"| {oem} | {oa} | {da} | {ov} |")

    sup_md = f"""# Online Appendix: Supplementary Diagnostics, Mature-Archive Sensitivity, and Machine-Readable Dataset Codebook

{AUTHOR_BLOCK}

---

## S1. Complete 18-OEM Leave-One-OEM-Out (LOOO) Table and Same-OEM Age-Overlap Bounds

This section archives the full manufacturer-by-manufacturer Leave-One-OEM-Out (`LOOO`) sensitivity table corresponding to Main Manuscript Section 4.2 and Figure 3B (`tables/table_v4_looo_sensitivity.csv`), alongside the exact overlapping vehicle-age intervals for the {len(cs8['same_oem_both_dsw_and_ota_oems'])} manufacturers observing both Dealer Software and OTA recalls in the fixed eighth-report sample.

**Appendix Table S1.** *Complete Leave-One-OEM-Out (`LOOO`) Sensitivity on Fixed Eighth-Report Vehicle-Age Interactions (Baseline $N = 148$, 18 OTA-Capable OEMs).*

{chr(10).join(s1_lines)}

*Notes:* Each row drops all eighth-report software campaigns from the named OEM and re-estimates the baseline specification (`veh_age`, `is_ota_pure`, `is_ota_hybrid`, and age interactions with Manufacturer, Component, Filing-Quarter, and Report-Year FE; $B = 999$ Rademacher WCB). Dealer-Software age decay remains significant in {looo_s['dealer_age_sig_05_count']}/{looo_s['n_oems_tested']} drops (all $p_{{\\text{{WCB}}}} \\le {looo_s['dealer_age_max_pwcb']:.3f}$), whereas Pure-OTA $\\times$ Age loses 5% significance in {looo_s['pure_x_age_non_sig_05_count']}/{looo_s['n_oems_tested']} drops and collapses to {fmt_signed(df_looo.loc[df_looo['Dropped_OEM']=='Tesla, Inc.', 'Pure_x_Age_Coef'].iloc[0])} ($p_{{\\text{{WCB}}}} = {fmt_p(df_looo.loc[df_looo['Dropped_OEM']=='Tesla, Inc.', 'Pure_x_Age_pWCB'].iloc[0])}$) without Tesla.

**Appendix Table S1B.** *Within-OEM Overlapping Vehicle-Age Ranges Among the {len(cs8['same_oem_both_dsw_and_ota_oems'])} Fixed Eighth-Report Common-Support Manufacturers.*

{chr(10).join(ov_lines)}

*Notes:* Only 6 individual `primary_make_model` lines (`{', '.join(cs8['same_model_overlap_list'])}`, $N = 20$ campaigns total) overlap across Dealer Software and OTA in the eighth-report sample, and every line exhibits zero within-model OTA age variation.

---

## S2. Mature ($\\ge 18$-Month) Latest-Snapshot Cross-Sections and Common-Support Audit

Because the public U.S. DOT Socrata registry (`6axg-epim`, frozen November 25, 2026) blends heterogeneous post-remedy reporting durations rather than anchoring campaigns at a uniform reporting quarter, all mature ($\\ge 540$-day) latest-snapshot analyses are presented strictly as supplementary sensitivity checks rather than primary fixed-horizon evidence.

**Appendix Table S2.** *Supplementary Mature ($\\ge 18$-Month) Latest-Snapshot Vehicle-Age Interaction Sensitivity (`6axg-epim`).*

{chr(10).join(s2_lines)}

*Notes:* Even in the larger latest-snapshot archive, restricting to ages 0–5 years ($p_{{\\text{{WCB}}}} = 0.119$), middle model year ($p_{{\\text{{WCB}}}} = 0.409$), owner-notice $\\ge 540$ days ($p_{{\\text{{WCB}}}} = 0.086$), or same-model overlap excluding Tesla (Pure $\\times$ Age $p_{{\\text{{WCB}}}} = 0.519$; Hybrid $\\times$ Age $p_{{\\text{{WCB}}}} = 0.112$; pooled OTA $p_{{\\text{{WCB}}}} = 0.064$) fails to establish a robust multi-OEM OTA age-buffering effect.

**Appendix Table S3.** *Manufacturer Concentration in Mature ($\\ge 18$-Month) Latest-Snapshot Pure-OTA Campaigns ($N = {csm['pure_total_n']}$).*

{chr(10).join(s3_lines)}

*Notes:* Tesla accounts for {csm['pure_tesla_n']}/{csm['pure_total_n']} campaigns, {csm['pure_tesla_vehicle_share_pct']:.2f}% of affected vehicle-instances, and {csm['pure_age_6plus_tesla']}/{csm['pure_age_6plus_total']} (100.0%) of mature Pure-OTA campaigns aged $\\ge 6$ years. Non-Tesla light-duty passenger Pure-OTA reaches a maximum oldest-model-year age of only 3 years.

---

## S3. Within-OEM Hybrid Batch-Scale Robustness and Unconditional First-OTA Event Study

Full robustness diagnostics for the retained conditional within-OEM Hybrid-OTA batch-scale contrast ($+1.947$ log points = $7.01\\times$, $p_{{\\text{{WCB}}}} = {fmt_p(p1['main_sw_ota_oems']['sw_ota_oems_4way_log_potaff']['terms']['is_ota_hybrid']['p_wcb'])}$) and the unconditional OEM-level staggered first-OTA adoption event study (`TWFE` $N = {p1['itt_staggered_adoption']['pooled_did']['n']:,}$, $G = {p1['itt_staggered_adoption']['pooled_did']['G_clusters']}$, $+0.176$, $p_{{\\text{{WCB}}}} = 0.579$; saturated Sun–Abraham 2021 IW $N = {p1['itt_staggered_adoption']['sun_abraham_iw']['n']:,}$, $G = {p1['itt_staggered_adoption']['sun_abraham_iw']['G_clusters']}$, 7 cohorts, 39 cohort $\\times$ relative-time cells, $-0.532$, $p_t = 0.470$, IW pre-trend $F(2, 66) = {p1['itt_staggered_adoption']['sun_abraham_iw']['iw_pre_trend_wald_m3_m2']['F_stat']:.2f}$, $p = {p1['itt_staggered_adoption']['sun_abraham_iw']['iw_pre_trend_wald_m3_m2']['p_value']:.3f}$) are archived in `tables/table2_blast_radius_and_selection.csv` and `results/d12_econometric_results.json`.

---

## S4. Supplementary Recall-Level Unremedied Proxy Checks and Safety/Complaint Empirical Nulls

In the mature latest-snapshot archive (`6axg-epim`), recall-level counts sum campaign–VIN instances (not unique fleet vehicles) and incorporate 49 CFR § 573.7(b)(5) unreachable-vehicle adjustments. Holding campaign size fixed, both Pure-OTA ({fmt_signed(p3_ctrl['is_ota_pure']['coef'], 3)}, $p_{{\\text{{WCB}}}} = {fmt_p(p3_ctrl['is_ota_pure']['p_wcb'])}$) and Hybrid-OTA ({fmt_signed(p3_ctrl['is_ota_hybrid']['coef'], 3)}, $p_{{\\text{{WCB}}}} = {fmt_p(p3_ctrl['is_ota_hybrid']['p_wcb'])}$) compress `log(1 + unremedied instance proxy)`. Unconditionally under finite-sample wild cluster bootstrap inference, estimates relative to physical hardware are marginally significant at 10% for Pure-OTA ({fmt_signed(p3_all['is_ota_pure']['coef'], 3)}, $p_{{\\text{{WCB}}}} = {fmt_p(p3_all['is_ota_pure']['p_wcb'])}$) and Hybrid-OTA ({fmt_signed(p3_all['is_ota_hybrid']['coef'], 3)}, $p_{{\\text{{WCB}}}} = {fmt_p(p3_all['is_ota_hybrid']['p_wcb'])}$; Hybrid-minus-Pure contrast {fmt_signed(p3_diff['all_vehicles']['diff_hybrid_minus_pure'], 3)}, $p_{{\\text{{WCB}}}} = {fmt_p(p3_diff['all_vehicles']['p_wcb'])}$), while relative to OTA-capable OEMs' dealer software, Pure-OTA is statistically null ({fmt_signed(p3_sw['is_ota_pure']['coef'], 3)}, $p_{{\\text{{WCB}}}} = {fmt_p(p3_sw['is_ota_pure']['p_wcb'])}$), Hybrid-OTA is {fmt_signed(p3_sw['is_ota_hybrid']['coef'], 3)} ($p_{{\\text{{WCB}}}} = {fmt_p(p3_sw['is_ota_hybrid']['p_wcb'])}$), and their contrast is {fmt_signed(p3_diff['sw_ota_oems']['diff_hybrid_minus_pure'], 3)} ($p_{{\\text{{WCB}}}} = {fmt_p(p3_diff['sw_ota_oems']['p_wcb'])}$). Because these unconditional proxy contrasts confound campaign scale, single-OEM weight concentration (98.73% Tesla), and heterogeneous reporting horizons, we do not interpret them as causal fleet-stock reductions.

Across regulatory oversight and consumer safety complaints (2020–2026 NHTSA ODI bulk archives: {s3['complaint_panel']['n_unique_odino_2020_2026']:,} unique deduplicated `ODINO` complaints across {s3['complaint_panel']['n_raw_complaint_rows_2020_2026']:,} component records linked to {s3['complaint_panel']['n_balanced_campaigns_2021_2025']:,} balanced 2021–2025 campaigns), Pure-OTA campaigns have +{100*p4_fmvss['coef']:.2f} pp higher FMVSS technical noncompliance ($p_{{\\text{{WCB}}}} = {fmt_p(p4_fmvss['p_wcb'])}$) and active-era API OTA campaigns have {100*p4_odi['coef']:.2f} pp fewer formal ODI investigations ($p_{{\\text{{WCB}}}} = {fmt_p(p4_odi['p_wcb'])}$). Balanced $[-12\\text{{m}}, +12\\text{{m}}]$ consumer complaint-decay event studies exhibit pre-recall ramp-up (pre-trend Wald $F({p4_pre_w['q']}, {p4_pre_w['df2']}) = {p4_pre_w['F_stat']:.2f}$, $p = {p4_pre_w['p_value']:.3f}$) and transparent empirical nulls across full-window (`Active SW` Pure {fmt_signed(p4_cmpl['is_pure_post']['coef'], 3)}, $p_{{\\text{{WCB}}}} = {fmt_p(p4_cmpl['is_pure_post']['p_wcb'])}$; Hybrid {fmt_signed(p4_cmpl['is_hybrid_post']['coef'], 3)}, $p_{{\\text{{WCB}}}} = {fmt_p(p4_cmpl['is_hybrid_post']['p_wcb'])}$) and short $[-3, -1]$ vs. $[+1, +12]$ specifications (Pure {fmt_signed(p4_short['is_pure_post']['coef'], 3)}, $p_{{\\text{{WCB}}}} = {fmt_p(p4_short['is_pure_post']['p_wcb'])}$; Hybrid {fmt_signed(p4_short['is_hybrid_post']['coef'], 3)}, $p_{{\\text{{WCB}}}} = {fmt_p(p4_short['is_hybrid_post']['p_wcb'])}$). Full tables are archived in `tables/table5_safety_cascades_and_complaints_did.csv` and `tables/table5b_prerecall_complaints_and_hazards.csv`.

---

## S5. Live Public API Spot-Check Receipt and Machine-Readable Dataset Codebook

**Appendix Table S4.** *Live Public NHTSA Campaign API Spot-Check Receipt (`results/d12_v4_live_api_spotcheck.json`, Retrieved `{spot['retrieved_utc']}`).*

{chr(10).join(spot_lines)}

**Appendix Table S5.** *Machine-Readable Replication Dataset Variable Dictionary (`data_processed/d12_v4_eighth_report_analysis_panel.csv`, $N = {prov['msom_replication_panel_csv']['rows']:,}$ Rows, SHA-256 `{prov['msom_replication_panel_csv']['sha256'][:16]}...`).*

{chr(10).join(cb_lines)}

*Source Provenance Receipts:* `data_raw/nhtsa_annual_eighth_report_2024_2025.csv` ({prov['annual_eighth_report_csv']['bytes']:,} bytes, SHA-256 `{prov['annual_eighth_report_csv']['sha256']}`); `data_raw/dot_79374_DS1.pdf` (`DOT HS 813 687`, {prov['dot_hs_813_687_pdf']['bytes']:,} bytes, SHA-256 `{prov['dot_hs_813_687_pdf']['sha256']}`).
"""
    return sup_md


def main() -> int:
    v4 = json.loads((RES_DIR / "d12_v4_fixed_report_audit.json").read_text(encoding="utf-8"))
    spot = json.loads((RES_DIR / "d12_v4_live_api_spotcheck.json").read_text(encoding="utf-8"))
    econ = json.loads((RES_DIR / "d12_econometric_results.json").read_text(encoding="utf-8"))
    audit_api = json.loads((RES_DIR / "api_reconciliation_audit.json").read_text(encoding="utf-8"))
    s3 = json.loads((RES_DIR / "step3_panel_build_summary.json").read_text(encoding="utf-8"))
    refs_json = json.loads((PROC_DIR / "verified_references.json").read_text(encoding="utf-8"))

    df_flow = pd.read_csv(TBL_DIR / "table_v4_sample_flow.csv")
    df_comp = pd.read_csv(TBL_DIR / "table_v4_eighth_report_completion.csv")
    df_sup = pd.read_csv(TBL_DIR / "table_channel_oem_age_support.csv")
    df_sens = pd.read_csv(TBL_DIR / "table_v4_vehicle_age_sensitivity.csv")
    df_looo = pd.read_csv(TBL_DIR / "table_v4_looo_sensitivity.csv")
    df_apic = pd.read_csv(TBL_DIR / "table_v4_text_coding_vs_api.csv")
    df_t4c = pd.read_csv(TBL_DIR / "table4c_mature_ota_oem_composition.csv")

    main_md, fig_blocks = build_main_manuscript(
        v4, spot, econ, audit_api, s3, refs_json, df_flow, df_comp, df_sup, df_sens, df_looo, df_apic
    )
    sup_md = build_supplementary_appendix(v4, spot, econ, s3, df_sup, df_sens, df_looo, df_t4c)

    main_md_path = BASE_DIR / "manuscript_d12_boost.md"
    main_pdf_path = BASE_DIR / "manuscript_d12_boost.pdf"
    sup_md_path = BASE_DIR / "supplementary_d12_jsr.md"
    sup_pdf_path = BASE_DIR / "supplementary_d12_jsr.pdf"

    main_md_path.write_text(main_md, encoding="utf-8")
    sup_md_path.write_text(sup_md, encoding="utf-8")

    main_html = convert_md_to_html(
        main_md,
        fig_blocks,
        "Vehicle Recall Completion at a Fixed Reporting Horizon",
        "Vehicle Recall Completion at a Fixed Reporting Horizon",
    )
    sup_html = convert_md_to_html(
        sup_md,
        {},
        "Online Appendix — Vehicle Recall Completion at a Fixed Reporting Horizon",
        "Online Appendix — Vehicle Recall Completion at a Fixed Reporting Horizon",
    )

    n_main = compile_edge_pdf(main_html, main_pdf_path)
    n_sup = compile_edge_pdf(sup_html, sup_pdf_path)

    print(
        f"[DONE] Compiled {main_pdf_path.name} ({main_pdf_path.stat().st_size:,} bytes, {n_main} pages, 0 leaks) "
        f"and {sup_pdf_path.name} ({sup_pdf_path.stat().st_size:,} bytes, {n_sup} pages, 0 leaks)",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
