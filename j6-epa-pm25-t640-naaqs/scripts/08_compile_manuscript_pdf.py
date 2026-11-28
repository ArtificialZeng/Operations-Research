"""Step 08 (v4 ES&T): Compile manuscript_j6_boost.md and supplementary_j6_est.md
with embedded 300-DPI figures into camera-ready zero-leak PDFs via balanced LaTeX->HTML
and Microsoft Edge --headless=new --user-data-dir=<tempdir> --print-to-pdf.
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from econ_utils import FIG_DIR, RES_DIR, WS_DIR
from pypdf import PdfReader

MD_MAIN = WS_DIR / "manuscript_j6_boost.md"
PDF_MAIN = WS_DIR / "manuscript_j6_boost.pdf"
PDF_MAIN_FALLBACK = WS_DIR / "manuscript_j6_est.pdf"
MD_SI = WS_DIR / "supplementary_j6_est.md"
PDF_SI = WS_DIR / "supplementary_j6_est.pdf"
EDGE_EXE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


def _fmt_p_html(p: float | None) -> str:
    if p is None or not math.isfinite(p):
        return "n/a"
    if p < 1e-4:
        exp = math.floor(math.log10(p))
        mant = p / (10.0**exp)
        return f"{mant:.2f} &times; 10<sup>&minus;{abs(exp)}</sup>"
    if p < 0.001:
        return f"{p:.4f}"
    return f"{p:.3f}"


def build_dynamic_figure_blocks() -> dict[str, tuple[str, str]]:
    """Build all 4 Main ES&T and 2 SI figure titles/captions 100% dynamically from JSON receipts."""
    r1 = json.loads((RES_DIR / "01_appn_audit.json").read_text(encoding="utf-8"))
    r2 = json.loads((RES_DIR / "02_collocated_physics_speciation.json").read_text(encoding="utf-8"))
    r3 = json.loads((RES_DIR / "03_ee_triage_hms_unification.json").read_text(encoding="utf-8"))
    r11 = json.loads((RES_DIR / "11_v4_est_comprehensive_audit.json").read_text(encoding="utf-8"))

    cs = r11["common_support_audit"]
    all_c = cs["all_2023_2025"]
    h_c = cs["heavy_smoke_2023_2025"]
    ow = cs["overlap_weighted_region_x_frm_bin"]
    tr = all_c["triples_by_hms_level"]

    off_t = r11["official_fixed_2021_2025"]["t640_fw"]
    t1_t = off_t["tier_1"]
    t1_b = r11["official_fixed_2021_2025"]["bam"]["tier_1"]
    oot = r11["oot_prospective_rolling_5yr"]
    oot_a = oot["oot_a_conservative_r_excl"]["t640_fw"]["tier_1"]
    oot_b2 = oot["oot_b2_fire_proxy_hms_med_heavy"]["t640_fw"]["tier_1"]
    nb20 = t1_t["near_threshold_bands"]["frm_pm20pct"]

    sv_t = r11["smoke_vs_nonsmoke_controls"]["t640_fw"]
    mc_t = sv_t["matched_concentration_smoke_vs_nonsmoke"]
    gv_t = sv_t["ground_level_smoke_verification"]
    loro = r11["leave_epa_region_out_t640_tier1"]
    s1_t = r2["speciation_and_meteorology"]["t640_fw"]["model_s1_spec_met_level_site_cr1"]
    s2_t = r2["speciation_and_meteorology"]["t640_fw"]["model_s2_interactions_level_site_cr1"]
    s1_b = r2["speciation_and_meteorology"]["bam"]["model_s1_spec_met_level_site_cr1"]

    wf21 = r1["accounting"]["combined_site_reg_appn_11of12"]["matched_2123_waterfall"]
    rt_t = r2["rooftop_dv_lottery_2023_2025"]["t640_fw"]
    rt_b = r2["rooftop_dv_lottery_2023_2025"]["bam"]
    rb = r11["oot_reconstruction_benchmark_2021_2025"]
    u2_wcy = r3["unification_u2_t640_ee_flagging"]["borderline_within_county_year_fe_flag"]

    return {
        "fig1_est_caseflow_and_common_support.png": (
            "Figure 1. Collocated Network Case-Flow Attrition, EPA Region Common-Support Audit, and Same-Rooftop Triple Observations.",
            (
                f"Panel A compares the U.S. EPA Region distribution of threshold-matched NOAA HMS Heavy-smoke pairs "
                f"({t1_t['n_site_days']} aligned T640_FW&ndash;FRM pairs at {t1_t['n_sites']} sites vs. {t1_b['n_site_days']} "
                f"background-reference BAM&ndash;FRM pairs at {t1_b['n_sites']} sites, 2023&ndash;2025). Nearly one quarter (23.9%) "
                f"of BAM Heavy pairs lie in EPA Regions 9&ndash;10, where T640_FW has zero Heavy-smoke support, and only "
                f"{h_c['heavy_triple_site_days']} same-site, same-day Heavy-smoke triple observations ({h_c['heavy_overlap_dates']} "
                f"overlapping dates) occur nationwide; accordingly, BAM&ndash;FRM is retained strictly as a background reference benchmark. "
                f"Panel B plots the differential Tier-1 excess (T640 &minus; FRM) &minus; (BAM &minus; FRM) with 95% smoke-block CIs "
                f"across progressively stricter common-support filters and exact overlap-weighted matching across {ow['n_shared_cells']} "
                f"shared EPA Region &times; FRM-bin strata ({ow['differential_pp']:+.2f} pp, bootstrap 95% CI "
                f"[{ow['block_bootstrap_ci95_pp'][0]:+.1f}, {ow['block_bootstrap_ci95_pp'][1]:+.1f}]). Inset reports the "
                f"{all_c['triple_site_days']} all-day exact same-rooftop triples ({all_c['triple_sites']} sites), where mean T640 &minus; BAM "
                f"rises monotonically from {tr['hms_0_none']['mean_t640_minus_bam']:+.2f} &mu;g/m<sup>3</sup> (HMS None) to "
                f"{tr['hms_3_heavy']['mean_t640_minus_bam']:+.2f} &mu;g/m<sup>3</sup> (HMS Heavy, <em>n</em> = {tr['hms_3_heavy']['n_site_days']})."
            ),
        ),
        "fig2_est_official_and_oot_tier_replay.png": (
            "Figure 2. Official Retrospective (2021&ndash;2025) and Strictly Out-of-Time Rolling 5-Year EPA Tier-1 Screening Replays and Near-Threshold Asymmetric Crossings.",
            (
                f"Panel A compares paired exceedance differences (percentage points; thick bars: two-way Site &times; Region-Smoke-Episode "
                f"95% CI; thin caps: one-way national smoke-date block 95% CI) for T640_FW&ndash;FRM (burnt sienna) versus background "
                f"BAM&ndash;FRM (teal) across EPA&rsquo;s official 2021&ndash;2025 Tier-1 ({t1_t['difference_pp']:+.2f} pp, "
                f"{t1_t['fem_exceed']} vs. {t1_t['frm_exceed']}; {t1_t['fem_only']}/{t1_t['frm_only']} discordant), Tier-2 lower, "
                f"fixed &gt;35 &mu;g/m<sup>3</sup>, and four strictly out-of-time prospective rolling 5-year reconstructions "
                f"(2018&ndash;2022 &rarr; 2023, 2019&ndash;2023 &rarr; 2024, 2020&ndash;2024 &rarr; 2025: "
                f"{oot_a['difference_pp']:+.2f} to {oot_b2['difference_pp']:+.2f} pp, {oot_a['fem_only']}&ndash;{oot_b2['fem_only']} vs. 0 FRM-only; "
                f"BAM null across all specifications). Panel B scatters normalized daily readings (Instrument / Site-Month Tier-1) for all "
                f"{t1_t['n_site_days']} matched T640_FW&ndash;FRM Heavy-smoke pairs, showing {nb20['fem_only']} of {t1_t['fem_only']} "
                f"T640-only crossings concentrated within the &plusmn;20% near-threshold band (shaded) versus only {t1_t['frm_only']} "
                f"FRM-only crossings."
            ),
        ),
        "fig3_est_smoke_vs_nonsmoke_and_ground_truth.png": (
            "Figure 3. Equal-Concentration Non-Smoke Controls Versus HMS Heavy Smoke and Independent Ground-Level Smoke Confirmation (T640_FW&ndash;FRM, 2023&ndash;2025).",
            (
                f"Panel A compares mean paired daily optical bias (T640_FW &minus; FRM, &mu;g/m<sup>3</sup>) and official Tier-1 exceedance "
                f"differences (bottom tags) between Non-Smoke days (HMS = 0, slate) and HMS Heavy smoke days (HMS = 3, crimson) within "
                f"identical concentration bands defined by independent Other-Site FRM/BAM monitors, collocated FRM, and Bland&ndash;Altman "
                f"midpoints: Heavy smoke amplifies optical bias three- to fivefold across every stratum (all Site-clustered <em>p</em> &lt; 0.001; "
                f"Other-Site &ge;25: {mc_t['other_site_ge25']['nonsmoke']['mean_bias']:+.2f} non-smoke vs. "
                f"{mc_t['other_site_ge25']['heavy_smoke']['mean_bias']:+.2f} &mu;g/m<sup>3</sup> Heavy). Panel B verifies ground-level smoke "
                f"specificity: Tier-1 excess concentrates in surface-impacted plumes (FRM &gt; site-month non-smoke p90: "
                f"{gv_t['heavy_surface_impact_frm_gt_p90']['t1_diff_pp']:+.1f} pp, <em>n</em> = {gv_t['heavy_surface_impact_frm_gt_p90']['n']}; "
                f"Surface OC &ge; 5 &mu;g/m<sup>3</sup>: {gv_t['heavy_oc_ge5']['t1_diff_pp']:+.1f} pp, <em>n</em> = {gv_t['heavy_oc_ge5']['n']}) "
                f"and vanishes on lofted plumes (&le; p90: 0.0 pp, <em>n</em> = {gv_t['heavy_lofted_frm_le_p90']['n']}), while non-smoke elevated "
                f"days split between humid winter inorganic haze ({gv_t['nonsmoke_frm_ge20_winter_djf']['t1_diff_pp']:+.1f} pp) and negative "
                f"warm-season non-smoke bias ({gv_t['nonsmoke_frm_ge20_warm_mjjas']['t1_diff_pp']:+.1f} pp)."
            ),
        ),
        "fig4_est_inference_loro_and_speciation.png": (
            "Figure 4. Multi-Dimensional Event-Level Inference, Leave-One-EPA-Region-Out Stability, and Observational Chemical-Speciation &amp; Hygroscopicity Associations.",
            (
                f"Panel A evaluates the stability of T640_FW&rsquo;s {t1_t['difference_pp']:+.2f} pp official Tier-1 excess across six "
                f"clustering estimators&mdash;1-way Site, Date, National Block, and Region-Smoke-Episode, plus 2-way Cameron&ndash;Gelbach&ndash;Miller "
                f"Site &times; National Block and primary Site &times; Region-Episode ({t1_t['inference']['twoway_site_x_reg_episode']['ci95'][0]:+.2f} to "
                f"{t1_t['inference']['twoway_site_x_reg_episode']['ci95'][1]:+.2f} pp)&mdash;and all {loro['n_regions']} leave-one-EPA-region-out "
                f"re-estimations (range [{loro['min_loro_diff_pp']:+.2f}, {loro['max_loro_diff_pp']:+.2f}] pp, all 95% CIs &gt; 0). "
                f"Panel B plots Site FE + Month FE observational partial associations with daily (FEM &minus; FRM) bias across "
                f"{s1_t['n']:,} T640_FW and {s1_b['n']:,} BAM paired days: T640_FW covaries positively with Organic Carbon "
                f"({s1_t['coefs']['oc']['beta']:+.2f}; additional {s2_t['coefs']['oc_x_hms_h']['beta']:+.2f} under HMS Heavy) and RH "
                f"({s1_t['coefs']['rh_10']['beta']:+.2f} per +10%) and negatively with light-absorbing Elemental Carbon "
                f"({s1_t['coefs']['ec']['beta']:+.2f}), consistent with Mie optical physics (Long et al., 2023), whereas heated-inlet BAM "
                f"is null on OC/EC and negative on semi-volatile NO<sub>3</sub><sup>&minus;</sup> and RH."
            ),
        ),
        "figS1_si_dv_reclassification_and_rooftop_lottery.png": (
            "Figure S1. Screening-Level 2021&ndash;2023 Monitor Design Value Threshold Waterfall (Distinct from CAA &sect; 107(d) Designations) and Same-Rooftop 2023&ndash;2025 Paired Annual DV Sensitivity.",
            (
                f"Panel A traces screening-level county monitor Design-Value threshold cross-overs (&ge; 9.1 &mu;g/m<sup>3</sup>) across "
                f"495 matched regulatory counties in 2021&ndash;2023: swapping pre-alignment raw T640 for aligned T640 alone lowers counts "
                f"from {wf21['raw_2123']['counties']} ({wf21['raw_2123']['pop_millions']:.1f}M) to {wf21['aln_2123']['counties']} "
                f"({wf21['aln_2123']['pop_millions']:.1f}M), a set of {wf21['flip_t640_alone']['counties']} screening-level monitor DV "
                f"reclassifications ({wf21['flip_t640_alone']['pop_millions']:.2f}M residents; explicitly distinct from formal EPA Clean Air Act "
                f"&sect; 107(d) five-factor legal designations). Panel B scatters paired-day 2023&ndash;2025 annual DVs across "
                f"{rt_t['n_sites']} T640_FW&ndash;FRM rooftops (mean bias +{rt_t['mean_dv_bias']:.3f} &mu;g/m<sup>3</sup>, "
                f"{rt_t['fem_na_frm_att']} vs. {rt_t['frm_na_fem_att']} crossing 9.0 &mu;g/m<sup>3</sup>, binomial <em>p</em> = "
                f"{_fmt_p_html(rt_t['binom_p'])}; BAM reference <em>N</em> = {rt_b['n_sites']}: {rt_b['mean_dv_bias']:+.3f} &mu;g/m<sup>3</sup>, "
                f"{rt_b['fem_na_frm_att']} vs. {rt_b['frm_na_fem_att']})."
            ),
        ),
        "figS2_si_oot_reconstruction_and_ee_nulls.png": (
            "Figure S2. Validation of 40 CFR Part 50 Appendix N Threshold Reconstruction Against EPA&rsquo;s 2021&ndash;2025 Table and Archival Exceptional Event Flagging Context with Within-County-Year Null.",
            (
                f"Panel A benchmarks 2021&ndash;2025 Tier-1 thresholds reconstructed from AQS bulk daily/annual archives against EPA&rsquo;s "
                f"official published table (for_posting.csv, 2026-09-14): on zero-event clean sites, combined-site Appendix N Table 1 "
                f"achieves median absolute error {rb['cs_all_no_ann_excl']['zero_flag_clean_median_abs_err']:.2f} &mu;g/m<sup>3</sup> "
                f"(<em>r</em> = {rb['cs_all_no_ann_excl']['zero_flag_clean_corr']:.2f}; OOT-B <em>r</em> = "
                f"{rb['oot_b_cs_excl_hms3']['zero_flag_clean_corr']:.2f}). Panel B displays archival 2018&ndash;2025 county-year "
                f"Exceptional Event flagging event-study coefficients (ref = 2020), showing the anticipatory 2022&ndash;2023 peak prior "
                f"to the Feb 2024 final rule, null 2024&ndash;2025 concurred exclusions, and the within-county-year FE T640 null "
                f"({100 * u2_wcy['coefs']['is_t640_f']['beta']:+.2f} pp, <em>p</em><sub>WCB</sub> = {u2_wcy['wcb']['p_wcb']:.3f}, "
                f"<em>N</em> = {u2_wcy['n']}), confirming no causal claim of instrument-induced EE filings."
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
    s = s.replace(r"^{\circ}", "&deg;")
    s = s.replace(r"^\circ", "&deg;")

    while r"\frac{" in s:
        idx = s.index(r"\frac{")
        num, nxt = _extract_braced(s, idx + len(r"\frac"))
        den, end = _extract_braced(s, nxt) if nxt < len(s) and s[nxt] == "{" else ("", nxt)
        n_clean, d_clean = num.strip(), den.strip()
        if n_clean == "1" and d_clean == "2":
            frac_repl = "&frac12;"
        else:
            n_wrap = f"({n_clean})" if re.search(r"[+\-= ]", n_clean) else n_clean
            d_wrap = f"({d_clean})" if re.search(r"[+\-= ]", d_clean) else d_clean
            frac_repl = (
                f"{n_wrap}/{d_wrap}"
                if (n_wrap == n_clean and d_wrap == d_clean)
                else f"{n_wrap} / {d_wrap}"
            )
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
        (r"\Phi", "&Phi;"),
        (r"\Pi", "&Pi;"),
        (r"\Omega", "&Omega;"),
        (r"\Delta", "&Delta;"),
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
        (r"\omega", "&omega;"),
        (r"\varepsilon", "&epsilon;"),
        (r"\epsilon", "&epsilon;"),
        (r"\tau", "&tau;"),
        (r"\rho", "&rho;"),
        (r"\mu", "&mu;"),
        (r"\sigma", "&sigma;"),
        (r"\lambda", "&lambda;"),
        (r"\circ", "&deg;"),
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


def convert_md_to_html(
    md_text: str,
    figure_blocks: dict[str, tuple[str, str]],
    running_header: str,
    doc_title: str,
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

            def split_md_row(row_s: str) -> list[str]:
                tmp = row_s.strip("|").replace(r"\|", "\x00PIPE\x00")
                return [c.replace("\x00PIPE\x00", r"\|").strip() for c in tmp.split("|")]

            headers = split_md_row(tbl_lines[0])
            aligns = split_md_row(tbl_lines[1])
            if len(headers) != len(aligns):
                raise ValueError(f"Markdown table column mismatch: {headers}")
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

    css = f"""
    @page {{
      size: letter;
      margin: 0.65in 0.65in 0.72in 0.65in;
      @top-right {{
        content: "{running_header}";
        font-family: Georgia, "Times New Roman", serif;
        font-size: 7.2pt;
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
      font-size: 13.4pt;
      line-height: 1.24;
      margin: 0 0 8pt 0;
      color: #0b2545;
      border-bottom: 1.5pt solid #0b2545;
      padding-bottom: 6pt;
    }}
    h2 {{
      font-size: 10.8pt;
      color: #0b2545;
      margin: 11pt 0 5pt 0;
      border-bottom: 0.6pt solid #cbd5e1;
      padding-bottom: 2pt;
      page-break-after: avoid;
    }}
    h3 {{
      font-size: 9.6pt;
      color: #1e3a5f;
      margin: 8.5pt 0 4pt 0;
      page-break-after: avoid;
    }}
    p {{ margin: 0 0 5.3pt 0; text-align: justify; }}
    p.table-caption {{
      font-size: 8.3pt;
      margin: 7pt 0 3pt 0;
      color: #0b2545;
      text-align: left;
      break-inside: avoid;
      page-break-inside: avoid;
      break-after: avoid;
      page-break-after: avoid;
    }}
    p.table-notes {{
      font-size: 7.3pt;
      color: #475569;
      margin: 2pt 0 8pt 0;
      text-align: left;
    }}
    ul, ol {{ margin: 3pt 0 6pt 16pt; padding: 0; }}
    li {{ margin: 0 0 2.6pt 0; text-align: justify; }}
    ol.refs-list li {{ text-align: left; font-size: 7.5pt; line-height: 1.22; margin: 0 0 1.8pt 0; break-inside: avoid; page-break-inside: avoid; }}
    code {{
      font-family: Consolas, "Courier New", monospace;
      font-size: 7.1pt;
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
      font-size: 9.3pt;
      text-align: center;
      margin: 6.2pt 0;
      padding: 5.5pt 10pt;
      background: #f8fafc;
      border-left: 2pt solid #0b2545;
      break-inside: avoid;
      page-break-inside: avoid;
    }}
    .table-wrap {{ margin: 4pt 0 4pt 0; page-break-inside: avoid; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 6.6pt;
      line-height: 1.22;
      border-top: 1.3pt solid #0f172a;
      border-bottom: 1.3pt solid #0f172a;
    }}
    thead tr {{ border-bottom: 0.8pt solid #334155; background: #f8fafc; }}
    th, td {{ padding: 2.2pt 2.8pt; vertical-align: top; }}
    td .math, th .math {{ white-space: nowrap; }}
    td code {{ white-space: nowrap; font-size: 6.3pt; }}
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
      line-height: 1.29;
      color: #334155;
      text-align: left;
    }}
    """
    return (
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8' />"
        f"<title>{html.escape(doc_title)}</title>"
        f"<style>{css}</style></head><body>{''.join(body)}</body></html>"
    )


def verify_pdf_zero_leaks(pdf_path: Path) -> tuple[int, list[str]]:
    reader = PdfReader(str(pdf_path))
    full_txt = "\n".join((p.extract_text() or "") for p in reader.pages)
    bad_patterns = [
        r"\\[A-Za-z]+",
        r"\\\$",
        r"\\_",
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
        r"fig[1-5S][a-z0-9_]*\.png",
        r"<!--",
        r"TOK\d+",
        r"&[a-z]+;",
        r"&#\d+;",
        r"</?(?:sub|sup|em|strong|span|div|i|b)>",
        r"\bNaN\b",
        r"\bInf\b",
        r"Target Venues|Track A|Track B",
    ]
    leaks = []
    for pat in bad_patterns:
        m = re.search(pat, full_txt)
        if m:
            leaks.append(f"{pat} (matched: {m.group(0)!r})")
    return len(reader.pages), leaks


def compile_one_pdf(
    md_path: Path,
    pdf_path: Path,
    figure_blocks: dict[str, tuple[str, str]],
    running_header: str,
    doc_title: str,
    fallback_pdf: Path | None = None,
) -> tuple[Path, int, str]:
    md_text = md_path.read_text(encoding="utf-8")
    html_doc = convert_md_to_html(md_text, figure_blocks, running_header, doc_title)

    with tempfile.TemporaryDirectory(prefix="j6_edge_pdf_") as tmpdir:
        tmp_path = Path(tmpdir)
        html_file = tmp_path / (md_path.stem + ".html")
        user_data = tmp_path / "edge_profile"
        html_file.write_bytes(html_doc.encode("utf-8"))

        target_pdf = pdf_path
        try:
            # Test writability before invoking Edge
            if target_pdf.exists():
                with target_pdf.open("ab"):
                    pass
        except PermissionError:
            if fallback_pdf is not None:
                target_pdf = fallback_pdf
            else:
                raise

        cmd = [
            str(EDGE_EXE),
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--user-data-dir={user_data}",
            f"--print-to-pdf={target_pdf}",
            html_file.as_uri(),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
        if res.returncode != 0 or not target_pdf.exists() or target_pdf.stat().st_size < 30_000:
            raise RuntimeError(f"Edge PDF compile failed for {md_path.name}: rc={res.returncode} {res.stderr}")

    n_pages, leaks = verify_pdf_zero_leaks(target_pdf)
    if leaks:
        raise RuntimeError(f"Leaked tokens found in {target_pdf.name}: {leaks}")
    sha = hashlib.sha256(target_pdf.read_bytes()).hexdigest()
    return target_pdf, n_pages, sha


def main() -> int:
    if not EDGE_EXE.exists():
        print(f"[ERROR] Microsoft Edge not found at {EDGE_EXE}", file=sys.stderr)
        return 1

    figure_blocks = build_dynamic_figure_blocks()
    out_main, p_main, sha_main = compile_one_pdf(
        MD_MAIN,
        PDF_MAIN,
        figure_blocks,
        running_header="Residual Optical PM2.5 Bias and U.S. Exceptional-Event Tiering Thresholds",
        doc_title="Residual Optical PM2.5 Bias During Wildfire Smoke and Sensitivity of U.S. Exceptional-Event Tiering Thresholds",
        fallback_pdf=PDF_MAIN_FALLBACK,
    )
    print(
        f"[DONE STEP 08] Compiled {out_main.name} ({out_main.stat().st_size:,} bytes, "
        f"{p_main} pages, 0 leaked tokens, SHA-256: {sha_main})",
        flush=True,
    )

    if MD_SI.exists():
        out_si, p_si, sha_si = compile_one_pdf(
            MD_SI,
            PDF_SI,
            figure_blocks,
            running_header="Supporting Information — Residual Optical PM2.5 Bias and Exceptional-Event Tiering",
            doc_title="Supporting Information: Residual Optical PM2.5 Bias During Wildfire Smoke",
        )
        print(
            f"[DONE STEP 08] Compiled {out_si.name} ({out_si.stat().st_size:,} bytes, "
            f"{p_si} pages, 0 leaked tokens, SHA-256: {sha_si})",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
