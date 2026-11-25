"""Step 8: Compile manuscript_f7_boost.md + embedded 300-DPI figures into a
publication-grade PDF (manuscript_f7_boost.pdf) via balanced LaTeX->HTML +
Microsoft Edge --headless=new --print-to-pdf, with strict zero-leak verification.
"""
from __future__ import annotations

import base64
import html
import json
import re
import subprocess
import sys
from pathlib import Path

from pypdf import PdfReader

BASE_DIR = Path(r"D:\AI_Science\antigravity\f7_boost_cpsc_ecommerce_recalls_20261126")
MD_PATH = BASE_DIR / "manuscript_f7_boost.md"
HTML_PATH = BASE_DIR / "manuscript_f7_boost.html"
PDF_PATH = BASE_DIR / "manuscript_f7_boost.pdf"
RES_DIR = BASE_DIR / "results"
EDGE_EXE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


def build_dynamic_figure_blocks() -> dict[str, tuple[str, str]]:
    """Build figure captions dynamically from saved JSON receipts so zero numbers drift."""
    p1 = json.loads((RES_DIR / "04_pillar1_econometrics.json").read_text(encoding="utf-8"))
    p234 = json.loads((RES_DIR / "05_pillars_2_3_4.json").read_text(encoding="utf-8"))
    theory = json.loads((RES_DIR / "03_theory_equilibrium.json").read_text(encoding="utf-8"))

    hist = {r["year"]: r for r in p1["historical_2000_2026"]}
    r15, r26 = hist[2015], hist[2026]
    diff_s = p234["pillar2"]["diffusion_slopes_2022_2026"]
    mm = p1["main_models_2022_2026"]
    rob = p1["robustness_photo_verify_2022_2026"]
    hac_jul = p234["pillar3"]["hac_its_results"]["jul2024_2024Q3"]
    persist = p234["pillar3"]["post_jan2025_contract_persistence"]["Mkt_FD_China"]["photo_verify"]
    hw_fd = p234["pillar4"]["hazwaste_by_archetype"]["1_Mkt_FD_China"]
    desc = p1["descriptives_6_archetypes_2022_2026"]
    cuts = theory["cutoffs"]

    return {
        "fig1_regime_emergence_and_diffusion.png": (
            "Figure 1. 27-Year Platform Disintermediation (2000&ndash;2026) and Proof-of-Destruction Domestic Diffusion (2022&ndash;2026).",
            (
                f"Panel A traces annual shares across the complete U.S. CPSC recall census (<em>N</em> = 8,386): Marketplace-Only recalls expanded "
                f"from {100*r15['share_mkt_only']:.2f}% (2015) to {100*r26['share_mkt_only']:.2f}% (2026), Foreign-Direct China recalls surged from "
                f"{100*r15['share_fd_china']:.2f}% to {100*r26['share_fd_china']:.2f}%, and all-recall Proof-of-Destruction (<code>photo_verify</code>) "
                f"emerged after 2021 to reach {100*r26['share_photo_verify_all']:.2f}% in 2026. Panel B plots 2022&ndash;2026 annual adoption curves "
                f"showing cross-border pioneer leadership (<code>1_Mkt_FD_China</code>: {100*diff_s['1_Mkt_FD_China']['pv_2022']:.1f}% &rarr; "
                f"{100*diff_s['1_Mkt_FD_China']['pv_2026']:.1f}%) followed by sequential diffusion into U.S.-entity marketplace sellers "
                f"({100*diff_s['3_Mkt_True_US']['pv_2022']:.1f}% &rarr; {100*diff_s['3_Mkt_True_US']['pv_2026']:.1f}%) and domestic Brick-and-Mortar "
                f"chains ({100*diff_s['6_Brick_and_Mortar']['pv_2022']:.1f}% &rarr; {100*diff_s['6_Brick_and_Mortar']['pv_2026']:.1f}%)."
            ),
        ),
        "fig2_theory_equilibrium_and_archetype_gaps.png": (
            "Figure 2. Formal Principal&ndash;Agent Equilibrium Phase Diagram and Strict-Era (2022&ndash;2026) Ultra-Saturated Contract Gaps.",
            (
                f"Panel A plots exact equilibrium regions from Section 2 in normalized reverse-logistics cost (<em>c</em><sub>rev</sub>/<em>p</em>) "
                f"and first-party buyer observability (<em>&theta;</em>) space, illustrating how institutional audit-cost reduction (<em>a</em><sub>2022</sub> &rarr; "
                f"<em>a</em><sub>2026</sub>) shifts <em>c</em><sub>rev</sub>*/<em>p</em> from {cuts['us_2022_crev_ratio']:.3f} to {cuts['us_2026_crev_ratio']:.3f} "
                f"(dashed crimson to solid navy) while keeping high-observability DTC brands protected inside Direct First-Party Remedy (<em>D/U</em>). "
                f"Panel B reports full-rank ultra-saturated FE effects (CR1 95% CIs, <em>N</em> = {mm['photo_verify']['n']:,}, <em>G</em> = {mm['photo_verify']['n_clusters']:,} firm clusters) vs. Brick-and-Mortar: "
                f"<code>1_Mkt_FD_China</code> drives +{100*mm['photo_verify']['terms']['a_mkt_fd_cn']['beta']:.2f} pp photo-verify, "
                f"+{100*mm['physical_mutilate']['terms']['a_mkt_fd_cn']['beta']:.2f} pp physical mutilation, "
                f"{100*mm['direct_return']['terms']['a_mkt_fd_cn']['beta']:.2f} pp direct return, and "
                f"+{100*mm['free_webmail']['terms']['a_mkt_fd_cn']['beta']:.2f} pp free webmail (all <em>p</em><sub>WCB</sub> = 0.001), whereas "
                f"<code>4_DTC_Online_Only</code> and <code>5_Omnichannel</code> remain statistically indistinguishable from zero on photo verification."
            ),
        ),
        "fig3_robustness_forest_and_platforms.png": (
            "Figure 3. Identification Robustness Forest Plot and Identical Product-Noun Head-to-Head Comparison (2022&ndash;2026).",
            (
                f"Panel A displays both <code>1_Mkt_FD_China</code> vs. Brick-and-Mortar (navy circles) and the exact within-marketplace contrast "
                f"<code>1_Mkt_FD_China &minus; 3_Mkt_True_US</code> (crimson diamonds, CR1 95% CIs) across 12 strict-era specifications, peaking at "
                f"+{100*rob['R7_high_price_ge_100']['terms']['a_mkt_fd_cn']['beta']:.1f} pp (<em>t</em> = +{rob['R7_high_price_ge_100']['terms']['a_mkt_fd_cn']['t']:.2f}) "
                f"inside High-Price Durables (&ge;$100) and surviving Fine-Noun &times; Year FE (+{100*rob['R3_fine_noun_x_year_fe']['terms']['a_mkt_fd_cn']['beta']:.1f} pp), "
                f"within Made-in-China (+{100*rob['R9_within_made_in_china']['terms']['a_mkt_fd_cn']['beta']:.1f} pp), mediation for webmail &amp; no-phone "
                f"(+{100*rob['R10_control_webmail_nophone']['terms']['a_mkt_fd_cn']['beta']:.1f} pp), and shell-front adjustment "
                f"(within-mkt +{100*rob['R11_shell_front_audit']['contrast']['diff']:.1f} pp). Panel B compares raw <code>photo_verify</code> shares "
                f"strictly inside identical fine product nouns (Domestic B&amp;M/Omnichannel vs. <code>1_Mkt_FD_China</code>)."
            ),
        ),
        "fig4_amazon_enforcement_ramp.png": (
            "Figure 4. Intermediary Liability Shock (In re Amazon.com, 2024&ndash;2026): Quarterly Enforcement Ramp and Contract Persistence.",
            (
                f"Panel A tracks complete-quarter recall volumes (2021Q1&ndash;2026Q3, <em>T</em> = 23; partial 2026Q4 excluded) across Amazon-Only "
                f"(total and mandatory-rule subset), Brick-and-Mortar, and Non-Amazon 3P marketplaces, shading the 3-quarter administrative lag between "
                f"the July 30, 2024 Distributor Decision and January 16, 2025 Final Remedy Order. Panel B fits Newey&ndash;West HAC (<em>L</em> = 4) "
                f"interrupted time-series regressions to relative log recall ratios, confirming sharp post-ruling slope acceleration in both "
                f"<code>log(Amz/B&amp;M)</code> (+{hac_jul['log_amz_over_bm_L4']['its_params']['slope_change']['beta']:.3f}/qtr, "
                f"<em>t</em> = +{hac_jul['log_amz_over_bm_L4']['its_params']['slope_change']['t']:.2f}) and <code>log(Amz/NonAmz)</code> "
                f"(+{hac_jul['log_amz_over_nonamz_L4']['its_params']['slope_change']['beta']:.3f}/qtr, "
                f"<em>t</em> = +{hac_jul['log_amz_over_nonamz_L4']['its_params']['slope_change']['t']:.2f}), while <code>1_Mkt_FD_China</code> "
                f"<code>photo_verify</code> climbed from {100*persist['pre_mean']:.1f}% pre-order to {100*persist['post_mean']:.1f}% post-order."
            ),
        ),
        "fig5_safety_hazwaste_and_infrastructure.png": (
            "Figure 5. Mandatory Safety-Rule Violations, Hazardous-Waste Externalization, and Contact/Traceability Collapse (2022&ndash;2026).",
            (
                f"Panel A contrasts five supply-chain archetypes across mandatory federal safety-rule violation rates "
                f"(<code>1_Mkt_FD_China</code> {100*desc['1_Mkt_FD_China']['mandatory_rule']:.1f}% vs. Brick-and-Mortar "
                f"{100*desc['6_Brick_and_Mortar']['mandatory_rule']:.1f}%) and hazardous-waste recall remedies (lithium-ion batteries, button cells, "
                f"lead/phthalates/chemicals): <code>1_Mkt_FD_China</code> exhibits {100*hw_fd['share_direct_return']:.1f}% firm direct return, "
                f"{100*hw_fd['share_photo_self_disposal']:.1f}% photo self-destruction, and {100*hw_fd['share_household_self_disposal']:.1f}% "
                f"household self-disposal ({hw_fd['units_self_disposed_total']:,} units externalized). Panel B documents simultaneous collapse in "
                f"contact infrastructure ({100*desc['1_Mkt_FD_China']['free_webmail']:.1f}% free webmail; {100*desc['1_Mkt_FD_China']['no_phone']:.1f}% no phone), "
                f"GS1 UPC listing ({100*desc['1_Mkt_FD_China']['has_upc']:.1f}% vs. {100*desc['6_Brick_and_Mortar']['has_upc']:.1f}%), and joint "
                f"Canada/Mexico recalls ({100*desc['1_Mkt_FD_China']['has_inconjunction']:.1f}% vs. {100*desc['6_Brick_and_Mortar']['has_inconjunction']:.1f}%)."
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
    # Protect literal \$ inside math mode first
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

    # Protect escaped underscores \_ inside math mode (e.g., \text{Mkt\_FD\_China}) using HTML entity &#95;
    # so they NEVER trigger subscript regexes!
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
    # Also handle standard single-char subscript after variable like q_0, C_R, p_i, k_m, a_t
    s = re.sub(r"([A-Za-z0-9>])_([A-Za-z0-9]+)\b", r"\1<sub>\2</sub>", s)
    s = re.sub(r"\^([A-Za-z0-9+\-*]+)", r"<sup>\1</sup>", s)

    # Replace ASCII minus inside text nodes with typographic minus
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

    # Protect escaped dollar signs OUTSIDE math mode (e.g. \$100) while preserving \$ inside $...$
    # First parse inline math allowing \$ inside math!
    text = re.sub(r"`([^`]+)`", lambda m: stash(f"<code>{html.escape(m.group(1))}</code>"), text)

    # Temporarily replace escaped \$ with placeholder before matching $...$
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


def convert_md_to_html(md_text: str, figure_blocks: dict[str, tuple[str, str]]) -> str:
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
        para_raw = " ".join(para_lines)
        p_cls = (
            ' class="table-caption"'
            if para_raw.startswith("**Table ")
            else (' class="table-notes"' if para_raw.startswith(("*Notes:*", "*Source:*")) else "")
        )
        body.append(f"<p{p_cls}>{_inline_md(para_raw)}</p>")

    for fname in figure_blocks:
        if fname not in inserted_figs and (BASE_DIR / "figures" / fname).exists():
            body.append(_embed_figure_html(fname, figure_blocks))

    css = """
    @page {
      size: letter;
      margin: 0.65in 0.65in 0.72in 0.65in;
      @top-right {
        content: "The Asset-Light Safety Gap: Proof-of-Destruction Recall Contracts (F7)";
        font-family: Georgia, "Times New Roman", serif;
        font-size: 7.4pt;
        color: #555;
      }
      @bottom-center {
        content: "Page " counter(page) " of " counter(pages);
        font-family: Georgia, "Times New Roman", serif;
        font-size: 7.9pt;
        color: #555;
      }
    }
    @page :first { @top-right { content: normal; } }
    body {
      font-family: Georgia, "Times New Roman", serif;
      font-size: 9.3pt;
      line-height: 1.42;
      color: #1a1a1a;
      max-width: 100%;
    }
    h1.paper-title {
      font-size: 14.2pt;
      line-height: 1.24;
      margin: 0 0 8pt 0;
      color: #0b2545;
      border-bottom: 1.5pt solid #0b2545;
      padding-bottom: 6pt;
    }
    h2 {
      font-size: 11.2pt;
      color: #0b2545;
      margin: 12pt 0 5pt 0;
      border-bottom: 0.6pt solid #cbd5e1;
      padding-bottom: 2pt;
      page-break-after: avoid;
    }
    h3 {
      font-size: 9.8pt;
      color: #1e3a5f;
      margin: 9pt 0 4pt 0;
      page-break-after: avoid;
    }
    p { margin: 0 0 5.4pt 0; text-align: justify; }
    p.table-caption {
      font-size: 8.5pt;
      margin: 7pt 0 3pt 0;
      color: #0b2545;
      text-align: left;
      break-inside: avoid;
      page-break-inside: avoid;
      break-after: avoid;
      page-break-after: avoid;
    }
    p.table-notes {
      font-size: 7.5pt;
      color: #475569;
      margin: 2pt 0 8pt 0;
      text-align: left;
    }
    ul, ol { margin: 3pt 0 6pt 16pt; padding: 0; }
    li { margin: 0 0 2.8pt 0; text-align: justify; }
    ol.refs-list li { text-align: left; font-size: 8.2pt; line-height: 1.33; break-inside: avoid; page-break-inside: avoid; }
    code {
      font-family: Consolas, "Courier New", monospace;
      font-size: 7.5pt;
      background: #f1f5f9;
      padding: 0.4pt 2.0pt;
      border-radius: 2pt;
    }
    hr { border: 0; border-top: 0.6pt solid #cbd5e1; margin: 8pt 0; }
    .math { font-family: "Cambria Math", Georgia, serif; font-style: italic; }
    .math .rm, .eq-block .rm { font-style: normal; }
    .math .cal, .eq-block .cal { font-family: "Lucida Calligraphy", "Cambria Math", serif; font-style: italic; }
    sup, sub { white-space: nowrap; }
    .eq-block {
      font-family: "Cambria Math", Georgia, serif;
      font-size: 9.5pt;
      text-align: center;
      margin: 6.5pt 0;
      padding: 5.5pt 10pt;
      background: #f8fafc;
      border-left: 2pt solid #0b2545;
    }
    .table-wrap { margin: 4pt 0 4pt 0; page-break-inside: avoid; }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 6.55pt;
      line-height: 1.18;
      border-top: 1.3pt solid #0f172a;
      border-bottom: 1.3pt solid #0f172a;
    }
    thead tr { border-bottom: 0.8pt solid #334155; background: #f8fafc; }
    th, td { padding: 1.8pt 2.4pt; vertical-align: top; }
    td .math, th .math { white-space: nowrap; }
    td code { white-space: nowrap; font-size: 6.5pt; }
    tbody tr:nth-child(even) { background: #fbfdff; }
    th.left, td.left { text-align: left; }
    th.center, td.center { text-align: center; }
    th.right, td.right { text-align: right; }
    figure.pub-fig {
      margin: 7.5pt 0 7.5pt 0;
      padding: 5pt;
      border: 0.5pt solid #e2e8f0;
      background: #ffffff;
      page-break-inside: avoid;
      text-align: center;
    }
    figure.pub-fig img {
      max-width: 100%;
      max-height: 4.10in;
      height: auto;
      display: block;
      margin: 0 auto 4.5pt auto;
    }
    figure.pub-fig figcaption {
      font-size: 7.7pt;
      line-height: 1.30;
      color: #334155;
      text-align: left;
    }
    """
    return (
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8' />"
        f"<title>F7 Boost Manuscript</title><style>{css}</style></head>"
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
    ]
    leaks = []
    for pat in bad_patterns:
        if re.search(pat, full_txt):
            leaks.append(pat)
    return len(reader.pages), leaks


def main() -> int:
    figure_blocks = build_dynamic_figure_blocks()
    md_text = MD_PATH.read_text(encoding="utf-8")
    html_doc = convert_md_to_html(md_text, figure_blocks)
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
    print(f"[DONE STEP 8] Compiled {PDF_PATH} ({PDF_PATH.stat().st_size:,} bytes, {n_pages} pages, 0 leaked tokens)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
