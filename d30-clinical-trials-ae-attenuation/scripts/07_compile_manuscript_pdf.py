"""Compile manuscript_d30_boost.md and supplementary_d30_jce.md with 300-DPI figures into PDFs.

Uses Microsoft Edge headless with an isolated temporary user-data-dir so compilation is
reproducible and never collides with an active browser profile.
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

BASE_DIR = Path(__file__).resolve().parents[1]
EDGE_EXE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

MAIN_FIGURES: dict[str, tuple[str, str]] = {
    "fig1_main_within_program_and_counterfactuals.png": (
        "Figure 1. Two-Way Alternative-Region Counterfactuals and Within-Program Replication (Per +10 pp EU-East Site Share).",
        (
            "Panel A shows exact Phase 3 Drug × Sponsor FE two-way counterfactuals (N = 1,282, 328 programs) "
            "contrasting +10 pp Eastern European EU site share replacing −10 pp of each comparator region "
            "(United States, North America, Western Europe EU/EEA, Western Europe & Dev., Latin America, Emerging Asia, "
            "Developed APAC/Israel, and Non-EU EE/RU-UA). Panel B verifies consistency across alternative fixed effects, "
            "documented AE time frames, dropping the top-10 weighted programs, strict 5% threshold, systematic assessment "
            "controls, terminated trials, Phase 2 OOS, and non-placebo active-comparator MRCTs. Finite-sample t(G−1) 95% CIs."
        ),
    ),
    "fig2_support_spline_and_weights.png": (
        "Figure 2. Observed [0%, 35%] Support Curve, Extensive vs. Intensive Margin Decomposition, and Effective FWL Weights.",
        (
            "Panel A plots Phase 3 Drug × Sponsor FE categorical bin contrasts and 4-knot Harrell restricted cubic splines "
            "strictly over observed [0%, 35%] support (95th percentile = 35.3%; Wald nonlinearity p = 0.548 placebo, p = 0.681 active) "
            "with background density histogram. Panel B compares support truncations, explicit zero-share indicator specifications, "
            "and exact common-236-program contrasts per +10 pp EU-East share. Panel C displays the top-10 Aronow–Samii effective FWL "
            "program weights (N_eff = 43.7 of 328 programs; top-10 = 32.0%) and leave-top-20-program-out stability."
        ),
    ),
    "fig3_meddra_fourstate_and_manski_bounds.png": (
        "Figure 3. Four-State MedDRA Cell Audit, Strict Zero-Fallback Paired Contrasts, and Sharp Manski FWL Bounds.",
        (
            "Panel A decomposes 166,260 trial-arm-term cells in the pre-defined 15+15 common MedDRA panel across reporting thresholds "
            "(0.0% left-censored in 0%-threshold trials vs. 69.0% left-censored in 5%-threshold trials). Panel B compares paired "
            "Subjective minus Objective / pure Investigations contrasts across legacy fallback, strict zero-fallback, zero-anomaly trials, "
            "fixed 5%, and uncensored 0% threshold strata. Panel C shows exact sharp Manski FWL identification intervals (thick bars) "
            "and Imbens–Manski 95% CIs (thin bars) for peak single-term SOC rates (72%–88% of trials point-identified)."
        ),
    ),
    "fig4_tost_equivalence_sae_mortality.png": (
        "Figure 4. Pre-Specified Clinical Equivalence (TOST) and Unified +10 pp Scale Comparison Across Registry Endpoints.",
        (
            "Panel A displays 90% TOST CIs (thick bars) and 95% CIs (thin bars) per +10 pp EU-East share against pre-specified "
            "clinical equivalence margins (±2.0 pp primary and ±1.0 pp strict for SAEs and within-trial RD; ±0.5 pp primary for "
            "all-cause mortality). SAEs and within-trial RD achieve equivalence at ±1.0–2.0 pp (all p_TOST <= 0.0032), whereas mortality "
            "fails equivalence at ±0.5 pp (p_TOST = 0.249–0.404). Panel B aligns all primary registry endpoints on a single +10 pp scale."
        ),
    ),
}

SI_FIGURES: dict[str, tuple[str, str]] = {
    "figS1_therapeutic_areas_and_accrual_bounds.png": (
        "Figure S1. Subgroup Consistency Across Therapeutic Areas and Simplex-Valid Site-to-Patient Accrual Calibration.",
        (
            "Panel A shows pooled P2+P3 Eastern European site-share slopes per +10 pp across all 9 major MeSH therapeutic areas "
            "(9/9 negative, 7/9 p < 0.05). Panel B plots simplex-preserving patient-share calibration across per-site accrual velocity "
            "ratios w in [0.5, 3.0] with empirical within-program velocity w_hat = 1.35x U.S. marked."
        ),
    ),
    "figS2_post2017_temporal_overlap.png": (
        "Figure S2. Descriptive Post-2017 Temporal Patterns and Overlapping Regulatory Regimes (Per +10 pp Site Share).",
        (
            "Panel A plots era-specific cross-sectional slopes (2005–2024). Panel B displays within-program 3-era shifts "
            "(2020–2024 EU-East p_WCB = 0.030 placebo, borderline 0.051 active) alongside joint FDAAA/ICH overlap terms "
            "(individually inseparable). Panel C tracks the post-2017 shift in 0% vs. 5% reporting thresholds."
        ),
    ),
    "figS3_war2022_all_registered_footprints.png": (
        "Figure S3. Uncensored All-Registered MRCT Footprints (2017–2025, N = 6,011) and Within-Sponsor Period Shifts.",
        (
            "Panel A compares all-registered Russia/Ukraine site participation (41.86% in 2019 to 6.10% in 2025; Russia 0.00%) "
            "against the right-censored results-posted subsample. Panel B displays uncensored within-sponsor post-2022 period shifts "
            "(out-of-sample exposure U.S. DiD = +0.33, p = 0.117, null)."
        ),
    ),
    "figS4_exploratory_openfda_faers.png": (
        "Figure S4. Exploratory Post-Approval FDA Labeling Supplements and FAERS Spontaneous-Reporting Audit (N = 229 Drugs).",
        (
            "Panel A shows descriptive pre-approval and post-approval percentages across pivotal EE-share bins. Panel B plots "
            "adjusted t-statistics (null band shaded). Hypothesis-generating only; FAERS lacks exposed-patient denominators "
            "and cannot estimate incidence rates or comparative risks."
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
        (r"\le", "&le;"),
        (r"\ge", "&ge;"),
        (r"\times", "&times;"),
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
        (r"\omega", "&omega;"),
        (r"\tau", "&tau;"),
        (r"\Phi", "&Phi;"),
        (r"\min", "min"),
        (r"\max", "max"),
        (r"\_", "_"),
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
    s = re.sub(r"_([A-Za-z0-9]+|&[a-z]+;)", r"<sub>\1</sub>", s)
    s = re.sub(r"\^([A-Za-z0-9]+)", r"<sup>\1</sup>", s)
    return s


def _inline_md(text: str) -> str:
    tokens: list[str] = []

    def stash(html_frag: str) -> str:
        idx = len(tokens)
        tokens.append(html_frag)
        return f"\x00TOK{idx}\x00"

    text = re.sub(
        r"`([^`]+)`",
        lambda m: stash(f"<code>{html.escape(m.group(1))}</code>"),
        text,
    )
    text = re.sub(
        r"\$([^$\n]+)\$",
        lambda m: stash(f'<span class="math">{_tex_to_html(m.group(1))}</span>'),
        text,
    )
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*\*([^*]+?)\*\*\*", r"<strong><em>\1</em></strong>", escaped)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<em>\1</em>", escaped)
    for i, frag in enumerate(tokens):
        escaped = escaped.replace(f"\x00TOK{i}\x00", frag)
    return escaped


def _embed_figure_html(fname: str, fig_map: dict[str, tuple[str, str]]) -> str:
    img_path = BASE_DIR / "figures" / fname
    b64 = base64.b64encode(img_path.read_bytes()).decode("ascii")
    title, caption = fig_map[fname]
    return (
        f'<figure class="pub-fig">'
        f'<img src="data:image/png;base64,{b64}" alt="{html.escape(title)}" />'
        f"<figcaption><strong>{html.escape(title)}</strong> {html.escape(caption)}</figcaption>"
        f"</figure>"
    )


def convert_md_to_html(
    md_text: str,
    fig_map: dict[str, tuple[str, str]] | None = None,
    running_header: str = "Geographic Site Mix and Registered Non-Serious Adverse Events (JCE v4)",
    doc_title: str = "D30 Manuscript (JCE v4)",
) -> str:
    if fig_map is None:
        fig_map = MAIN_FIGURES
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

        para_lines = [ln.rstrip("\r\n")]
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
            para_lines.append(lines[i].rstrip("\r\n"))
            i += 1
        # Preserve markdown hard line breaks (trailing two spaces), e.g., authorship block
        rendered_parts: list[str] = []
        for idx_p, pln in enumerate(para_lines):
            has_br = pln.endswith("  ")
            frag = _inline_md(pln.strip())
            if idx_p < len(para_lines) - 1:
                rendered_parts.append(frag + ("<br />" if has_br else " "))
            else:
                rendered_parts.append(frag)
        para_raw = " ".join(p.strip() for p in para_lines)
        p_cls = ' class="table-caption"' if para_raw.startswith("**Table ") else (
            ' class="table-notes"' if para_raw.startswith(("*Notes:*", "*Source:*", "*Sources:*")) else (
                ' class="author-block"' if any(p.endswith("  ") for p in para_lines[:-1]) else ""
            )
        )
        body.append(f"<p{p_cls}>{''.join(rendered_parts)}</p>")

        for fname in fig_map:
            if fname in para_raw and fname not in inserted_figs:
                body.append(_embed_figure_html(fname, fig_map))
                inserted_figs.add(fname)

    for fname in fig_map:
        if fname not in inserted_figs:
            body.append(_embed_figure_html(fname, fig_map))

    css = f"""
    @page {{
      size: letter;
      margin: 0.70in 0.70in 0.76in 0.70in;
      @top-right {{
        content: "{running_header}";
        font-family: Georgia, "Times New Roman", serif;
        font-size: 7.4pt;
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
      font-size: 15.8pt;
      line-height: 1.24;
      margin: 0 0 8pt 0;
      color: #0b2545;
      border-bottom: 1.5pt solid #0b2545;
      padding-bottom: 6pt;
    }}
    h2 {{
      font-size: 11.8pt;
      color: #0b2545;
      margin: 13pt 0 5pt 0;
      border-bottom: 0.6pt solid #cbd5e1;
      padding-bottom: 2pt;
      page-break-after: avoid;
    }}
    h3 {{
      font-size: 10.1pt;
      color: #1e3a5f;
      margin: 10pt 0 4pt 0;
      page-break-after: avoid;
    }}
    p {{ margin: 0 0 5.5pt 0; text-align: justify; }}
    p.author-block {{ text-align: left; margin: 0 0 6pt 0; line-height: 1.38; }}
    p.table-caption {{
      font-size: 8.9pt;
      margin: 10pt 0 4pt 0;
      color: #0b2545;
      text-align: left;
      page-break-after: avoid;
    }}
    p.table-notes {{
      font-size: 7.7pt;
      color: #475569;
      margin: 2pt 0 8pt 0;
      text-align: left;
    }}
    ul, ol {{ margin: 3pt 0 7pt 16pt; padding: 0; }}
    li {{ margin: 0 0 3.2pt 0; text-align: justify; }}
    code {{
      font-family: Consolas, "Courier New", monospace;
      font-size: 8.1pt;
      background: #f1f5f9;
      padding: 0.5pt 2.4pt;
      border-radius: 2pt;
    }}
    hr {{ border: 0; border-top: 0.6pt solid #cbd5e1; margin: 9pt 0; }}
    .math {{ font-family: "Cambria Math", Georgia, serif; font-style: italic; }}
    .math .rm, .eq-block .rm {{ font-style: normal; }}
    .eq-block {{
      font-family: "Cambria Math", Georgia, serif;
      font-size: 9.6pt;
      text-align: center;
      margin: 8pt 0;
      padding: 6pt 10pt;
      background: #f8fafc;
      border-left: 2pt solid #0b2545;
    }}
    .table-wrap {{ margin: 4pt 0 4pt 0; }}
    thead {{ display: table-header-group; }}
    tr {{ page-break-inside: avoid; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 7.5pt;
      line-height: 1.26;
      border-top: 1.3pt solid #0f172a;
      border-bottom: 1.3pt solid #0f172a;
    }}
    thead tr {{ border-bottom: 0.8pt solid #334155; background: #f8fafc; }}
    th, td {{ padding: 3.0pt 3.8pt; vertical-align: top; }}
    td code {{ white-space: nowrap; }}
    tbody tr:nth-child(even) {{ background: #fbfdff; }}
    th.left, td.left {{ text-align: left; }}
    th.center, td.center {{ text-align: center; }}
    th.right, td.right {{ text-align: right; }}
    figure.pub-fig {{
      margin: 9pt 0 9pt 0;
      padding: 5.5pt;
      border: 0.5pt solid #e2e8f0;
      background: #ffffff;
      page-break-inside: avoid;
      text-align: center;
    }}
    figure.pub-fig img {{
      max-width: 100%;
      max-height: 4.15in;
      height: auto;
      display: block;
      margin: 0 auto 4.5pt auto;
    }}
    figure.pub-fig figcaption {{
      font-size: 7.9pt;
      line-height: 1.31;
      color: #334155;
      text-align: left;
    }}
    """
    return (
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8' />"
        f"<title>{html.escape(doc_title)}</title><style>{css}</style></head>"
        f"<body>{''.join(body)}</body></html>"
    )


def compile_one(md_path: Path, pdf_path: Path, fig_map: dict[str, tuple[str, str]], header: str, title: str) -> None:
    if not EDGE_EXE.exists():
        raise FileNotFoundError(f"Microsoft Edge not found at {EDGE_EXE}")
    md_text = md_path.read_text(encoding="utf-8")
    html_doc = convert_md_to_html(md_text, fig_map=fig_map, running_header=header, doc_title=title)

    tmp_dir = Path(tempfile.mkdtemp(prefix="d30_edge_pdf_"))
    try:
        html_path = tmp_dir / f"{md_path.stem}.html"
        user_data_dir = tmp_dir / "edge_profile"
        html_path.write_text(html_doc, encoding="utf-8")
        cmd = [
            str(EDGE_EXE),
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--user-data-dir={user_data_dir}",
            f"--print-to-pdf={pdf_path}",
            html_path.as_uri(),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=90, check=False)
        if res.returncode != 0 or not pdf_path.exists() or pdf_path.stat().st_size < 50_000:
            raise RuntimeError(f"Edge PDF compile failed for {pdf_path.name} rc={res.returncode}: {res.stderr}")
        print(f"[DONE] Compiled {pdf_path.name} ({pdf_path.stat().st_size:,} bytes)", flush=True)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def main() -> int:
    compile_one(
        BASE_DIR / "manuscript_d30_boost.md",
        BASE_DIR / "manuscript_d30_boost.pdf",
        MAIN_FIGURES,
        "Geographic Site Mix and Registered Non-Serious Adverse Events (JCE v4)",
        "Geographic Site Mix and Registered Non-Serious Adverse Events (JCE v4)",
    )
    si_md = BASE_DIR / "supplementary_d30_jce.md"
    if si_md.exists():
        compile_one(
            si_md,
            BASE_DIR / "supplementary_d30_jce.pdf",
            SI_FIGURES,
            "Supplementary Appendix — Geographic Site Mix and Registered AEs (JCE v4)",
            "Supplementary Appendix — D30 (JCE v4)",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
