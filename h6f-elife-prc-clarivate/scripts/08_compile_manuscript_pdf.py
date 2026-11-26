"""Step 8: Compile manuscript_h6f_boost.md + embedded 300-DPI figures into a
publication-grade PDF (manuscript_h6f_boost.pdf) via escaped-underscore-safe
balanced LaTeX->HTML + Microsoft Edge --headless=new --print-to-pdf, with
strict zero-leak verification.
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

BASE_DIR = Path(r"D:\AI_Science\antigravity\h6f_boost_elife_prc_clarivate_20261126")
MD_PATH = BASE_DIR / "manuscript_h6f_boost.md"
HTML_PATH = BASE_DIR / "manuscript_h6f_boost.html"
PDF_PATH = BASE_DIR / "manuscript_h6f_boost.pdf"
RES_DIR = BASE_DIR / "results"
EDGE_EXE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


def build_dynamic_figure_blocks() -> dict[str, tuple[str, str]]:
    """Build figure captions 100% dynamically from saved JSON receipts (zero hardcoded estimates)."""
    p4 = json.loads((RES_DIR / "04_pillar1_2_results.json").read_bytes().decode("utf-8"))
    p5 = json.loads((RES_DIR / "05_pillar3_4_results.json").read_bytes().decode("utf-8"))

    t_inc = p4["pillar1_transition_mature"]["v1_Incomp_Inad"]
    e450 = p4["pillar1_esci_solid_cliff"]["win_450d"]
    p450 = e450["fe_up_among_vors"]["params"]["post_esci"]
    p450_d = e450["fe_up_among_vors_donut"]["params"]["post_esci"]
    g_oa = p4["pillar2_v1_gradient_and_autopsy"]["vor_true_v1_oa_post_ppml"]["params"]["v1_incomp_d"]
    g_oa_f = p4["pillar2_v1_gradient_and_autopsy"]["vor_flawed_vor_oa_post_ppml"]["params"]["fin_incomp_d"]
    g_pv_sig = p4["pillar2_v1_gradient_and_autopsy"]["vor_true_v1_pv_ppml"]["params"]["v1_sig_imp"]
    u_inc = p4["pillar2_upgrade_payoff"]["v1_Incomp_VoRs"]
    u_sol = p4["pillar2_upgrade_payoff"]["v1_Solid_VoRs"]
    ev_raw = u_inc["ev_raw_summary"]
    ed = p5["pillar3a_editorial_cushioning"]
    v1_inc_q = ed["v1_quality_shift"]["v1_incomp"]["base_subj_fe"]["params"]["post_clar_eid"]
    sc_all_c = p5["pillar3b_expanded_sc_and_did"]["synthetic_control"]["log_n_all"]["sc_clarivate_vs_23_24"]
    sc_all_35 = p5["pillar3b_expanded_sc_and_did"]["synthetic_control"]["log_n_all"]["sc_clarivate_exp35"]
    sc_cn_f = p5["pillar3b_expanded_sc_and_did"]["synthetic_control"]["log_n_CN"]["sc_full_pre_clarivate"]
    sc_cn_c = p5["pillar3b_expanded_sc_and_did"]["synthetic_control"]["log_n_CN"]["sc_clarivate_vs_23_24"]
    sc_cn_35 = p5["pillar3b_expanded_sc_and_did"]["synthetic_control"]["log_n_CN"]["sc_full_pre_exp35"]
    es_cn_24h2 = p5["pillar3b_expanded_sc_and_did"]["event_study_2021H1_2026H1"]["log_n_CN"]["2024H2"]["did_vs_2022H2"]
    pi = p5["pillar4_global_metric_dependence"]["senior_pi_last_author_shares"]
    reg = p5["pillar4_global_metric_dependence"]["institutional_regime_test"]
    ext = p5["pillar4_global_metric_dependence"]["external_validation_blog_9nations"]

    return {
        "fig1_transition_and_esci_norms.png": (
            "Figure 1. Complete Longitudinal v1 &rarr; VoR Revision Architecture and Clarivate ESCI Solid-Threshold Experiment.",
            (
                f"Panel A decomposes final outcomes for all mature 2023&ndash;2024 <em>eLife</em> PRC cohorts (<em>N</em> = {p4['n_mature_2023_2024']:,}): "
                f"among initially <em>Incomplete/Inadequate</em> v1 preprints (<em>n</em> = {t_inc['n_total']}), {t_inc['pct_vor']:.1f}% convert to VoR "
                f"and {t_inc['pct_vor_upgraded']:.1f}% of those VoRs ({t_inc['pct_vor_upgraded_to_solid']:.1f}% crossing to <em>Solid+</em>) upgrade their "
                f"Strength of Evidence over a mean {t_inc['mean_rev_lag_up']:.1f}-day lag. "
                f"Panel B tests Clarivate&rsquo;s December 2024 ESCI <em>Solid</em>-threshold indexing rule across fixed uncensored 365-, 450-, and 540-day "
                f"windows on v1 <em>Incomplete</em> manuscripts: 450-day full Subject-FE DiD is {100*p450['beta']:+.2f} pp (<em>p</em><sub>WCB</sub> = {p450.get('p_wcb', 0):.3f}; "
                f"donut excluding 2024Q3: {100*p450_d['beta']:+.2f} pp, <em>p</em> = {p450_d['p']:.2f}), confirming intrinsic scientific norms sustain revision."
            ),
        ),
        "fig2_evaluation_market_paradox.png": (
            "Figure 2. First-Impression v1 Gradient, VoR-Date Autopsy, and Zero Sustained Upgrade Payoff vs. Version-Release Traffic.",
            (
                f"Panel A contrasts Subject-clustered (<em>G</em> = {p4['pillar2_v1_gradient_and_autopsy']['vor_true_v1_oa_post_ppml']['G']}) PPML estimates across mature VoRs inside FE "
                f"(<em>N</em> = {p4['pillar2_v1_gradient_and_autopsy']['vor_true_v1_oa_post_ppml']['n']:,}): "
                f"strict v1-date alignment exposes a {g_oa['pct']:+.1f}% strictly post-v1 citation penalty for v1 <em>Incomplete</em> "
                f"(<em>p</em> = {g_oa['p']:.2e}) that flawed VoR-date alignment erases to {g_oa_f['pct']:+.1f}% (<em>p</em> = {g_oa_f['p']:.3f}), "
                f"while live <em>eLife</em> page-views respond primarily to headline v1 <em>Significance</em> ({g_pv_sig['pct']:+.1f}%, <em>p</em> = {g_pv_sig['p']:.4f}). "
                f"Panel B reports Subject-clustered upgrade effects within v1 <em>Incomplete</em> VoRs (<em>N</em> = {u_inc['ppml_oa_post_v1']['n']:,} total; "
                f"<em>N</em> = {u_inc['ols_did_log_pv_rate_clean']['n']:,} untruncated v1 &ge; 2023-11 monthly; <em>N</em> = {u_inc['ev_pv_m0']['n']:,} local VoR event study): "
                f"upgrading to <em>Solid+</em> yields zero sustained gain in citations ({u_inc['ppml_oa_post_v1']['params']['str_upgraded_to_solid']['pct']:+.1f}%, "
                f"<em>p</em> = {u_inc['ppml_oa_post_v1']['params']['str_upgraded_to_solid']['p']:.3f}), untruncated monthly rate DiD "
                f"({u_inc['ols_did_log_pv_rate_clean']['params']['str_upgraded_to_solid']['beta']:+.3f}, <em>p</em><sub>WCB</sub> = {u_inc['ols_did_log_pv_rate_clean']['params']['str_upgraded_to_solid'].get('p_wcb', 0):.3f}), "
                f"or local VoR post-months 1&ndash;6 ({u_inc['ev_pv_p16']['params']['str_upgraded_to_solid']['beta']:+.3f}, <em>p</em><sub>WCB</sub> = {u_inc['ev_pv_p16']['params']['str_upgraded_to_solid'].get('p_wcb', 0):.3f}), "
                f"with an identical VoR month-0 spike ({ev_raw['dlog_pv_ev_m0']['upgraded_mean']:+.2f} vs. {ev_raw['dlog_pv_ev_m0']['unchanged_mean']:+.2f}); "
                f"reader traffic responds instead to version-release events ({u_inc['traj_dlog_pv_12_21_ctrl_ver']['params']['cr_n_versions']['beta']:+.3f} per version in <em>Incomplete</em>, "
                f"<em>p</em> = {u_inc['traj_dlog_pv_12_21_ctrl_ver']['params']['cr_n_versions']['p']:.3f}; "
                f"{u_sol['traj_dlog_pv_12_21_ctrl_ver']['params']['cr_n_versions']['beta']:+.3f} in <em>Solid</em>, "
                f"<em>p</em> = {u_sol['traj_dlog_pv_12_21_ctrl_ver']['params']['cr_n_versions']['p']:.4f})."
            ),
        ),
        "fig3_clarivate_two_margin_cushioning.png": (
            "Figure 3. Clarivate October 24, 2024 Delisting Shock: Submission Velocity Collapse and Two-Margin Editorial Cushioning.",
            (
                f"Panel A tracks implied quarterly submissions from sequential manuscript ID velocity calibrated against <em>N</em> = {ed['n_sfr_sample']} "
                f"exact <code>sentForReview</code> timestamps (Spearman <em>r</em> = {ed['spearman_eid_sfr_r']:.4f}), documenting a {ed['vel_drop_pct']:.1f}% "
                f"intake contraction ({ed['pre_vel_mean_subs_q']:,.0f} &rarr; {ed['post_vel_mean_subs_q']:,.0f}/qtr). Panel B plots peer-review acceptance across "
                f"{len(ed['blocks_500'])} sequential 500-<code>eid</code> blocks (<code>eid</code> 87.5k&ndash;112k): acceptance jumped discontinuously from "
                f"{ed['acc_pre_mean_pct']:.2f}% to {ed['acc_post_mean_pct']:.2f}% ({ed['acc_jump_pp']:+.2f} pp, HAC <em>t</em> = {ed['acc_jump_hac_t']:+.2f}, "
                f"Perm <em>p</em> = {ed['acc_jump_perm_p']:.4f}, Sup-Wald <em>F</em> = {ed['sup_wald_best_F_hac']:.1f}) while v1 <em>Incomplete</em> quality "
                f"remained completely invariant ({100*v1_inc_q['beta']:+.2f} pp, <em>p</em> = {v1_inc_q['p']:.3f})."
            ),
        ),
        "fig4_expanded_synthetic_control.png": (
            f"Figure 4. Expanded {sc_cn_f['n_units']}-Journal Strict (&amp; {sc_cn_35['n_units']}-Journal Expanded) Abadie&ndash;Diamond&ndash;Hainmueller Synthetic Control and Event Study.",
            (
                f"Panel A displays exact in-space placebo gap trajectories for China output (<code>log_n_CN</code>) under Full-Pre (<em>T</em><sub>0</sub> = 7) "
                f"strictly convex ADH Synthetic Control across all <em>N</em> = {sc_cn_f['n_units']} strict (&ge;90% true country coverage every half-year) peer biology journals: "
                f"<em>eLife</em> diverges sharply post-delisting ({sc_cn_f['treated']['post_mean_gap']:+.3f} log pts, RMSPE Rank {sc_cn_f['rmspe_ratio_rank_of_N']}/{sc_cn_f['n_units']}, "
                f"<em>p</em> = {sc_cn_f['p_rmspe_ratio']:.4f}; Clarivate <em>T</em><sub>0</sub> = 3 gap {sc_cn_c['treated']['post_mean_gap']:+.3f}, Rank {sc_cn_c['rmspe_ratio_rank_of_N']}/{sc_cn_c['n_units']}; "
                f"Expanded <em>N</em> = {sc_cn_35['n_units']} Rank {sc_cn_35['rmspe_ratio_rank_of_N']}/{sc_cn_35['n_units']}, <em>p</em> = {sc_cn_35['p_rmspe_ratio']:.4f}). "
                f"Panel B plots half-yearly DiD event-study paths (base 2022H2) exposing the two-phase inverted-V China surge ({es_cn_24h2:+.2f} log pts by 2024H2) and post-Clarivate collapse "
                f"alongside Total Volume Clarivate SC ({sc_all_c['treated']['post_mean_gap']:+.3f}, Rank {sc_all_c['rmspe_ratio_rank_of_N']}/{sc_all_c['n_units']}, "
                f"<em>p</em> = {sc_all_c['p_rmspe_ratio']:.4f}; Expanded Rank {sc_all_35['rmspe_ratio_rank_of_N']}/{sc_all_35['n_units']}, <em>p</em> = {sc_all_35['p_rmspe_ratio']:.4f})."
            ),
        ),
        "fig5_asymmetric_global_jif_dependence.png": (
            "Figure 5. Two-Phase Asymmetric Global Impact-Factor Dependence: Senior-PI Geography and 12-Nation Regime Test.",
            (
                f"Panel A tracks Senior/Last-Author PI shares inside <em>eLife</em> PRC (2023H2&ndash;2026H1): China surged to {pi['2024H2']['pi_CN_pct']:.1f}% "
                f"before crashing overnight to {pi['2025H1']['pi_CN_pct']:.1f}% in 2025H1 while US Senior-PI share held flat ({pi['2024H2']['pi_US_pct']:.1f}% "
                f"&rarr; {pi['2026H1']['pi_US_pct']:.1f}%). Panel B ranks Phase-2 Clarivate DiD output shifts across 12 major research nations: JIF-codified "
                f"systems (CN, ES, IT; mean {reg['jif_mean_p2_pct']:+.1f}%) contracted {reg['jif_mean_p2_pct'] - reg['dora_mean_p2_pct']:.1f} pp more "
                f"severely than DORA-reformed systems (7 nations; mean {reg['dora_mean_p2_pct']:+.1f}%, exact permutation <em>p</em> = "
                f"{reg['exact_comb_perm_p_1sided']:.4f}), tracking <em>eLife</em>&rsquo;s March 2026 official submission drops "
                f"(<em>N</em> = {ext['n_countries']}, Spearman <em>&rho;</em> = {ext['spearman_rho']:.3f}, <em>p</em> = {ext['spearman_p']:.3f})."
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
        (r"\|", "&#8214;"),
        (r"\ldots", "&hellip;"),
        (r"\dots", "&hellip;"),
        (r"\;", "&ensp;"),
        (r"\,", "&thinsp;"),
        (r"\!", ""),
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
        # Honor Markdown trailing double-space line breaks (`  `) cleanly
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
        content: "Intrinsic Revision Norms & Asymmetric Impact-Factor Dependence (eLife PRC, 2021–2026)";
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
      font-size: 7.3pt;
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
    th, td { padding: 1.8pt 2.3pt; vertical-align: top; }
    td .math, th .math { white-space: nowrap; }
    td code { white-space: nowrap; font-size: 6.3pt; }
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
      max-height: 4.05in;
      height: auto;
      display: block;
      margin: 0 auto 4.5pt auto;
    }
    figure.pub-fig figcaption {
      font-size: 7.6pt;
      line-height: 1.30;
      color: #334155;
      text-align: left;
    }
    """
    return (
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8' />"
        f"<title>H6f Boost Manuscript</title><style>{css}</style></head>"
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
        r"\\mathbb\{",
        r"\\frac\{",
        r"\\mathcal\{",
        r"\bp_WCB\b",
        r"\^[0-9A-Za-z{]",
        r"fig[1-5]_[a-z0-9_]+\.png",
        r"<!--",
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
        print(f"[ERROR] Leaked LaTeX/Markdown/ASCII tokens found in PDF: {leaks}", file=sys.stderr)
        return 2
    print(f"[DONE STEP 8] Compiled {PDF_PATH} ({PDF_PATH.stat().st_size:,} bytes, {n_pages} pages, 0 leaked tokens)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
