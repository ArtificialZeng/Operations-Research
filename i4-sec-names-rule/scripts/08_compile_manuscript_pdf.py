"""Pillar 8 (v4): Compile Zero-Leak Publication PDFs via Microsoft Edge (--headless=new)
for BOTH manuscript_i4_boost.pdf AND supplementary_i4_jbf.pdf.

Uses a fresh temporary --user-data-dir profile (never touches active browser profiles),
embeds high-resolution 300 DPI PNG figures inline, formats LaTeX math cleanly into HTML
entities/typography, and runs automated zero-leak text verification via pypdf.
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

BASE_DIR = Path(__file__).resolve().parents[1]
EDGE_CANDIDATES = [
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
]


def build_figure_blocks() -> dict[str, tuple[str, str]]:
    return {
        "fig1_statutory_timing_and_concentration.png": (
            "Figure 1. Label Concentration, Early Timing Relative to Release 33-11368, and Per-Fund EDGAR Disclosure Taxonomy.",
            "Panel A compares multi-asset GVI rename categories by fund count and prior-report assets, with and without Vanguard (which represents 96.2% of numeric-ratio assets). Panel B plots Pass-2 verified effective months across all 50 renamers relative to the June 11, 2026 large-group on-cycle start (49/50 precede June 11; 36/50 do not reach statutory on-cycle updates until 2027). Panel C reports the per-fund EDGAR statutory disclosure classification by fund share and AUM share.",
        ),
        "fig2_event_study_placebos_and_honest_did.png": (
            "Figure 2. Quarterly Event-Study Phases, Counterfactual Placebo Forest Plot, and Rambachan–Roth (2023) Sensitivity Bounds.",
            "Panel A plots quarterly exit-rate contrasts relative to 2023Q2 with shaded Announcement (2023Q3–2024Q4), Early Response (2025Q1–2026Q1), and On-Cycle Start (2026Q2–2026Q3) windows, explicitly annotating joint pre-trend rejections in the Growth/Value lexical screen (FAQ2 p = 0.043; FAQ4 p = 0.003). Panel B contrasts observed 2025–2026 estimates with pre-rule historical placebos (2021–2022) and unregulated-word renaming placebos (all 95% CR1 CIs). Panel C displays Rambachan–Roth (2023) Delta-RM robust 95% intervals and exact breakdown values.",
        ),
        "fig3_lookthrough_paths_and_partial_id_bounds.png": (
            "Figure 3. Repaired Multi-Quarter Portfolio Trajectories and Full Partial-Identification Sensitivity Bounds.",
            "Panel A tracks repaired zero-leakage look-through largest-class weights across four historical N-PORT snapshots (2023Q2, 2024Q2, 2025Q2, 2026Q2/Q3) for renamed versus retained funds in the below-80% GVI sample, annotating drift-adjusted differences at each snapshot. Panel B compares repaired point estimates, fund-return-calibrated drift, crosser-deleted samples, sharp Manski partial-identification sets (thick bars), and outer 95% confidence intervals (thin whiskers) across all 2,502 paired GVI and 1,550 GV-screen funds.",
        ),
        "fig4_exploratory_monthly_flows.png": (
            "Figure 4. Exploratory Monthly Investor-Flow Trajectories and Gross Sales/Redemptions Decomposition.",
            "Panel A plots centered monthly net-flow contrasts (m = -12 to +12) for non-numeric (n = 42) and numeric-ratio (n = 7 across 3 complexes) renamers. Panel B reports pooled TWFE net-flow, gross-sales, and gross-redemption contrasts with 95% CR1 CIs. Estimates are strictly exploratory descriptive evidence and do not identify investor comprehension or welfare.",
        ),
        "figA1_redemption_sign_audit.png": (
            "Figure A1. Form N-PORT Negative-Redemption Sign Incidence and Flow Concordance Validation.",
            "Panel A shows the incidence of negative redemption entries across N-PORT monthly fields MON1–MON3 (18.61% of non-missing records). Panel B displays Pearson and Spearman agreement with asset-and-return-implied flows before (r = 0.088) and after (r = 0.955) taking absolute redemption magnitudes across 299,416 fund-quarters.",
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
    s = s.replace(r"\$", "$")

    while r"\frac{" in s:
        idx = s.index(r"\frac{")
        num, nxt = _extract_braced(s, idx + len(r"\frac"))
        den, end = _extract_braced(s, nxt) if nxt < len(s) and s[nxt] == "{" else ("", nxt)
        n_clean, d_clean = num.strip(), den.strip()
        if not re.search(r"[+\-= ]", n_clean) and not re.search(r"[+\-= ]", d_clean):
            frac_repl = f"{n_clean}/{d_clean}"
        else:
            frac_repl = f"({n_clean}) / ({d_clean})"
        s = s[:idx] + frac_repl + s[end:]

    macro_wrappers = [
        (r"\text{", '<span class="rm">', "</span>"),
        (r"\mathrm{", '<span class="rm">', "</span>"),
        (r"\mathcal{", '<span class="cal">', "</span>"),
        (r"\mathbb{", '<span class="rm"><b>', "</b></span>"),
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

    s = s.replace(r"\_", "&#95;")

    replacements = [
        (r"{,}", ","),
        (r"\qquad", "&emsp;&emsp;"),
        (r"\quad", "&emsp;"),
        (r"\iff", "&hArr;"),
        (r"\Rightarrow", "&rArr;"),
        (r"\times", "&times;"),
        (r"\cdot", "&middot;"),
        (r"\pm", "&plusmn;"),
        (r"\le", "&le;"),
        (r"\ge", "&ge;"),
        (r"\neq", "&ne;"),
        (r"\approx", "&approx;"),
        (r"\to", "&rarr;"),
        (r"\in", "&isin;"),
        (r"\beta", "&beta;"),
        (r"\alpha", "&alpha;"),
        (r"\delta", "&delta;"),
        (r"\rho", "&rho;"),
        (r"\mu", "&mu;"),
        (r"\Delta", "&Delta;"),
        (r"\sigma", "&sigma;"),
        (r"\%", "%"),
        (r"\{", "{"),
        (r"\}", "}"),
        (r"\|", "|"),
        (r"\ldots", "&hellip;"),
        (r"\dots", "&hellip;"),
        (r"\;", "&ensp;"),
        (r"\,", "&thinsp;"),
        (r"\!", ""),
        (r"\ ", " "),
        ("--", "&ndash;"),
    ]
    for old, new in replacements:
        s = s.replace(old, new)

    for _ in range(3):
        for sym, tag in [("_", "sub"), ("^", "sup")]:
            while f"{sym}{{" in s:
                idx = s.index(f"{sym}{{")
                inner, end = _extract_braced(s, idx + 1)
                s = s[:idx] + f"<{tag}>{inner}</{tag}>" + s[end:]

    s = re.sub(r"(?<![A-Za-z0-9])_([A-Za-z0-9+\-]+|&[a-z]+;)", r"<sub>\1</sub>", s)
    s = re.sub(r"([A-Za-z0-9>])_([A-Za-z0-9]+)\b", r"\1<sub>\2</sub>", s)
    s = re.sub(r"\^([A-Za-z0-9+\-*]+)", r"<sup>\1</sup>", s)

    parts = re.split(r"(<[^>]+>)", s)
    for i in range(0, len(parts), 2):
        parts[i] = re.sub(r"(?<![&a-zA-Z])-(?![a-zA-Z]*;)", "&minus;", parts[i])
    return "".join(parts)


def _inline_md(text: str) -> str:
    tokens: list[str] = []

    def stash(html_frag: str) -> str:
        idx = len(tokens)
        tokens.append(html_frag)
        return f"\x00TOK{idx}\x00"

    text = re.sub(r"`([^`]+)`", lambda m: stash(f"<code>{html.escape(m.group(1))}</code>"), text)
    text = text.replace(r"\$", "\x00DOLLAR\x00")
    # Protect currency amounts like $117.63B, $1B, $44.31T so two dollar amounts never trigger math mode!
    text = re.sub(r"\$(?=\d)", "\x00DOLLAR\x00", text)
    text = re.sub(
        r"\$([^$\n]+)\$",
        lambda m: stash(
            f'<span class="math">{_tex_to_html(m.group(1).replace(chr(0) + "DOLLAR" + chr(0), r"\$"))}</span>'
        ),
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


def _embed_figure_html(fname: str, figure_blocks: dict[str, tuple[str, str]]) -> str:
    img_path = BASE_DIR / "figures" / fname
    b64 = base64.b64encode(img_path.read_bytes()).decode("ascii")
    title_html, caption_html = figure_blocks[fname]
    alt_txt = re.sub(r"<[^>]+>", "", title_html)
    return (
        f'<figure class="pub-fig">'
        f'<img src="data:image/png;base64,{b64}" alt="{html.escape(alt_txt)}" />'
        f"<figcaption><strong>{title_html}</strong> {caption_html}</figcaption>"
        f"</figure>"
    )


def convert_md_to_html(md_text: str, figure_blocks: dict[str, tuple[str, str]], running_head: str) -> str:
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
            if fname in figure_blocks and fname not in inserted_figs:
                body.append(_embed_figure_html(fname, figure_blocks))
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

            def split_md_row(row_s: str) -> list[str]:
                tmp = row_s.strip("|").replace(r"\|", "\x00PIPE\x00")
                return [c.replace("\x00PIPE\x00", r"\|").strip() for c in tmp.split("|")]

            headers = split_md_row(tbl_lines[0])
            aligns = split_md_row(tbl_lines[1])
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
                cells = split_md_row(rln)
                tds = "".join(
                    f'<td class="{col_cls[idx] if idx < len(col_cls) else "left"}">{_inline_md(c)}</td>'
                    for idx, c in enumerate(cells)
                )
                rows_html.append(f"<tr>{tds}</tr>")
            # Allow long appendix tables (>15 rows) to break cleanly across pages with repeated thead
            wrap_cls = "table-wrap-long" if len(rows_html) > 15 else "table-wrap"
            body.append(
                f'<div class="{wrap_cls}"><table><thead><tr>{th_html}</tr></thead>'
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
            is_refs = bool(body and "<h2>References</h2>" in body[-1])
            cls_attr = ' class="refs-list"' if is_refs else ""
            body.append(f"<ol{cls_attr}{start_attr}>{''.join(items)}</ol>")
            continue

        para_raw_lines = [ln]
        i += 1
        while i < n:
            nxt_raw = lines[i]
            nxt = nxt_raw.strip()
            if (
                not nxt
                or nxt == "---"
                or nxt.startswith(("#", "|", "- ", "$$", "<!--"))
                or re.match(r"^\d+\.\s+", nxt)
            ):
                break
            para_raw_lines.append(nxt_raw)
            i += 1
        para_first = para_raw_lines[0].strip()
        p_cls = (
            ' class="table-caption"'
            if para_first.startswith("**Table ")
            else (' class="table-notes"' if para_first.startswith(("*Notes:*", "*Source:*")) else "")
        )
        segs: list[str] = []
        cur_seg: list[str] = []
        for raw_l in para_raw_lines:
            cur_seg.append(raw_l.strip())
            if raw_l.endswith("  "):
                segs.append(_inline_md(" ".join(cur_seg)))
                cur_seg = []
        if cur_seg:
            segs.append(_inline_md(" ".join(cur_seg)))
        body.append(f"<p{p_cls}>{'<br />'.join(segs)}</p>")

    css = f"""
    @page {{
      size: letter;
      margin: 0.65in 0.65in 0.72in 0.65in;
      @top-right {{
        content: "{running_head}";
        font-family: Georgia, "Times New Roman", serif;
        font-size: 7.3pt;
        color: #555;
      }}
      @bottom-center {{
        content: "Page " counter(page) " of " counter(pages);
        font-family: Georgia, "Times New Roman", serif;
        font-size: 7.9pt;
        color: #555;
      }}
    }}
    @page :first {{ @top-right {{ content: normal; }} }}
    body {{
      font-family: Georgia, "Times New Roman", serif;
      font-size: 9.2pt;
      line-height: 1.42;
      color: #1a1a1a;
      max-width: 100%;
    }}
    h1.paper-title {{
      font-size: 13.6pt;
      line-height: 1.24;
      margin: 0 0 8pt 0;
      color: #0b2545;
      border-bottom: 1.5pt solid #0b2545;
      padding-bottom: 6pt;
    }}
    h2 {{
      font-size: 10.9pt;
      color: #0b2545;
      margin: 11pt 0 5pt 0;
      border-bottom: 0.6pt solid #cbd5e1;
      padding-bottom: 2pt;
      page-break-after: avoid;
    }}
    h3 {{
      font-size: 9.7pt;
      color: #1e3a5f;
      margin: 8.5pt 0 4pt 0;
      page-break-after: avoid;
    }}
    p {{ margin: 0 0 5.3pt 0; text-align: justify; }}
    p.table-caption {{
      font-size: 8.4pt;
      margin: 7pt 0 3pt 0;
      color: #0b2545;
      text-align: left;
      break-inside: avoid;
      page-break-inside: avoid;
      break-after: avoid;
      page-break-after: avoid;
    }}
    p.table-notes {{
      font-size: 7.4pt;
      color: #475569;
      margin: 2pt 0 8pt 0;
      text-align: left;
    }}
    ul, ol {{ margin: 3pt 0 6pt 16pt; padding: 0; }}
    li {{ margin: 0 0 2.6pt 0; text-align: justify; }}
    ol.refs-list li {{ text-align: left; font-size: 7.9pt; line-height: 1.30; break-inside: avoid; page-break-inside: avoid; }}
    code {{
      font-family: Consolas, "Courier New", monospace;
      font-size: 7.2pt;
      background: #f1f5f9;
      padding: 0.4pt 2.0pt;
      border-radius: 2pt;
    }}
    hr {{ border: 0; border-top: 0.6pt solid #cbd5e1; margin: 7.5pt 0; }}
    .math {{ font-family: "Cambria Math", Georgia, serif; font-style: italic; }}
    .math .rm {{ font-style: normal; }}
    sup, sub {{ white-space: nowrap; }}
    .table-wrap {{ margin: 4pt 0 4pt 0; page-break-inside: avoid; }}
    .table-wrap-long {{ margin: 4pt 0 4pt 0; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 6.4pt;
      line-height: 1.18;
      border-top: 1.3pt solid #0f172a;
      border-bottom: 1.3pt solid #0f172a;
    }}
    thead {{ display: table-header-group; }}
    tr {{ page-break-inside: avoid; }}
    thead tr {{ border-bottom: 0.8pt solid #334155; background: #f8fafc; }}
    th, td {{ padding: 1.8pt 2.3pt; vertical-align: top; }}
    td .math, th .math {{ white-space: nowrap; }}
    td code {{ white-space: nowrap; font-size: 6.0pt; }}
    tbody tr:nth-child(even) {{ background: #fbfdff; }}
    th.left, td.left {{ text-align: left; }}
    th.center, td.center {{ text-align: center; }}
    th.right, td.right {{ text-align: right; }}
    figure.pub-fig {{
      margin: 7.5pt 0 7.5pt 0;
      padding: 5pt;
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
      margin: 0 auto 4.5pt auto;
    }}
    figure.pub-fig figcaption {{
      font-size: 7.4pt;
      line-height: 1.28;
      color: #334155;
      text-align: left;
    }}
    """
    return (
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8' />"
        f"<title>{running_head}</title><style>{css}</style></head>"
        f"<body>{''.join(body)}</body></html>"
    )


def verify_pdf_zero_leaks(pdf_path: Path) -> tuple[int, list[str]]:
    reader = PdfReader(str(pdf_path))
    full_txt = "\n".join((p.extract_text() or "") for p in reader.pages)
    bad_patterns = [
        r"\\[A-Za-z]+",
        r"\\\$",
        r"\$\$",
        r"\*\*",
        r"\|---",
        r"\{,\}",
        r"\\text\{",
        r"\\mathbf\{",
        r"\\mathbb\{",
        r"\\frac\{",
        r"\\mathcal\{",
        r"\bp_WCB\b",
        r"fig[1-5A-Z0-9_]+\.png",
        r"<!--",
        r"TOK\d+",
        r"&[a-z]+;",
        r"&#\d+;",
        r"Target Venues|Target Format|Track A|Track B",
    ]
    leaks = []
    for pat in bad_patterns:
        if re.search(pat, full_txt):
            leaks.append(pat)
    return len(reader.pages), leaks


def render_doc(browser: str, md_path: Path, pdf_path: Path, running_head: str, figure_blocks: dict[str, tuple[str, str]]) -> int:
    md_text = md_path.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="i4-v4-pdf-") as temporary:
        temp = Path(temporary)
        html_path = temp / "doc.html"
        fresh_pdf = temp / "doc.pdf"
        html_path.write_text(convert_md_to_html(md_text, figure_blocks, running_head), encoding="utf-8")
        command = [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--user-data-dir={temp / 'profile'}",
            f"--print-to-pdf={fresh_pdf}",
            html_path.as_uri(),
        ]
        process = subprocess.run(command, capture_output=True, text=True, timeout=90, check=False)
        if process.returncode != 0 or not fresh_pdf.is_file():
            print(f"Renderer failed for {md_path.name}: {process.stderr}", file=sys.stderr)
            return 1
        pages, leaks = verify_pdf_zero_leaks(fresh_pdf)
        if leaks:
            print(f"Zero-leak audit FAILED for {md_path.name}: {leaks}", file=sys.stderr)
            return 2
        try:
            shutil.copyfile(fresh_pdf, pdf_path)
            target_written = pdf_path
        except PermissionError:
            fallback = pdf_path.with_name("manuscript_i4_jbf.pdf") if pdf_path.name == "manuscript_i4_boost.pdf" else pdf_path.with_stem(pdf_path.stem + "_fresh")
            shutil.copyfile(fresh_pdf, fallback)
            target_written = fallback
    print(f"[OK PDF] Compiled zero-leak PDF: {target_written.name} ({pages} pages, {target_written.stat().st_size:,} bytes)", flush=True)
    return 0


def main() -> int:
    browser = next((str(p) for p in EDGE_CANDIDATES if p.is_file()), None) or shutil.which("msedge") or shutil.which("chrome")
    if not browser:
        print("Microsoft Edge or Chromium is required to render the manuscript.", file=sys.stderr)
        return 1
    figs = build_figure_blocks()
    rc1 = render_doc(
        browser,
        BASE_DIR / "manuscript_i4_boost.md",
        BASE_DIR / "manuscript_i4_boost.pdf",
        "Manager Choice Under the 2023 SEC Names Rule Rollout",
        figs,
    )
    if rc1 != 0:
        return rc1
    rc2 = render_doc(
        browser,
        BASE_DIR / "supplementary_i4_jbf.md",
        BASE_DIR / "supplementary_i4_jbf.pdf",
        "Supplementary Information & Data Appendix (I4)",
        figs,
    )
    return rc2


if __name__ == "__main__":
    raise SystemExit(main())
