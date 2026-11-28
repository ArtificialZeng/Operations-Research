"""Step 8 (v4): Compile BOTH manuscript_h6f_boost.md -> manuscript_h6f_boost.pdf
AND supplementary_h6f_scientometrics.md -> supplementary_h6f_scientometrics.pdf
with 100% dynamic JSON-driven figure captions, isolated Edge --headless=new
--user-data-dir=<tempdir>, and strict zero-leak verification.
"""
from __future__ import annotations

import base64
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from pypdf import PdfReader

BASE_DIR = Path(__file__).resolve().parents[1]
RES_DIR = BASE_DIR / "results"
EDGE_EXE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


def build_dynamic_figure_blocks() -> dict[str, tuple[str, str]]:
    """Build 100% dynamic figure titles and captions from saved v4 JSON receipts."""
    p3b = json.loads((RES_DIR / "03b_openalex_dedup_audit.json").read_bytes().decode("utf-8"))
    p9 = json.loads((RES_DIR / "09_v4_scientometrics_results.json").read_bytes().decode("utf-8"))
    p5 = json.loads((RES_DIR / "05_pillar3_4_results.json").read_bytes().decode("utf-8"))

    bs = p3b["by_stratum"]
    am = p3b["all_manifestations_post_v1"]
    eo = p3b["elife_only_post_v1"]
    reg_a = p3b["regression_impact_audit_sample"]
    rev = p9["covariate_audit_and_crossed_clock"]["reviewer_2285_exact_parity"]
    sc = p9["covariate_audit_and_crossed_clock"]["strict_v1_frozen"]
    ev = p9["equal_window_validation"]["by_sample"]
    incp = p9["equal_window_validation"]["incremental_predictive_power"]["all_v1_oa_next_yr"]
    att = p9["onsite_readership"]["complete_monthly_cohort_n1852"]
    fun = p9["revision_and_upgrade"]["funnel_by_v1_tier"]["v1_Incomp_Inad"]
    up = p9["revision_and_upgrade"]["upgrade_models"]
    si = p9["supplementary_indexing_cohort"]
    fh_v3 = si["fixed_horizon_v3_parity_fin_subj"]["450"]
    ed = p5["pillar3a_editorial_cushioning"]
    sc_all = p5["pillar3b_expanded_sc_and_did"]["synthetic_control"]["log_n_all"]["sc_clarivate_vs_23_24"]
    sc_cn = p5["pillar3b_expanded_sc_and_did"]["synthetic_control"]["log_n_CN"]["sc_full_pre_clarivate"]
    reg_g = p5["pillar4_global_metric_dependence"]["institutional_regime_test"]
    ext = p5["pillar4_global_metric_dependence"]["external_validation_blog_9nations"]

    vor_split = bs["VoR_v1Low"]["n_split_oa_works"] + bs["VoR_v1SolidPlus"]["n_split_oa_works"]
    nv_split = bs["NonVoR_v1Low"]["n_split_oa_works"] + bs["NonVoR_v1SolidPlus"]["n_split_oa_works"]

    return {
        "fig1_v4_measurement_and_dedup_audit.png": (
            f"Figure 1. Stratified OpenAlex Multi-DOI Canonicalization and Citing-Work ID Deduplication Audit (N = {p3b['n_audited_articles']}).",
            (
                f"Panel A contrasts OpenAlex work-splitting rates and aggregate yearly-max-to-union citation ratios across four strata "
                f"(mean {p3b['mean_queried_dois_per_article']} DOIs queried per manuscript): only {vor_split}/120 ({100*vor_split/120:.1f}%) "
                f"of finalized VoRs remain split across multiple OpenAlex Work IDs, compared with {nv_split}/80 ({100*nv_split/80:.1f}%) "
                f"of non-VoR reviewed preprints (where bioRxiv/medRxiv and <em>eLife</em> records remain unmerged). "
                f"Panel B plots exact deduplicated citing-work ID unions against yearly-max proxies on the log(1 + count) scale: "
                f"<em>r</em> = {am['pearson_r']:.4f} (<em>&rho;</em> = {am['spearman_rho']:.4f}, aggregate ratio {am['agg_ymax_to_union_ratio']:.4f}) across all DOIs "
                f"and <em>r</em> = {eo['pearson_r']:.5f} (exact match {eo['exact_match_pct']:.1f}%) across <em>eLife</em> DOIs alone, yielding nearly identical "
                f"audit-sample PPML estimates ({reg_a['all_audit_all_manifest_union_post']['pct']:+.1f}% vs. {reg_a['all_audit_all_manifest_ymax_post']['pct']:+.1f}%). "
                f"Inset summarizes the look-ahead authorship audit on <em>N</em> = {rev['n']:,} VoRs ({rev['n_max_authors_gt_v1']}/{rev['n']:,} exceeded <em>v</em><sub>1</sub> authors; "
                f"{rev['leaked_max_authors']['pct']:+.2f}% &rarr; {rev['frozen_v1_authors']['pct']:+.2f}%)."
            ),
        ),
        "fig2_v4_equal_window_predictive_value.png": (
            "Figure 2. Crossed 2&times;2 Date-Clock / Assessment-Timing Sensitivity and Equal-Window Validation Across All-v1, VoR, and Non-VoR Samples.",
            (
                f"Panel A holds the VoR estimation sample fixed under strictly frozen <em>v</em><sub>1</sub> covariates (<em>v</em><sub>1</sub> authors and <em>v</em><sub>1</sub> primary subject) "
                f"and varies assessment timing (initial vs. final) and fixed-effect quarter clock (<em>v</em><sub>1</sub> vs. VoR quarter) separately: "
                f"switching only the quarter clock attenuates post-<em>v</em><sub>1</sub> estimates from {sc['oa_post_v1_cites']['v1_v1q']['pct']:+.1f}% to {sc['oa_post_v1_cites']['v1_finq']['pct']:+.1f}% "
                f"(next full calendar year: {sc['oa_next_full_year']['v1_v1q']['pct']:+.1f}% &rarr; {sc['oa_next_full_year']['v1_finq']['pct']:+.1f}%), while substituting final ratings removes the signal. "
                f"Panel B extends equal-window validation to unselected cohorts including non-VoR reviewed preprints: initial below-<em>Solid</em> ratings predict "
                f"{ev['all_v1']['oa_next_full_year']['v1_low']['pct']:+.1f}% next-full-year citations across all mature <em>v</em><sub>1</sub> preprints "
                f"(<em>N</em> = {ev['all_v1']['oa_next_full_year']['v1_low']['n']:,}, &Delta;Deviance = {incp['deviance_reduction']:.1f}, &Delta;Pseudo-<em>R</em><sup>2</sup> = +{incp['delta_pseudo_r2_pp']:.2f} pp), "
                f"{ev['vor_only']['oa_next_full_year']['v1_low']['pct']:+.1f}% within VoRs, and {ev['non_vor_only_subj_q']['oa_post_v1_cites']['v1_low']['pct']:+.1f}% post-<em>v</em><sub>1</sub> citations "
                f"(<em>p</em> = {ev['non_vor_only_subj_q']['oa_post_v1_cites']['v1_low']['p']:.4f}) within non-VoR reviewed preprints."
            ),
        ),
        "fig3_v4_onsite_readership_and_funnel.png": (
            "Figure 3. Observational Onsite Readership Associations and Four-Stage Public Revision, VoR Conversion, and Upgrade Funnel.",
            (
                f"Panel A reports discipline-clustered PPML associations on the untruncated monthly readership cohort "
                f"(<em>v</em><sub>1</sub> &ge; 2023-11, <em>N</em> = {att['pv_first_3m']['v1_low']['n']:,}, strictly frozen <em>v</em><sub>1</sub> covariates + posting day): "
                f"higher <em>Significance</em> tiers positively predict page-views (<em>Important</em> {att['pv_first_3m']['v1_imp']['pct']:+.1f}% early, {att['pv_total']['v1_imp']['pct']:+.1f}% cumulative), "
                f"whereas below-<em>Solid</em> evidence predicts lower cumulative PDF downloads ({att['dl_total']['v1_low']['pct']:+.1f}%, <em>p</em> = {att['dl_total']['v1_low']['p']:.4f}); "
                f"estimates reflect observational traffic mixtures overlapping <em>eLife</em>&rsquo;s June 2024 discoverability redesign rather than causal badge clicks. "
                f"Panel B separates outcomes across mature 2023&ndash;2024 tiers (<em>N</em> = {p9['cohort_summary']['n_mature_2023_2024']:,}): "
                f"among {fun['n_total']:,} <em>v</em><sub>1</sub> below-<em>Solid</em> preprints, {fun['n_posted_revision']} ({fun['pct_posted_revision']:.1f}%) posted public revisions, "
                f"{fun['n_vor']} ({fun['pct_vor']:.1f}%) converted to VoR, and {fun['n_vor_upgraded_any']} ({fun['pct_all_upgraded_any']:.1f}% unconditional; "
                f"{fun['pct_vor_upgraded_any']:.1f}% VoR-conditional) upgraded evidence ratings over a mean {fun['mean_rev_lag_up_days']:.1f}-day calendar interval; "
                f"across the April 2023+ cohort, {si['apr2023_lower_rated_vors_with_posted_revision']}/{si['apr2023_lower_rated_vors']} "
                f"({si['apr2023_lower_rated_vors_with_revision_pct']:.1f}%) final below-<em>Solid</em> VoRs posted public revisions."
            ),
        ),
        "fig4_v4_upgrade_precision_and_trajectories.png": (
            "Figure 4. Observational Upgrade-to-Solid+ Precision with Explicit Equivalence Bounds and Version-Release Traffic Trajectories.",
            (
                f"Panel A plots observational associations for upgrading from below-<em>Solid</em> to <em>Solid+</em> within finalized VoRs against pre-specified &plusmn;15% and &plusmn;20% equivalence margins: "
                f"benchmark covariates yield {up['bench_v3_parity_oa_post_v1']['pct']:+.1f}% [{up['bench_v3_parity_oa_post_v1']['pct_ci95_lo']:+.1f}%, {up['bench_v3_parity_oa_post_v1']['pct_ci95_hi']:+.1f}%] "
                f"(TOST &plusmn;20% <em>p</em> = {up['bench_v3_parity_oa_post_v1']['tost_pm20']:.3f}, &plusmn;15% <em>p</em> = {up['bench_v3_parity_oa_post_v1']['tost_pm15']:.3f}), "
                f"and strictly frozen <em>v</em><sub>1</sub> covariates yield {up['strict_v1_oa_post_v1']['pct']:+.1f}% [{up['strict_v1_oa_post_v1']['pct_ci95_lo']:+.1f}%, {up['strict_v1_oa_post_v1']['pct_ci95_hi']:+.1f}%] "
                f"(TOST &plusmn;20% <em>p</em> = {up['strict_v1_oa_post_v1']['tost_pm20']:.3f}, &plusmn;15% <em>p</em> = {up['strict_v1_oa_post_v1']['tost_pm15']:.3f}), "
                f"demonstrating wide uncertainty incompatible with claiming zero return. Panel B contrasts version-release events against rating-change terms: "
                f"VoR publication triggers an identical raw month-0 view spike ({up['raw_ev_m0_summary']['pv_m0_upgraded_mean']:+.2f} vs. {up['raw_ev_m0_summary']['pv_m0_unchanged_mean']:+.2f} log pts; "
                f"<em>N</em> = {up['raw_ev_m0_summary']['n_clean_ev']}), while each additional posted version predicts sustained months 12&ndash;21 traffic "
                f"({up['version_release_m12_21_incomp']['cr_n_versions']['beta']:+.2f} log pts in below-<em>Solid</em>, <em>p</em><sub>WCB</sub> = {up['version_release_m12_21_incomp']['cr_n_versions']['p_wcb']:.3f}; "
                f"{up['version_release_m12_21_solid']['cr_n_versions']['beta']:+.2f} in <em>Solid</em>, <em>p</em><sub>WCB</sub> = {up['version_release_m12_21_solid']['cr_n_versions']['p_wcb']:.3f})."
            ),
        ),
        "figs1_si_indexing_cohort_cif.png": (
            "Figure S1. Exploratory Cohort Cumulative Incidence and Fixed-Horizon Contrasts Around the December 10, 2024 Web of Science &amp; Scopus Notice.",
            (
                f"Panel A plots unadjusted Aalen&ndash;Johansen competing-risks cumulative incidence comparing earlier (<em>v</em><sub>1</sub> &lt; Oct 1, 2024; <em>n</em> = {si['pre_n']}) "
                f"and later (<em>v</em><sub>1</sub> &ge; Dec 10, 2024; <em>n</em> = {si['post_n']}) below-<em>Solid</em> cohorts, disclosing explicitly that "
                f"{si['pre_450_vors_after_announcement']}/{si['pre_450_vors']} ({si['pct_pre_450_vors_crossing_announcement']:.1f}%) earlier-cohort 450-day VoRs finalized after the Dec 10 notice. "
                f"Panel B plots complete-followup subject-adjusted linear probability contrasts: at 450 days, final below-<em>Solid</em> VoR "
                f"({100*fh_v3['lower_rated_vor']['beta']:+.2f} pp [{100*fh_v3['lower_rated_vor']['ci95_lo']:+.2f}, {100*fh_v3['lower_rated_vor']['ci95_hi']:+.2f}]) "
                f"and posted public revision ({100*fh_v3['observed_revision']['beta']:+.2f} pp [{100*fh_v3['observed_revision']['ci95_lo']:+.2f}, {100*fh_v3['observed_revision']['ci95_hi']:+.2f}]) "
                f"cross zero and do not establish a causal policy effect."
            ),
        ),
        "figs2_si_id_velocity_and_sc.png": (
            "Figure S2. Exploratory Sequential Manuscript-ID Velocity Proxy and Published-Output Synthetic Control (30 Clean Biology Journals).",
            (
                f"Panel A plots implied quarterly ID velocity calibrated on <em>N</em> = {ed['n_sfr_sample']} <code>sentForReview</code> timestamps "
                f"(Spearman <em>r</em> = {ed['spearman_eid_sfr_r']:.4f}; {ed['vel_drop_pct']:.1f}% proxy contraction vs. <em>eLife</em>&rsquo;s reported &minus;55.4% official submission decline). "
                f"Panel B plots exploratory published-output synthetic-control gaps for China-affiliated articles across 30 clean biology journals "
                f"(Full-Pre <em>T</em><sub>0</sub> = 7 gap {sc_cn['treated']['post_mean_gap']:+.3f}, Rank {sc_cn['rmspe_ratio_rank_of_N']}/{sc_cn['n_units']}; "
                f"Total Published-Output SC gap {sc_all['treated']['post_mean_gap']:+.3f}, Rank {sc_all['rmspe_ratio_rank_of_N']}/{sc_all['n_units']}). "
                f"Both series measure published output or indirect ID velocity rather than confidential submission logs."
            ),
        ),
        "figs3_si_geographic_exploratory.png": (
            "Figure S3. Exploratory Senior-PI Geography and 12-Nation Published-Output Contrasts.",
            (
                f"Panel A tracks Senior/Last-Author PI shares inside published <em>eLife</em> PRC articles (2023H2&ndash;2026H1). "
                f"Panel B ranks exploratory Phase-2 published-output DiD shifts across 12 nations relative to peer biology donors: "
                f"3 JIF-codified nations averaged {reg_g['jif_mean_p2_pct']:+.1f}% vs. {reg_g['dora_mean_p2_pct']:+.1f}% among 7 DORA-reformed nations "
                f"(exact permutation <em>p</em> = {reg_g['exact_comb_perm_p_1sided']:.4f}), tracking <em>eLife</em>&rsquo;s published 9-nation submission declines "
                f"(Spearman <em>&rho;</em> = {ext['spearman_rho']:.3f}, <em>p</em> = {ext['spearman_p']:.4f}). Excluded from main claims for lack of submission/transfer micro-logs."
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
    s = expr.strip().replace(r"\$", "$")
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
        (r"\widehat{", "", "&#770;"),
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
        (r"^\top", "<sup>T</sup>"),
        (r"\top", "T"),
        (r"\left(", "("),
        (r"\right)", ")"),
        (r"\left[", "["),
        (r"\right]", "]"),
        (r"\left", ""),
        (r"\right", ""),
        (r"\exp", "exp"),
        (r"\log", "log"),
        (r"\ln", "ln"),
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


def convert_md_to_html(md_text: str, figure_blocks: dict[str, tuple[str, str]], running_head: str, doc_title: str) -> str:
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
            is_refs = bool(body and ("<h2>References</h2>" in body[-1] or "<h2>Supplementary References</h2>" in body[-1]))
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
    ol.refs-list li {{ text-align: left; font-size: 8.0pt; line-height: 1.32; break-inside: avoid; page-break-inside: avoid; }}
    code {{
      font-family: Consolas, "Courier New", monospace;
      font-size: 7.3pt;
      background: #f1f5f9;
      padding: 0.4pt 2.0pt;
      border-radius: 2pt;
    }}
    hr {{ border: 0; border-top: 0.6pt solid #cbd5e1; margin: 7.5pt 0; }}
    .math {{ font-family: "Cambria Math", Georgia, serif; font-style: italic; }}
    .math .rm, .eq-block .rm {{ font-style: normal; }}
    .math .cal, .eq-block .cal {{ font-family: "Lucida Calligraphy", "Cambria Math", serif; font-style: italic; }}
    sup, sub {{ white-space: nowrap; }}
    .eq-block {{
      font-family: "Cambria Math", Georgia, serif;
      font-size: 9.1pt;
      text-align: center;
      margin: 6.2pt 0;
      padding: 5.5pt 10pt;
      background: #f8fafc;
      border-left: 2pt solid #0b2545;
    }}
    .table-wrap {{ margin: 4pt 0 4pt 0; page-break-inside: avoid; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 6.8pt;
      line-height: 1.20;
      border-top: 1.3pt solid #0f172a;
      border-bottom: 1.3pt solid #0f172a;
    }}
    thead tr {{ border-bottom: 0.8pt solid #334155; background: #f8fafc; }}
    th, td {{ padding: 2.0pt 2.6pt; vertical-align: top; }}
    td .math, th .math {{ white-space: nowrap; }}
    td code {{ white-space: nowrap; font-size: 6.4pt; }}
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
      max-height: 4.05in;
      height: auto;
      display: block;
      margin: 0 auto 4.5pt auto;
    }}
    figure.pub-fig figcaption {{
      font-size: 7.55pt;
      line-height: 1.30;
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
        r"\\mathbb\{",
        r"\\frac\{",
        r"\\mathcal\{",
        r"\bp_WCB\b",
        r"\^[0-9A-Za-z{]",
        r"fig[s0-9]_[a-z0-9_]+\.png",
        r"<!--",
        r"TOK\d+",
    ]
    leaks = [pat for pat in bad_patterns if re.search(pat, full_txt)]
    return len(reader.pages), leaks


def compile_one(md_path: Path, pdf_path: Path, figure_blocks: dict[str, tuple[str, str]], running_head: str, doc_title: str) -> int:
    html_path = md_path.with_suffix(".html")
    md_text = md_path.read_text(encoding="utf-8")
    html_doc = convert_md_to_html(md_text, figure_blocks, running_head, doc_title)
    html_path.write_bytes(html_doc.encode("utf-8"))

    tmp_profile = Path(tempfile.mkdtemp(prefix="edge_h6f_v4_"))
    try:
        cmd = [
            str(EDGE_EXE),
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--user-data-dir={tmp_profile}",
            f"--print-to-pdf={pdf_path}",
            html_path.as_uri(),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
        if res.returncode != 0 or not pdf_path.exists() or pdf_path.stat().st_size < 50_000:
            print(f"[ERROR] Edge PDF compile failed for {pdf_path.name} rc={res.returncode}: {res.stderr}", file=sys.stderr)
            return 1
        n_pages, leaks = verify_pdf_zero_leaks(pdf_path)
        if leaks:
            print(f"[ERROR] Leaked tokens in {pdf_path.name}: {leaks}", file=sys.stderr)
            return 2
        print(f"[Compiled PDF] {pdf_path.name}: {pdf_path.stat().st_size:,} bytes, {n_pages} pages, 0 leaked tokens", flush=True)
        return 0
    finally:
        html_path.unlink(missing_ok=True)
        shutil.rmtree(tmp_profile, ignore_errors=True)


def main() -> int:
    if not EDGE_EXE.exists():
        print(f"[ERROR] Microsoft Edge not found at {EDGE_EXE}", file=sys.stderr)
        return 1
    figure_blocks = build_dynamic_figure_blocks()
    rc1 = compile_one(
        BASE_DIR / "manuscript_h6f_boost.md",
        BASE_DIR / "manuscript_h6f_boost.pdf",
        figure_blocks,
        "Version-Level Measurement & Predictive Validity of Public Peer Review (eLife PRC)",
        "Version-Level Measurement & Predictive Validity of Public Peer Review (eLife PRC)",
    )
    if rc1 != 0:
        return rc1
    rc2 = compile_one(
        BASE_DIR / "supplementary_h6f_scientometrics.md",
        BASE_DIR / "supplementary_h6f_scientometrics.pdf",
        figure_blocks,
        "Supplementary Information — eLife PRC Audits & Exploratory Indexing Analyses",
        "Supplementary Information — eLife PRC Audits & Exploratory Indexing Analyses",
    )
    return rc2


if __name__ == "__main__":
    sys.exit(main())
