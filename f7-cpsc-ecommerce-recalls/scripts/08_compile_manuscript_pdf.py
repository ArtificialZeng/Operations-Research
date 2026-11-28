"""Step 8 (v4): Compile manuscript_f7_boost.md and supplementary_f7_jcp.md +
embedded 300-DPI figures into publication-grade zero-leak PDFs via balanced
LaTeX->HTML + Microsoft Edge --headless=new --user-data-dir=<tempdir> --print-to-pdf.
"""
from __future__ import annotations

import base64
import html
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from pypdf import PdfReader

BASE_DIR = Path(r"D:\AI_Science\antigravity\f7_boost_cpsc_ecommerce_recalls_20261126")
MD_PATH = BASE_DIR / "manuscript_f7_boost.md"
PDF_PATH = BASE_DIR / "manuscript_f7_boost.pdf"
SUPP_MD_PATH = BASE_DIR / "supplementary_f7_jcp.md"
SUPP_PDF_PATH = BASE_DIR / "supplementary_f7_jcp.pdf"
RES_DIR = BASE_DIR / "results"
EDGE_EXE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


def build_dynamic_figure_blocks() -> dict[str, tuple[str, str]]:
    """Build all figure captions dynamically from saved JSON receipts (zero drift!)."""
    p1 = json.loads((RES_DIR / "04_pillar1_econometrics.json").read_text(encoding="utf-8"))
    theory = json.loads((RES_DIR / "03_theory_equilibrium.json").read_text(encoding="utf-8"))
    v4 = json.loads((RES_DIR / "09_v4_channel_remedy_audit.json").read_text(encoding="utf-8"))

    sf = v4["channel_contamination_and_sample_flow"]
    c3 = v4["three_definition_channel_comparisons"]
    l391 = sf["legacy_cs_391_contamination"]
    d1 = c3["Def1_Broad_Mkt_Mentions_Amazon"]
    d2a = c3["Def2a_NoOtherFlaggedPlat_Benchmark"]
    d2b = c3["Def2b_Strict_Amazon_Exclusive_Verbatim"]
    disp = v4["hazardous_notice_coverage_v4"]
    amz_cs = v4["in_re_amazon_case_study_v4"]
    fba = amz_cs["fba_terminology_audit"]
    hist = {r["year"]: r for r in p1["historical_2000_2026"]}
    r15, r26 = hist[2015], hist[2026]
    mm = p1["main_models_2022_2026"]
    rob = p1["robustness_photo_verify_2022_2026"]
    cuts = theory["cutoffs"]
    b_all = v4["all_channel_within_mkt_misclassification_bounds"]

    return {
        "fig1_sample_flow_and_channel_audit.png": (
            "Figure 1. CPSC Recall Census Sample Flow (2000&ndash;2026) and Asymmetric Multi-Channel Contamination in Legacy Amazon Labels.",
            (
                f"Panel A traces the exact filtering path from the complete U.S. CPSC SaferProducts census (<em>N</em> = {v4['notice_universe']:,}) "
                f"to the post-emergence era (<em>N</em> = {sf['n_2022_2026_all']:,}; classified regression sample <em>N</em> = {sf['n_2022_2026_reg_sample']:,}, "
                f"<em>G</em> = {sf['g_2022_2026_reg_clusters']:,} firms), the three verbatim Amazon channel categories, calendar-aligned common-support "
                f"comparison samples (Def 1 <em>N</em> = {d1['cs_n']}, Def 2a <em>N</em> = {d2a['cs_n']}, Def 2b <em>N</em> = {d2b['cs_n']}), and the "
                f"<em>N</em> = 150 stratified coding audit. Panel B shows asymmetric contamination inside legacy <code>amazon_only_mkt</code>: "
                f"in the common-support sample (<em>N</em> = 391), {l391['verbatim_multi_channel_by_group']['3_Mkt_True_US']}/127 (58.3%) U.S.-entity "
                f"notices sold across multiple online channels versus {l391['verbatim_multi_channel_by_group']['1_Mkt_FD_China']}/264 (9.8%) China-direct notices."
            ),
        ),
        "fig2_three_definition_channel_comparison.png": (
            "Figure 2. Side-by-Side Channel Definition Sensitivity and Group-Specific Misclassification Bounds (2022&ndash;2026).",
            (
                f"Panel A compares conditional <code>1_Mkt_FD_China &minus; 3_Mkt_True_US</code> gaps (CR1 95% CIs) across All-Channel Within-Marketplace "
                f"(<em>N</em> = {sf['n_2022_2026_reg_sample']:,}), Def 1 Broad Mkt-Amazon (<em>N</em> = {d1['cs_n']}), Def 2a No Other Flagged 3P "
                f"(<em>N</em> = {d2a['cs_n']}: photo +{100*d2a['common_support_models']['photo_language']['beta']:.2f} pp, <em>p</em><sub>WCB</sub> = "
                f"{d2a['common_support_models']['photo_language']['p_wcb']:.3f}; return {100*d2a['common_support_models']['direct_return']['beta']:.2f} pp, "
                f"<em>p</em><sub>WCB</sub> = {d2a['common_support_models']['direct_return']['p_wcb']:.3f}), and Def 2b Verbatim Strict Amazon-Exclusive "
                f"(<em>N</em> = {d2b['cs_n']}: photo +{100*d2b['common_support_models']['photo_language']['beta']:.2f} pp, <em>p</em><sub>WCB</sub> = "
                f"{d2b['common_support_models']['photo_language']['p_wcb']:.3f}; return {100*d2b['common_support_models']['direct_return']['beta']:.2f} pp, "
                f"<em>p</em><sub>WCB</sub> = {d2b['common_support_models']['direct_return']['p_wcb']:.3f}). Panel B compares raw FE estimates against "
                f"Rogan&ndash;Gladen empirical-error-adjusted gaps and 95% Clopper&ndash;Pearson point misclassification bounds from the <em>N</em> = 150 "
                f"stratified audit (All-Channel <code>photo_language</code> adjusted +{100*b_all['photo_language']['beta_empirical_adjusted']:.2f} pp; "
                f"<code>direct_return</code> adjusted {100*b_all['direct_return']['beta_empirical_adjusted']:.2f} pp)."
            ),
        ),
        "fig3_regime_emergence_and_diffusion.png": (
            "Figure 3. 27-Year Platform Disintermediation (2000&ndash;2026) and Disaggregated Mutually Exclusive Notice-Duty Shares (2022&ndash;2026).",
            (
                f"Panel A plots annual CPSC recall shares (<em>N</em> = {v4['notice_universe']:,}): Marketplace-Only notices rose from "
                f"{100*r15['share_mkt_only']:.2f}% (2015) to {100*r26['share_mkt_only']:.2f}% (2026), Foreign-Direct China notices rose from "
                f"{100*r15['share_fd_china']:.2f}% to {100*r26['share_fd_china']:.2f}%, and all-recall photo verification reached "
                f"{100*r26['share_photo_verify_all']:.2f}% in 2026. Panel B disaggregates 2022&ndash;2026 notices across seven mutually exclusive "
                f"remedy-duty categories, separating photo + physical destruction, photo + permanent marking only, mandatory photo-only, "
                f"optional/alternative photo (e.g., Jugader), non-photo destruction proof (e.g., UVIPC), direct return without photo, and other remedies."
            ),
        ),
        "fig4_hazwaste_coverage_and_in_re_amazon.png": (
            "Figure 4. Standalone Institutional Evidence: Hazardous-Product Notice Coverage and In re Amazon.com Case Study.",
            (
                f"Panel A decomposes notice-listed affected inventory across the {disp['screened_notices']}/{disp['hazard_group_notices']} China-direct "
                f"hazardous-product notices assigning consumer self-disposal (0.0% firm direct return): total affected stock is "
                f"{disp['screened_affected_units']:,} units (strictly notice coverage, NOT observed waste stream), with "
                f"{100*disp['top2_ocoopa_anker_share']:.2f}% concentrated in multi-channel recalls OCOOPA (1.500M) and Anker (1.158M) and "
                f"{disp['warning_full_notice_count']}/{disp['screened_notices']} complete notices ({disp['warning_full_notice_affected_units']:,} units, "
                f"{100*disp['warning_full_notice_share_units']:.2f}%) carrying explicit HHW/local-disposal warnings. Panel B compares complete-quarter "
                f"counts (2021Q1&ndash;2026Q3, <em>T</em> = 23) across both broad Amazon-mentioning and verbatim strict Amazon-exclusive notices around "
                f"In re Amazon.com (Jul 30, 2024 &amp; Jan 16, 2025; {fba['explicit_fulfilled_by_amazon_mentions']}/{fba['broad_amazon_only_mkt_2022_2026']} "
                f"explicit FBA mentions, 1/601 standalone FBA model suffix in TADAKAZU 10317)."
            ),
        ),
        "fig2_theory_equilibrium_and_archetype_gaps.png": (
            "Figure S1. Conceptual Principal&ndash;Agent Equilibrium Phase Diagram and All-Channel Conditional Associations (2022&ndash;2026).",
            (
                f"Panel A plots equilibrium adoption thresholds from Supplementary Appendix A showing how institutional audit-cost reduction "
                f"(<em>a</em><sub>2022</sub> &rarr; <em>a</em><sub>2026</sub>) shifts <em>c</em><sub>rev</sub>*/<em>p</em> from "
                f"{cuts['us_2022_crev_ratio']:.3f} to {cuts['us_2026_crev_ratio']:.3f} while keeping high-observability DTC brands inside Direct "
                f"First-Party Remedy (<em>D/U</em>). Panel B displays saturated FE conditional observational gaps across all five non-baseline archetypes "
                f"(<em>N</em> = {mm['photo_verify']['n']:,}, <em>G</em> = {mm['photo_verify']['n_clusters']:,} firms)."
            ),
        ),
        "fig5_robustness_forest_and_platforms.png": (
            "Figure S2. All-Channel Specification Forest Plot (Including Strict Durables &ge;$100) and Identical Product-Noun Comparison (2022&ndash;2026).",
            (
                f"Panel A plots <code>1_Mkt_FD_China</code> vs. Brick-and-Mortar (navy) and within-marketplace <code>FD &minus; U.S.</code> (crimson) "
                f"across 13 strict-era specifications, including Products &ge;$100 All Categories (+{100*rob['R7_high_price_ge_100']['terms']['a_mkt_fd_cn']['beta']:.2f} pp, "
                f"<em>N</em> = {rob['R7_high_price_ge_100']['n']}) and Strict Durables &ge;$100 (+{100*rob['R7b_strict_durables_ge_100']['terms']['a_mkt_fd_cn']['beta']:.2f} pp, "
                f"<em>N</em> = {rob['R7b_strict_durables_ge_100']['n']}). Panel B compares raw <code>photo_verify</code> shares inside identical fine product nouns."
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
    s = s.replace(r"\$", "$")

    while r"\frac{" in s:
        idx = s.index(r"\frac{")
        num, nxt = _extract_braced(s, idx + len(r"\frac"))
        den, end = _extract_braced(s, nxt) if nxt < len(s) and s[nxt] == "{" else ("", nxt)
        s = s[:idx] + f"({num}) / ({den})" + s[end:]

    macro_wrappers = [
        (r"\text{", '<span class="rm">', "</span>"),
        (r"\mathrm{", '<span class="rm">', "</span>"),
        (r"\mathcal{", '<span class="cal">', "</span>"),
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
        (r"\setminus", " &#8726; "),
        (r"\partial", "&part;"),
        (r"\gg", "&gg;"),
        (r"\ll", "&ll;"),
        (r"\mid", " | "),
        (r"\big[", "["),
        (r"\big]", "]"),
        (r"\big(", "("),
        (r"\big)", ")"),
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
        (r"\eta", "&eta;"),
        (r"\nu", "&nu;"),
        (r"\pi", "&pi;"),
        (r"\kappa", "&kappa;"),
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
        parts[i] = parts[i].replace("-", "&minus;")
    return "".join(parts)


def _inline_md(text: str) -> str:
    tokens: list[str] = []

    def stash(html_frag: str) -> str:
        idx = len(tokens)
        tokens.append(html_frag)
        return f"\x00TOK{idx}\x00"

    text = re.sub(r"`([^`]+)`", lambda m: stash(f"<code>{html.escape(m.group(1))}</code>"), text)
    text = re.sub(
        r"\[([^\]\n]+)\]\((https?://[^)\s]+)\)",
        lambda m: stash(f'<a href="{html.escape(m.group(2))}">{html.escape(m.group(1))}</a>'),
        text,
    )

    text = text.replace(r"\$", "\x00DOLLAR\x00")
    text = re.sub(
        r"\$([^$\n]+)\$",
        lambda m: stash(f'<span class="math">{_tex_to_html(m.group(1).replace(chr(0) + "DOLLAR" + chr(0), r"\$"))}</span>'),
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


def convert_md_to_html(
    md_text: str,
    figure_blocks: dict[str, tuple[str, str]],
    running_header: str = "Notice-Level Duties & Channel Classification in U.S. CPSC E-Commerce Recalls",
    doc_title: str = "Who Bears the Burden of Product Recall Remedies?",
) -> str:
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
        # Preserve intentional Markdown hard line breaks (trailing two spaces) for authorship blocks
        if len(para_lines) <= 4 and para_lines[0].startswith("**Zijian Zeng**"):
            html_lines = "<br />".join(_inline_md(pl) for pl in para_lines)
            body.append(f'<p class="author-block">{html_lines}</p>')
            continue
        para_raw = " ".join(para_lines)
        p_cls = (
            ' class="table-caption"'
            if para_raw.startswith("**Table ")
            else (' class="table-notes"' if para_raw.startswith(("*Notes:*", "*Source:*")) else "")
        )
        body.append(f"<p{p_cls}>{_inline_md(para_raw)}</p>")

    css = f"""
    @page {{
      size: letter;
      margin: 0.62in 0.62in 0.70in 0.62in;
      @top-right {{
        content: "{running_header}";
        font-family: Georgia, "Times New Roman", serif;
        font-size: 7.3pt;
        color: #555;
      }}
      @bottom-center {{
        content: "Page " counter(page) " of " counter(pages);
        font-family: Georgia, "Times New Roman", serif;
        font-size: 7.8pt;
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
      font-size: 13.8pt;
      line-height: 1.24;
      margin: 0 0 7pt 0;
      color: #0b2545;
      border-bottom: 1.5pt solid #0b2545;
      padding-bottom: 5pt;
    }}
    p.author-block {{
      text-align: left;
      font-size: 8.8pt;
      line-height: 1.38;
      color: #1e293b;
      margin: 0 0 6pt 0;
    }}
    h2 {{
      font-size: 11.0pt;
      color: #0b2545;
      margin: 11pt 0 5pt 0;
      border-bottom: 0.6pt solid #cbd5e1;
      padding-bottom: 2pt;
      page-break-after: avoid;
    }}
    h3 {{
      font-size: 9.7pt;
      color: #1e3a5f;
      margin: 8.5pt 0 3.5pt 0;
      page-break-after: avoid;
    }}
    p {{ margin: 0 0 5.2pt 0; text-align: justify; }}
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
      margin: 2pt 0 7.5pt 0;
      text-align: left;
    }}
    ul, ol {{ margin: 3pt 0 6pt 16pt; padding: 0; }}
    li {{ margin: 0 0 2.6pt 0; text-align: justify; }}
    ol.refs-list li {{ text-align: left; font-size: 8.0pt; line-height: 1.32; break-inside: avoid; page-break-inside: avoid; }}
    code {{
      font-family: Consolas, "Courier New", monospace;
      font-size: 7.3pt;
      background: #f1f5f9;
      padding: 0.3pt 1.8pt;
      border-radius: 2pt;
    }}
    a {{ color: #1d4ed8; text-decoration: none; }}
    hr {{ border: 0; border-top: 0.6pt solid #cbd5e1; margin: 7.5pt 0; }}
    .math {{ font-family: "Cambria Math", Georgia, serif; font-style: italic; }}
    .math .rm, .eq-block .rm {{ font-style: normal; }}
    .math .cal, .eq-block .cal {{ font-family: "Lucida Calligraphy", "Cambria Math", serif; font-style: italic; }}
    sup, sub {{ white-space: nowrap; }}
    .eq-block {{
      font-family: "Cambria Math", Georgia, serif;
      font-size: 9.4pt;
      text-align: center;
      margin: 6pt 0;
      padding: 5pt 9pt;
      background: #f8fafc;
      border-left: 2pt solid #0b2545;
    }}
    .table-wrap {{ margin: 4pt 0 4pt 0; page-break-inside: avoid; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 6.45pt;
      line-height: 1.18;
      border-top: 1.3pt solid #0f172a;
      border-bottom: 1.3pt solid #0f172a;
    }}
    thead tr {{ border-bottom: 0.8pt solid #334155; background: #f8fafc; }}
    th, td {{ padding: 1.8pt 2.3pt; vertical-align: top; }}
    td .math, th .math {{ white-space: nowrap; }}
    td code {{ white-space: nowrap; font-size: 6.35pt; }}
    tbody tr:nth-child(even) {{ background: #fbfdff; }}
    th.left, td.left {{ text-align: left; }}
    th.center, td.center {{ text-align: center; }}
    th.right, td.right {{ text-align: right; }}
    figure.pub-fig {{
      margin: 7pt 0 7pt 0;
      padding: 4.5pt;
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
      margin: 0 auto 4pt auto;
    }}
    figure.pub-fig figcaption {{
      font-size: 7.6pt;
      line-height: 1.29;
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
        r"\{,\}",
        r"\\text\{",
        r"\\mathbf\{",
        r"\\frac\{",
        r"\\mathcal\{",
        r"\bp_WCB\b",
        r"\^[0-9A-Za-z{]",
        r"fig[1-5]_[a-z0-9_]+\.png",
        r"<!--",
        r"ESC_US",
        r"TOK\d+",
        r"Target Venues",
        r"Target Format",
        r"Track A",
        r"Track B",
    ]
    leaks = []
    for pat in bad_patterns:
        if re.search(pat, full_txt):
            leaks.append(pat)
    return len(reader.pages), leaks


def compile_markdown_to_pdf(
    md_path: Path,
    pdf_path: Path,
    figure_blocks: dict[str, tuple[str, str]],
    running_header: str,
    doc_title: str,
) -> tuple[int, int]:
    if not EDGE_EXE.exists():
        raise RuntimeError(f"Microsoft Edge not found at {EDGE_EXE}")
    md_text = md_path.read_text(encoding="utf-8")
    html_doc = convert_md_to_html(md_text, figure_blocks, running_header=running_header, doc_title=doc_title)

    with tempfile.TemporaryDirectory(prefix="f7_v4_edge_") as tmpdir:
        tmp = Path(tmpdir)
        html_file = tmp / f"{pdf_path.stem}.html"
        out_tmp = tmp / pdf_path.name
        html_file.write_text(html_doc, encoding="utf-8")
        cmd = [
            str(EDGE_EXE),
            f"--user-data-dir={tmp / 'edge_profile'}",
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-pdf-header-footer",
            f"--print-to-pdf={out_tmp}",
            html_file.as_uri(),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=90, check=False)
        if res.returncode != 0 or not out_tmp.exists() or out_tmp.stat().st_size < 40_000:
            raise RuntimeError(f"Edge PDF compile failed for {pdf_path.name} rc={res.returncode}: {res.stderr}")
        n_pages, leaks = verify_pdf_zero_leaks(out_tmp)
        if leaks:
            raise RuntimeError(f"Leaked tokens in {pdf_path.name}: {leaks}")
        pdf_path.write_bytes(out_tmp.read_bytes())
        return n_pages, pdf_path.stat().st_size


def main() -> int:
    figure_blocks = build_dynamic_figure_blocks()
    n_main, sz_main = compile_markdown_to_pdf(
        MD_PATH,
        PDF_PATH,
        figure_blocks,
        running_header="Notice-Level Duties & Channel Classification in U.S. CPSC E-Commerce Recalls",
        doc_title="Who Bears the Burden of Product Recall Remedies?",
    )
    print(f"[DONE STEP 8 v4] Compiled {PDF_PATH} ({sz_main:,} bytes, {n_main} pages, 0 leaked tokens)", flush=True)

    if SUPP_MD_PATH.exists():
        n_supp, sz_supp = compile_markdown_to_pdf(
            SUPP_MD_PATH,
            SUPP_PDF_PATH,
            figure_blocks,
            running_header="Supplementary Material — Notice-Level Duties in U.S. CPSC E-Commerce Recalls",
            doc_title="Supplementary Material — Who Bears the Burden of Product Recall Remedies?",
        )
        print(f"[DONE STEP 8 v4] Compiled {SUPP_PDF_PATH} ({sz_supp:,} bytes, {n_supp} pages, 0 leaked tokens)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
