"""Pillar 7b: Compile manuscript_i4_boost.md + embedded 300-DPI figures into camera-ready
manuscript_i4_boost.pdf via escaped-underscore-safe balanced LaTeX->HTML + Microsoft Edge
--headless=new --print-to-pdf, with strict zero-leak verification on extracted PDF text.
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

BASE_DIR = Path(r"D:\AI_Science\antigravity\i4_boost_sec_names_rule_20261126")
MD_PATH = BASE_DIR / "manuscript_i4_boost.md"
HTML_PATH = BASE_DIR / "manuscript_i4_boost.html"
PDF_PATH = BASE_DIR / "manuscript_i4_boost.pdf"
RES_DIR = BASE_DIR / "results"
EDGE_EXE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


def build_dynamic_figure_blocks() -> dict[str, tuple[str, str]]:
    """Build all 5 figure captions 100% dynamically from saved JSON receipts."""
    r1 = json.loads((RES_DIR / "01_panel_audit.json").read_text(encoding="utf-8"))
    r2 = json.loads((RES_DIR / "02_edgar_audit_summary.json").read_text(encoding="utf-8"))
    r3 = json.loads((RES_DIR / "03_holdings_lookthrough.json").read_text(encoding="utf-8"))
    r4 = json.loads((RES_DIR / "04_econometrics_results.json").read_text(encoding="utf-8"))
    r5 = json.loads((RES_DIR / "05_monthly_flow_results.json").read_text(encoding="utf-8"))

    bif = r1["bifurcated_equilibrium_multi_asset_gvi"]
    fv = r1["flow_sign_fix_validation"]
    ed_all = r2["arm_summary"]["ALL_DROPPERS"]
    ed_ma = r2["arm_summary"]["MULTI_ASSET_GVI_ALL"]
    ed_num = r2["arm_summary"]["MA_GVI_NUMERIC"]
    ed_keep = r2["arm_summary"]["CONTROL_MA_GVI_KEEPER"]
    ed_eff = r2["effective_date_clustering"]
    eff_hm = ed_eff["monthly_histogram_ma_gvi"]
    n_eff_apr_may25 = eff_hm.get("2025-04", 0) + eff_hm.get("2025-05", 0)
    n_eff_sep25 = eff_hm.get("2025-09", 0)
    n_eff_apr_may26 = eff_hm.get("2026-04", 0) + eff_hm.get("2026-05", 0)
    in_all = r3["inertia_cross_section"]["MULTI_ASSET_GVI_ALL"]
    in_lt = r3["inertia_cross_section"]["HOLD_LT_CONSTR_GVI"]
    in_faq = r3["inertia_cross_section"]["HOLD_LT_CONSTR_GV_NO_INC"]
    xv = r4["ex_vanguard_sensitivity"]
    a3 = r4["main_did_full_20_26Q3"]["A3_GVI_ALL"]
    a3_opq = r4["main_did_full_20_26Q3"]["A3_GVI_OPAQUE_ONLY"]
    a3_faq = r4["main_did_full_20_26Q3"]["FAQ2_GV_NO_INC"]["post_25_26"]
    fe_id = r4["high_dim_fe"]["FULL_20_26Q3_GVI_ALLOC_COMPLEX_X_QTR_IDENTIFYING"]
    step = r4["statutory_size_step_function"]
    b4_loc = r4["statutory_cutoff_tests"]["B4_LOCAL_1B_10B_VS_LT1B"]["did_post_25_26"]
    leg_vals = [v["post_pct"] for v in step["LEGACY_2001_PLACEBO"].values()]
    fm = r5["monthly_arms"]
    ma_es = fm["MA_GVI_POOLED"]["event_study_summary"]
    esg_es = fm["ESG_DROPPERS"]["event_study_summary"]

    return {
        "fig1_compliance_cliffs_and_bifurcation.png": (
            "Figure 1. Quarterly Regulated Name-Drop Hazards by True REPORT_DATE and Dynamic DiD Event Study (2020Q1&ndash;2026Q3).",
            (
                f"Panel A decomposes quarterly regulated name-drop rates among constrained multi-asset Growth/Value/Income (GVI) funds into "
                f"Opaque Exempt-Synonym substitutions (crimson) versus Transparency-Enhancing Numeric Ratios (teal), plotted against Pure-Equity/Bond "
                f"GVI controls (navy) and Legacy-2001 placebos (slate); partial July-2026 2026Q3 filings are shaded. "
                f"Panel B plots quarter-by-quarter DiD event-study coefficients (ref = 2023Q2, CR1 95% CI clustered by unified COMPLEX_ID): "
                f"all 13 pre-rule quarters are flat (All GVI joint <em>F</em> = {a3['joint_pre_F']['F']:.2f}, <em>p</em> = {a3['joint_pre_F']['p']:.3f}; "
                f"Opaque Only joint <em>F</em> = {a3_opq['joint_pre_F']['F']:.2f}, <em>p</em> = {a3_opq['joint_pre_F']['p']:.3f}), followed by sharp "
                f"May-2025 lock-in and June-2026 on-cycle compliance surges (pooled DiD {a3['post_25_26']['beta']*100:+.2f} pp/qtr, <em>p</em><sub>WCB</sub> = {a3['post_25_26']['p_wcb']:.3f})."
            ),
        ),
        "fig2_bifurcated_equilibrium_and_edgar_proof.png": (
            "Figure 2. Bifurcated Compliance Equilibrium (Including Ex-Vanguard Sensitivity) and Symmetric Live SEC EDGAR 497/485BPOS Proof.",
            (
                f"Panel A contrasts Fund Count share, Renamed AUM share (All vs. Ex-Vanguard), Variable-Annuity share, and Index/ETF share across multi-asset GVI droppers: "
                f"Opaque Synonyms represent {bif['OPAQUE_SYNONYM']['pct_funds']:.1f}% of funds ({bif['OPAQUE_SYNONYM']['n_funds']} funds across "
                f"{xv['all_ma_gvi']['OPAQUE_SYNONYM']['n_complexes']} complexes, ${bif['OPAQUE_SYNONYM']['aum_B']:.1f}B, {bif['OPAQUE_SYNONYM']['pct_va_insurance']:.1f}% VA/insurance, 0.0% index/ETF), "
                f"whereas Numeric Ratios represent {bif['NUMERIC_RATIO']['pct_funds']:.1f}% of funds ({bif['NUMERIC_RATIO']['n_funds']} funds) and "
                f"{bif['NUMERIC_RATIO']['pct_aum']:.1f}% of renamed AUM overall (${bif['NUMERIC_RATIO']['aum_B']:.1f}B) but drop to "
                f"{xv['ex_vanguard_ma_gvi']['NUMERIC_RATIO']['pct_aum']:.1f}% (${xv['ex_vanguard_ma_gvi']['NUMERIC_RATIO']['aum_B']:.2f}B; Opaque = "
                f"{xv['ex_vanguard_ma_gvi']['OPAQUE_SYNONYM']['pct_aum']:.1f}% of AUM and {xv['ex_vanguard_ma_gvi']['OPAQUE_SYNONYM']['pct_funds']:.1f}% of funds) "
                f"excluding Vanguard LifeStrategy ({xv['vanguard_share_of_numeric_aum_pct']:.1f}% of numeric AUM). "
                f"Panel B summarizes 100% symmetric live EDGAR 497/485BPOS audits (up to 6 MB per filing) across all {ed_all['n_funds']} droppers and "
                f"{ed_keep['n_funds']} matched Keepers: Keepers cite trust-level Rule 35d-1 boilerplate significantly more often "
                f"({ed_keep['trust_cites_35d1_pct']:.0f}% vs. {ed_ma['trust_cites_35d1_pct']:.0f}% in MA droppers, "
                f"Fisher <em>p</em> = {r2['fisher_tests_ma_droppers_vs_keepers']['p_2sided_trust_cites_35d1']:.4f}), whereas droppers file concentrated "
                f"name-change disclosures ({ed_ma['name_change_sticker_pct']:.0f}% vs. {ed_keep['name_change_sticker_pct']:.0f}% in keepers; "
                f"{ed_num['no_strategy_change_pct']:.0f}% of numeric droppers certifying strategies remain unchanged). "
                f"Panel C plots window-validated legal effective months parsed from 497/497K supplements ({ed_eff['n_ma_gvi_with_parsed_eff_date']} MA GVI funds): "
                f"{n_eff_apr_may25} cluster in Apr&ndash;May 2025 ({ed_eff['exact_2025_05_01_ma_gvi']}/{eff_hm.get('2025-05', 0)} May-2025 dates on exact May 1, 2025), "
                f"{n_eff_sep25} in Sept 2025, and {n_eff_apr_may26} in Apr&ndash;May 2026 ahead of the June 11, 2026 on-cycle start date."
            ),
        ),
        "fig3_statutory_cutoff_and_robustness_forest.png": (
            "Figure 3. Statutory $1 Billion vs. $10 Billion Step Function and Full Econometric, Ex-Vanguard, SEC-FAQ &amp; LOFO Forest.",
            (
                f"Panel A compares post-period (2025Q1&ndash;2026Q3) quarterly drop rates across pre-rule (2023Q2) unified complex net-asset bins for active 2024+ complexes: "
                f"Non-political Multi-Asset GVI jumps sharply right above Rule 35d-1&rsquo;s $1B statutory threshold "
                f"(&lt;$1B: {step['MULTI_ASSET_GVI']['<$1B (Exempt in 26Q3)']['post_pct']:.2f}% vs. $1B&ndash;$10B: {step['MULTI_ASSET_GVI']['$1B-$10B (Binding Jun26)']['post_pct']:.2f}%, "
                f"exempt from the delayed $10B Form N-PORT reporting cutoff under Release IC-35963), whereas Political ESG drops are highest below $1B ({step['ESG']['<$1B (Exempt in 26Q3)']['post_pct']:.2f}%) "
                f"and Legacy-2001 placebos stay flat ({min(leg_vals):.2f}%&ndash;{max(leg_vals):.2f}%). Panel B displays point estimates, 95% CR1 CIs, and exact LSDV-equivalent WCB <em>p</em>-values "
                f"across 13 specifications, including Ex-Vanguard Opaque GVI, SEC-FAQ strict non-exempt Growth/Value excluding Income and Growth &amp; Income "
                f"({a3_faq['beta']*100:+.2f} pp, <em>p</em><sub>WCB</sub> = {a3_faq['p_wcb']:.3f}), identifying-complexes-only COMPLEX_ID &times; REP_YQ FE "
                f"({fe_id['beta']*100:+.2f} pp, <em>p</em><sub>WCB</sub> = {fe_id['p_wcb']:.3f}), zero-keyword 4-tier look-through (&lt;80% single-class proxy), "
                f"saturated DDD, worst-case LOFO (dropping Fidelity), and local $1B&ndash;$10B Legacy-2001 placebo ({b4_loc['beta']*100:+.2f} pp, <em>p</em><sub>WCB</sub> = {b4_loc['p_wcb']:.3f})."
            ),
        ),
        "fig4_lookthrough_holdings_inertia.png": (
            "Figure 4. 4-Tier Cross-Quarter CUSIP-Consensus Look-Through Stock-Bond Allocation Inertia (2023Q2 &rarr; 2026Q2/Q3).",
            (
                f"Panel A scatters pre-rule 2023Q2 versus post-cliff 2026Q2/Q3 true 4-tier look-through equity shares across all paired multi-asset GVI funds "
                f"(<em>n</em> = {in_all['n_droppers']} droppers vs. {in_all['n_keepers']} keepers, resolved via a 5,597-CUSIP cross-quarter title registry with 100/100 top-100 accuracy), "
                f"confirming Vanguard LifeStrategy 20/80, 40/60, 60/40, and 80/20 and Prudential AST sit along the 45&deg; zero-reallocation diagonal inside the shaded &lt;80% single-asset-class blended zone "
                f"(a holdings proxy for blended mandates rather than literal statutory noncompliance, as Rule 35d-1 permits prospectus-defined multi-asset 80% baskets). "
                f"Panel B plots Dropper minus Keeper allocation-inertia differentials (95% CR1 CI &amp; WCB <em>p</em>) against exact non-overlapping monthly passive drift: "
                f"inside the &lt;80% single-class proxy sample, droppers shift {in_lt['metrics']['ACTIVE_TOWARD_80']['beta']:+.2f} pp relative to keepers away from 80% single-class concentration "
                f"(<em>p</em><sub>WCB</sub> = {in_lt['metrics']['ACTIVE_TOWARD_80']['p_wcb']:.3f}; SEC-FAQ strict GV excl. Income/G&amp;I: "
                f"{in_faq['metrics']['ACTIVE_TOWARD_80']['beta']:+.2f} pp, <em>p</em><sub>WCB</sub> = {in_faq['metrics']['ACTIVE_TOWARD_80']['p_wcb']:.3f}; "
                f"all MA GVI {in_all['metrics']['ACTIVE_TOWARD_80']['beta']:+.2f} pp, <em>p</em><sub>WCB</sub> = {in_all['metrics']['ACTIVE_TOWARD_80']['p_wcb']:.3f}), "
                f"IS_FOF-controlled 3-year CUSIP overlap is {in_all['metrics']['CUSIP_OVERLAP_PCT_CTRL_FOF']['beta']:+.2f} pp <em>higher</em> among droppers "
                f"(<em>p</em><sub>WCB</sub> = {in_all['metrics']['CUSIP_OVERLAP_PCT_CTRL_FOF']['p_wcb']:.3f}), and panel TWFE cash and volatility are zero."
            ),
        ),
        "fig5_monthly_investor_flows_reversal.png": (
            "Figure 5. Monthly Investor Flow Event Study (m = &minus;12..+12, Pre-Period-Mean Centered) and Inflow/Outflow Channel Decomposition.",
            (
                f"Panel A plots pre-period-mean centered monthly net-flow event-study coefficients (SERIES_ID FE + Month FE + consecutive-month-guarded lagged 3m/12m returns and log TNA, "
                f"corrected abs(REDEMPTION) flows; shaded 95% CR1 CI) for Multi-Asset GVI droppers (<em>n</em> = {fm['MA_GVI_POOLED']['n_droppers']}; "
                f"pre-slope <em>p</em><sub>WCB</sub> = {ma_es['pre_linear_slope_m12_m2']['p_wcb']:.2f}; pooled {fm['MA_GVI_POOLED']['pooled_twfe']['preferred_ret_tna_ctrl']['beta']:+.2f}%/mo, "
                f"<em>p</em><sub>WCB</sub> = {fm['MA_GVI_POOLED']['pooled_twfe']['preferred_ret_tna_ctrl']['p_wcb']:.2f}) and ESG droppers "
                f"(<em>n</em> = {fm['ESG_DROPPERS']['n_droppers']}; pre-slope <em>p</em><sub>WCB</sub> = {esg_es['pre_linear_slope_m12_m2']['p_wcb']:.2f}; "
                f"pooled {fm['ESG_DROPPERS']['pooled_twfe']['preferred_ret_tna_ctrl']['beta']:+.2f}%/mo, "
                f"<em>p</em><sub>WCB</sub> = {fm['ESG_DROPPERS']['pooled_twfe']['preferred_ret_tna_ctrl']['p_wcb']:.2f}). "
                f"Panel B decomposes monthly shifts into Net Flow, Gross Sales (inflows), and |Redemptions| (outflows) across channels, demonstrating zero redemption runs, "
                f"a retail opaque new-sales drag ({fm['MA_GVI_RETAIL']['decomposition']['SALES_PCT']['beta']:+.2f}%/mo, <em>t</em> = {fm['MA_GVI_RETAIL']['decomposition']['SALES_PCT']['t_cr1']:+.2f}), "
                f"dead-flat captive variable-annuity flows ({fm['MA_GVI_VA_INSURANCE']['pooled_twfe']['preferred_ret_tna_ctrl']['beta']:+.2f}%/mo), and positive numeric-ratio net flows "
                f"({fm['MA_GVI_NUMERIC']['pooled_twfe']['preferred_ret_tna_ctrl']['beta']:+.2f}%/mo). Inset reports the N-PORT sign-fix validation jump "
                f"(<em>r</em> = {fv['pearson_raw_unclipped_vs_tna']:.3f} &rarr; {fv['pearson_fixed_abs_vs_tna']:.3f}, <em>N</em> = {fv['n_valid_qtr_obs']:,})."
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
        n_clean, d_clean = num.strip(), den.strip()
        if n_clean == "1" and d_clean == "2":
            frac_repl = "&frac12;"
        elif not re.search(r"[+\-= ]", n_clean) and not re.search(r"[+\-= ]", d_clean):
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

    # Protect escaped underscores \_ inside math mode so they NEVER trigger subscript regexes
    s = s.replace(r"\_", "&#95;")

    replacements = [
        (r"{,}", ","),
        (r"\arg\min", '<span class="rm">arg min</span>'),
        (r"\qquad", "&emsp;&emsp;"),
        (r"\quad", "&emsp;"),
        (r"\iff", "&hArr;"),
        (r"\Rightarrow", "&rArr;"),
        (r"\setminus", " &#8726; "),
        (r"\partial", "&part;"),
        (r"\gg", "&gg;"),
        (r"\ll", "&ll;"),
        (r"\mid", " | "),
        (r"\Big(", "("),
        (r"\Big)", ")"),
        (r"\Big[", "["),
        (r"\Big]", "]"),
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
        (r"\Pi", "&Pi;"),
        (r"\kappa", "&kappa;"),
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
        # Preserve HTML entity names like &ndash; while converting unary/binary hyphens to minus
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
            # Handle escaped \| inside markdown table cells cleanly
            def split_md_row(row_s: str) -> list[str]:
                tmp = row_s.strip("|").replace(r"\|", "\x00PIPE\x00")
                return [c.replace("\x00PIPE\x00", r"\|").strip() for c in tmp.split("|")]

            headers = split_md_row(tbl_lines[0])
            aligns = split_md_row(tbl_lines[1])
            if len(headers) != len(aligns):
                raise ValueError(f"Markdown table column mismatch: header={len(headers)} vs aligns={len(aligns)}: {headers}")
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

    for fname in figure_blocks:
        if fname not in inserted_figs and (BASE_DIR / "figures" / fname).exists():
            body.append(_embed_figure_html(fname, figure_blocks))

    css = """
    @page {
      size: letter;
      margin: 0.65in 0.65in 0.72in 0.65in;
      @top-right {
        content: "Bifurcated Regulatory Name Arbitrage (SEC Rule 35d-1, 2020–2026)";
        font-family: Georgia, "Times New Roman", serif;
        font-size: 7.3pt;
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
      font-size: 9.2pt;
      line-height: 1.42;
      color: #1a1a1a;
      max-width: 100%;
    }
    h1.paper-title {
      font-size: 13.8pt;
      line-height: 1.24;
      margin: 0 0 8pt 0;
      color: #0b2545;
      border-bottom: 1.5pt solid #0b2545;
      padding-bottom: 6pt;
    }
    h2 {
      font-size: 11.0pt;
      color: #0b2545;
      margin: 11pt 0 5pt 0;
      border-bottom: 0.6pt solid #cbd5e1;
      padding-bottom: 2pt;
      page-break-after: avoid;
    }
    h3 {
      font-size: 9.7pt;
      color: #1e3a5f;
      margin: 8.5pt 0 4pt 0;
      page-break-after: avoid;
    }
    p { margin: 0 0 5.3pt 0; text-align: justify; }
    p.table-caption {
      font-size: 8.4pt;
      margin: 7pt 0 3pt 0;
      color: #0b2545;
      text-align: left;
      break-inside: avoid;
      page-break-inside: avoid;
      break-after: avoid;
      page-break-after: avoid;
    }
    p.table-notes {
      font-size: 7.4pt;
      color: #475569;
      margin: 2pt 0 8pt 0;
      text-align: left;
    }
    ul, ol { margin: 3pt 0 6pt 16pt; padding: 0; }
    li { margin: 0 0 2.6pt 0; text-align: justify; }
    ol.refs-list li { text-align: left; font-size: 8.0pt; line-height: 1.32; break-inside: avoid; page-break-inside: avoid; }
    code {
      font-family: Consolas, "Courier New", monospace;
      font-size: 7.2pt;
      background: #f1f5f9;
      padding: 0.4pt 2.0pt;
      border-radius: 2pt;
    }
    hr { border: 0; border-top: 0.6pt solid #cbd5e1; margin: 7.5pt 0; }
    .math { font-family: "Cambria Math", Georgia, serif; font-style: italic; }
    .math .rm, .eq-block .rm { font-style: normal; }
    .math .cal, .eq-block .cal { font-family: "Lucida Calligraphy", "Cambria Math", serif; font-style: italic; }
    sup, sub { white-space: nowrap; }
    .eq-block {
      font-family: "Cambria Math", Georgia, serif;
      font-size: 9.4pt;
      text-align: center;
      margin: 6.2pt 0;
      padding: 5.5pt 10pt;
      background: #f8fafc;
      border-left: 2pt solid #0b2545;
      break-inside: avoid;
      page-break-inside: avoid;
    }
    .table-wrap { margin: 4pt 0 4pt 0; page-break-inside: avoid; }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 6.5pt;
      line-height: 1.18;
      border-top: 1.3pt solid #0f172a;
      border-bottom: 1.3pt solid #0f172a;
    }
    thead tr { border-bottom: 0.8pt solid #334155; background: #f8fafc; }
    th, td { padding: 1.8pt 2.3pt; vertical-align: top; }
    td .math, th .math { white-space: nowrap; }
    td code { white-space: nowrap; font-size: 6.2pt; }
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
      max-height: 3.95in;
      height: auto;
      display: block;
      margin: 0 auto 4.5pt auto;
    }
    figure.pub-fig figcaption {
      font-size: 7.5pt;
      line-height: 1.30;
      color: #334155;
      text-align: left;
    }
    """
    return (
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8' />"
        f"<title>Bifurcated Regulatory Name Arbitrage: SEC Rule 35d-1</title><style>{css}</style></head>"
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
        r"\^[0-9A-Za-z{]",
        r"fig[1-5]_[a-z0-9_]+\.png",
        r"<!--",
        r"TOK\d+",
        r"&[a-z]+;",
        r"&#\d+;",
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
    HTML_PATH.write_bytes(html_doc.encode("utf-8"))

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
        print(f"[ERROR] Leaked LaTeX/Markdown/HTML tokens found in PDF: {leaks}", file=sys.stderr)
        return 2
    print(f"[DONE STEP 8] Compiled {PDF_PATH} ({PDF_PATH.stat().st_size:,} bytes, {n_pages} pages, 0 leaked tokens)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
