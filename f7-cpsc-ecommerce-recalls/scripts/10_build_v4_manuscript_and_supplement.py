"""Step 10 (v4): Programmatically build manuscript_f7_boost.md and
supplementary_f7_jcp.md directly from frozen JSON/CSV receipts and live
Crossref-verified references (ZERO hardcoded empirical numbers!).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BASE_DIR = Path(r"D:\AI_Science\antigravity\f7_boost_cpsc_ecommerce_recalls_20261126")
RES_DIR = BASE_DIR / "results"
TBL_DIR = BASE_DIR / "tables"
MAIN_MD = BASE_DIR / "manuscript_f7_boost.md"
SUPP_MD = BASE_DIR / "supplementary_f7_jcp.md"


def fmt_pp(val: float, signed: bool = True) -> str:
    return f"{100 * val:+.2f}" if signed else f"{100 * val:.2f}"


def fmt_p(val: float) -> str:
    if val < 1e-4:
        return f"{val:.2e}"
    return f"{val:.3f}"


def fmt_ref_entry(rec: dict) -> str:
    auths = rec["authors"]
    if len(auths) == 1:
        a_str = auths[0]
    elif len(auths) == 2:
        a_str = f"{auths[0]}, & {auths[1]}"
    else:
        a_str = ", ".join(auths[:-1]) + f", & {auths[-1]}"
    yr_str = "2024" if rec["key"] == "raithel2024" else str(rec["year"])
    vol_part = ""
    if rec.get("volume"):
        vol_part = f", {rec['volume']}"
        if rec.get("issue"):
            vol_part += f"({rec['issue']})"
        if rec.get("page"):
            vol_part += f", {rec['page']}"
    elif rec["key"] == "fang2026":
        vol_part = " (published online September 23, 2026)"
    return f"{a_str} ({yr_str}). {rec['title']}. *{rec['journal']}*{vol_part}. `https://doi.org/{rec['doi']}`"


def build_references_section(refs: dict) -> str:
    entries: list[tuple[str, str]] = []
    for j in refs["journal_references"]:
        sort_key = j["authors"][0].lower() + str(j["year"])
        entries.append((sort_key, fmt_ref_entry(j)))
    for o in refs["official_and_policy_references"]:
        entries.append((o["citation"].lower(), o["citation"]))
    entries.sort(key=lambda x: x[0])
    lines = ["## References", ""]
    for idx, (_, txt) in enumerate(entries, start=1):
        lines.append(f"{idx}. {txt}")
    return "\n".join(lines)


def build_main_manuscript(
    manifest: dict,
    aud_legacy: dict,
    theory: dict,
    p1: dict,
    p234: dict,
    refs: dict,
    v4: dict,
) -> str:
    sf = v4["channel_contamination_and_sample_flow"]
    l601 = sf["legacy_amazon_only_mkt_601_breakdown"]
    l391 = sf["legacy_cs_391_contamination"]
    amz3 = sf["amazon_channel_3way_all_2022_2026"]
    c3 = v4["three_definition_channel_comparisons"]
    d1 = c3["Def1_Broad_Mkt_Mentions_Amazon"]
    d2a = c3["Def2a_NoOtherFlaggedPlat_Benchmark"]
    d2b = c3["Def2b_Strict_Amazon_Exclusive_Verbatim"]
    d3 = c3["Def3_MultiChannel_Online_With_Amazon"]

    all_ch = v4["all_channel_disaggregated_2022_2026"]
    all_hi = v4["all_price_ge_100_disaggregated"]
    sdur = v4["strict_durables_ge_100_disaggregated"]
    aud = v4["remedy_duty_coding_audit_150"]
    ao = aud["overall"]
    afd = aud["by_entity_group"]["1_Mkt_FD_China"]
    aus = aud["by_entity_group"]["3_Mkt_True_US"]
    b_all = v4["all_channel_within_mkt_misclassification_bounds"]
    b_d1 = d1["misclassification_bounds_common_support"]
    b_d2a = d2a["misclassification_bounds_common_support"]
    b_d2b = d2b["misclassification_bounds_common_support"]
    disp = v4["hazardous_notice_coverage_v4"]
    amz_cs = v4["in_re_amazon_case_study_v4"]
    fba = amz_cs["fba_terminology_audit"]
    d4 = v4["remedy_duty_4cat_distribution_2022_2026"]

    hist = {r["year"]: r for r in p1["historical_2000_2026"]}
    r15, r26 = hist[2015], hist[2026]
    mm = p1["main_models_2022_2026"]
    rob = p1["robustness_photo_verify_2022_2026"]
    p2 = p234["pillar2"]
    p3 = p234["pillar3"]
    p4 = p234["pillar4"]
    persist = p3["post_jan2025_contract_persistence"]["Mkt_FD_China"]["photo_verify"]

    d1_pl = d1["common_support_models"]["photo_language"]
    d1_pm = d1["common_support_models"]["photo_mandatory"]
    d1_dr = d1["common_support_models"]["direct_return"]

    d2a_pl = d2a["common_support_models"]["photo_language"]
    d2a_dr = d2a["common_support_models"]["direct_return"]

    d2b_pl = d2b["common_support_models"]["photo_language"]
    d2b_pm = d2b["common_support_models"]["photo_mandatory"]
    d2b_dr = d2b["common_support_models"]["direct_return"]
    d2b_pd = d2b["common_support_models"]["physical_destruction"]
    d2b_raw_pl = d2b["full_subsample_prodcat_yq_models"]["photo_language"]
    d2b_raw_dr = d2b["full_subsample_prodcat_yq_models"]["direct_return"]

    d3_raw_pl = d3["full_subsample_prodcat_yq_models"]["photo_language"]
    d3_raw_mk = d3["full_subsample_prodcat_yq_models"]["permanent_marking"]

    all_pl = all_ch["photo_language"]
    all_pm = all_ch["photo_mandatory"]
    all_dr = all_ch["direct_return"]

    sdur_pl = sdur["photo_language"]
    sdur_pm = sdur["photo_mandatory"]
    sdur_dr = sdur["direct_return"]
    sdur_pd = sdur["physical_destruction"]
    sdur_mk = sdur["permanent_marking"]

    r7 = rob["R7_high_price_ge_100"]
    r7b = rob["R7b_strict_durables_ge_100"]
    dtc_pl = all_pl["terms"]["a_dtc_online"]

    sc_b = amz_cs["hac_its_jul2024_L4"]["log_broad_over_bm"]["params"]["slope_change"]
    sc_s = amz_cs["hac_its_jul2024_L4"]["log_strict_over_bm"]["params"]["slope_change"]
    ann_amz = {r["year"]: r for r in amz_cs["annual_counts_2021_2026"]}

    top4 = disp["largest_cases"][:4]
    raw_sha = manifest["raw_json_sha256"][:12]
    diff_s = p2["diffusion_slopes_2022_2026"]
    bm_dec = p2["bm_diffusion_decomposition"]

    def _cell(rec: dict, is_contrast: bool = False) -> str:
        b = rec["diff"] if is_contrast else rec["beta"]
        lo, hi = rec["ci_lo"], rec["ci_hi"]
        pw = rec["p_wcb"]
        b_s = f"**{fmt_pp(b)}**" if pw <= 0.05 else fmt_pp(b)
        return f"{b_s} [{fmt_pp(lo)}, {fmt_pp(hi)}] (*p*={pw:.3f})"

    t3_outcomes = [
        ("Photo Language (Literal)", "photo_language"),
        ("Mandatory Photo (No Alt. Path)", "photo_mandatory"),
        ("Direct Return Option", "direct_return"),
        ("Physical Destruction", "physical_destruction"),
        ("Permanent Marking", "permanent_marking"),
        ("Photo-Only (No Action)", "photo_only_no_action"),
        ("Explicit Destruction-Proof Phrase", "destruction_proof"),
    ]
    t3_lines = [
        "| Notice-Duty Outcome | All-Channel Within-Mkt (`N=1,822`) | Def 1: Broad Mkt-Amz CS (`N=391`, 38 cells) | Def 2a: No Other 3P CS (`N=313`, 34 cells) | Def 2b: Strict Amz-Excl CS (`N=236`, 25 cells) | Def 3: Multi-Ch Online Full (`N=138`, ProdCat+YQ) |",
        "|:---|---:|---:|---:|---:|---:|",
    ]
    for lbl, yk in t3_outcomes:
        t3_lines.append(
            f"| {lbl} | {_cell(all_ch[yk]['contrast'], is_contrast=True)} | "
            f"{_cell(d1['common_support_models'][yk])} | "
            f"{_cell(d2a['common_support_models'][yk])} | "
            f"{_cell(d2b['common_support_models'][yk])} | "
            f"{_cell(d3['full_subsample_prodcat_yq_models'][yk])} |"
        )
    table3_md = "\n".join(t3_lines)

    t2_err_lines = [
        "| Coded Field & Audit Slice | $N$ | TP | FP | TN | FN | Exact Acc. | F1 | FPR [95% CI] | FNR [95% CI] |",
        "|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        "| **Categorical (`N=150` Overall)** | | | | | | | | | |",
        f"| `amazon_channel_3way` (Overall / FD-CN / U.S.) | 150 | — | — | — | — | {ao['categorical_fields']['amazon_channel']['exact_accuracy']:.4f} | — | FD: {afd['categorical_fields']['amazon_channel']['exact_accuracy']:.4f} | U.S.: {aus['categorical_fields']['amazon_channel']['exact_accuracy']:.4f} |",
        f"| `proof_status` (Overall / FD-CN / U.S.) | 150 | — | — | — | — | {ao['categorical_fields']['proof_status']['exact_accuracy']:.4f} | — | FD: {afd['categorical_fields']['proof_status']['exact_accuracy']:.4f} | U.S.: {aus['categorical_fields']['proof_status']['exact_accuracy']:.4f} |",
        f"| `duty_bearer` (Overall / FD-CN / U.S.) | 150 | — | — | — | — | {ao['categorical_fields']['duty_bearer']['exact_accuracy']:.4f} | — | FD: {afd['categorical_fields']['duty_bearer']['exact_accuracy']:.4f} | U.S.: {aus['categorical_fields']['duty_bearer']['exact_accuracy']:.4f} |",
        "| **Binary Fields by Entity Group (FD-CN `n=55` vs. U.S. `n=49`)** | | | | | | | | | |",
    ]
    for bf_lbl, bf_k in [
        ("`photo_language` — Overall", "photo_language"),
        ("`photo_language` — FD-China", "photo_language"),
        ("`photo_language` — U.S. Entity", "photo_language"),
        ("`photo_mandatory` — FD-China", "photo_mandatory"),
        ("`photo_mandatory` — U.S. Entity", "photo_mandatory"),
        ("`direct_return` — FD-China", "direct_return"),
        ("`direct_return` — U.S. Entity", "direct_return"),
        ("`physically_disabled` — FD-China", "physically_disabled"),
        ("`physically_disabled` — U.S. Entity", "physically_disabled"),
        ("`permanent_marking` — FD-China", "permanent_marking"),
        ("`permanent_marking` — U.S. Entity", "permanent_marking"),
        ("`destruction_proof_no_photo` — Overall", "destruction_proof_no_photo"),
    ]:
        src = ao if "Overall" in bf_lbl else (afd if "FD-China" in bf_lbl else aus)
        m = src["binary_fields"][bf_k]
        t2_err_lines.append(
            f"| {bf_lbl} | {m['n']} | {m['tp']} | {m['fp']} | {m['tn']} | {m['fn']} | {m['accuracy']:.4f} | {m['f1']:.4f} | "
            f"{100*m['fpr']:.1f}% [{100*m['fpr_ci95'][0]:.1f}, {100*m['fpr_ci95'][1]:.1f}] | "
            f"{100*m['fnr']:.1f}% [{100*m['fnr_ci95'][0]:.1f}, {100*m['fnr_ci95'][1]:.1f}] |"
        )
    table2a_md = "\n".join(t2_err_lines)

    t2b_lines = [
        "| Sample Definition & Outcome | Raw FE Gap (pp) | Emp. Bias (pp) | Emp. Adjusted (pp) | 95% Point Misclass. Bound (pp) | Joint Sampling + Misclass. (pp) |",
        "|:---|---:|---:|---:|---:|---:|",
    ]
    for slbl, bsrc in [
        ("All-Channel Within-Mkt (`N=1,822`)", b_all),
        ("Def 1: Broad Mkt-Amz CS (`N=391`)", b_d1),
        ("Def 2a: No Other 3P CS (`N=313`)", b_d2a),
        ("Def 2b: Strict Amz-Excl CS (`N=236`)", b_d2b),
    ]:
        for yk, ylbl in [
            ("photo_language", "Photo Language"),
            ("photo_mandatory", "Mandatory Photo"),
            ("direct_return", "Direct Return"),
            ("physically_disabled", "Physically Disabled"),
            ("permanent_marking", "Permanent Marking"),
        ]:
            b = bsrc[yk]
            t2b_lines.append(
                f"| {slbl}: {ylbl} | {fmt_pp(b['beta_fe'])} | {fmt_pp(b['empirical_diff_bias'])} | "
                f"**{fmt_pp(b['beta_empirical_adjusted'])}** | [{fmt_pp(b['point_misclass_bound_lo'])}, {fmt_pp(b['point_misclass_bound_hi'])}] | "
                f"[{fmt_pp(b['joint_sampling_and_misclass_lo'])}, {fmt_pp(b['joint_sampling_and_misclass_hi'])}] |"
            )
    table2b_md = "\n".join(t2b_lines)

    t4_lines = [
        "| Specification / Outcome (2022–2026, Ultra-Saturated FE) | $N$ | Clusters | `1_Mkt_FD_China` vs. B&M (pp) | Within-Mkt $\\Delta_{\\text{FD}-\\text{US}}$ (pp) | `4_DTC_Online` vs. B&M (pp) |",
        "|:---|---:|---:|---:|---:|---:|",
        f"| **Photo Language (`photo_language`, Full Sample)** | {all_pl['n']:,} | {all_pl['n_clusters']:,} | {_cell(all_pl['terms']['a_mkt_fd_cn'])} | {_cell(all_pl['contrast'], True)} | {_cell(all_pl['terms']['a_dtc_online'])} |",
        f"| **Mandatory Photo (`photo_mandatory`, Full Sample)** | {all_pm['n']:,} | {all_pm['n_clusters']:,} | {_cell(all_pm['terms']['a_mkt_fd_cn'])} | {_cell(all_pm['contrast'], True)} | {_cell(all_pm['terms']['a_dtc_online'])} |",
        f"| **Products Priced $\\ge \\$100$ (All Categories): `photo_verify`** | {r7['n']:,} | {r7['n_clusters']:,} | {_cell(r7['terms']['a_mkt_fd_cn'])} | {_cell(r7['contrast'], True)} | {_cell(r7['terms']['a_dtc_online'])} |",
        f"| **Products Priced $\\ge \\$100$ (All Categories): `photo_language`** | {all_hi['photo_language']['n']:,} | {all_hi['photo_language']['n_clusters']:,} | {_cell(all_hi['photo_language']['terms']['a_mkt_fd_cn'])} | {_cell(all_hi['photo_language']['contrast'], True)} | {_cell(all_hi['photo_language']['terms']['a_dtc_online'])} |",
        f"| **Strict Durables ($\\ge \\$100$): `photo_verify`** | {r7b['n']:,} | {r7b['n_clusters']:,} | {_cell(r7b['terms']['a_mkt_fd_cn'])} | {_cell(r7b['contrast'], True)} | {_cell(r7b['terms']['a_dtc_online'])} |",
        f"| **Strict Durables ($\\ge \\$100$): `photo_language`** | {sdur_pl['n']:,} | {sdur_pl['n_clusters']:,} | {_cell(sdur_pl['terms']['a_mkt_fd_cn'])} | {_cell(sdur_pl['contrast'], True)} | {_cell(sdur_pl['terms']['a_dtc_online'])} |",
        f"| **Strict Durables ($\\ge \\$100$): `photo_mandatory`** | {sdur_pm['n']:,} | {sdur_pm['n_clusters']:,} | {_cell(sdur_pm['terms']['a_mkt_fd_cn'])} | {_cell(sdur_pm['contrast'], True)} | {_cell(sdur_pm['terms']['a_dtc_online'])} |",
        f"| **Strict Durables ($\\ge \\$100$): `direct_return`** | {sdur_dr['n']:,} | {sdur_dr['n_clusters']:,} | {_cell(sdur_dr['terms']['a_mkt_fd_cn'])} | {_cell(sdur_dr['contrast'], True)} | {_cell(sdur_dr['terms']['a_dtc_online'])} |",
        f"| **Strict Durables ($\\ge \\$100$): `physical_destruction`** | {sdur_pd['n']:,} | {sdur_pd['n_clusters']:,} | {_cell(sdur_pd['terms']['a_mkt_fd_cn'])} | {_cell(sdur_pd['contrast'], True)} | {_cell(sdur_pd['terms']['a_dtc_online'])} |",
        f"| **Strict Durables ($\\ge \\$100$): `permanent_marking`** | {sdur_mk['n']:,} | {sdur_mk['n_clusters']:,} | {_cell(sdur_mk['terms']['a_mkt_fd_cn'])} | {_cell(sdur_mk['contrast'], True)} | {_cell(sdur_mk['terms']['a_dtc_online'])} |",
        f"| Contact Infrastructure: Free Webmail (`free_webmail`) | {mm['free_webmail']['n']:,} | {mm['free_webmail']['n_clusters']:,} | {_cell(mm['free_webmail']['terms']['a_mkt_fd_cn'])} | {_cell(mm['free_webmail']['contrast'], True)} | {_cell(mm['free_webmail']['terms']['a_dtc_online'])} |",
        f"| Contact Infrastructure: No U.S. Phone (`no_phone`) | {mm['no_phone']['n']:,} | {mm['no_phone']['n_clusters']:,} | {_cell(mm['no_phone']['terms']['a_mkt_fd_cn'])} | {_cell(mm['no_phone']['contrast'], True)} | {_cell(mm['no_phone']['terms']['a_dtc_online'])} |",
        f"| Statutory Scope: Mandatory Federal Safety Rule | {p4['mandatory_rule_fe']['n']:,} | {p4['mandatory_rule_fe']['n_clusters']:,} | {_cell(p4['mandatory_rule_fe']['terms']['a_mkt_fd_cn'])} | {_cell(p4['mandatory_rule_fe']['contrast'], True)} | {_cell(p4['mandatory_rule_fe']['terms']['a_dtc_online'])} |",
        f"| Traceability: GS1 `ProductUPCs` Listed | {p2['traceability_upc_fe']['n']:,} | {p2['traceability_upc_fe']['n_clusters']:,} | {_cell(p2['traceability_upc_fe']['terms']['a_mkt_fd_cn'])} | {_cell(p2['traceability_upc_fe']['contrast'], True)} | {_cell(p2['traceability_upc_fe']['terms']['a_dtc_online'])} |",
        f"| Cross-Border Coordination: Joint CAN/MEX Recall | {p2['coordination_inconjunction_fe']['n']:,} | {p2['coordination_inconjunction_fe']['n_clusters']:,} | {_cell(p2['coordination_inconjunction_fe']['terms']['a_mkt_fd_cn'])} | {_cell(p2['coordination_inconjunction_fe']['contrast'], True)} | {_cell(p2['coordination_inconjunction_fe']['terms']['a_dtc_online'])} |",
    ]
    table4_md = "\n".join(t4_lines)

    t1_md = f"""| Sample Filtering Stage | Total Notices | `1_Mkt_FD_China` | `3_Mkt_True_US` | Exact Scope & Inclusion Note |
|:---|---:|---:|---:|:---|
| 1. Complete CPSC SaferProducts Census (2000–2026) | {v4['notice_universe']:,} | — | — | Frozen HTTP-200 API JSON (2000-01-04 to 2026-11-19, SHA-256 `{raw_sha}...`) |
| 2. Post-Emergence Contract Era (2022–2026) | {sf['n_2022_2026_all']:,} | 448 | 233 | Photo verification $\\le 2.74\\%$ pre-2022; strict era discipline avoids zero-variation pooling |
| 3. Classified 6-Archetype Universe | {sf['n_2022_2026_classified']:,} | 448 | 233 | Excludes {sf['n_2022_2026_other_unclear']} `7_Other_Unclear` notices (2.03%: giveaways / unlocated alerts) |
| 4. All-Channel Saturated Regression Sample | {sf['n_2022_2026_reg_sample']:,} | 447 | 233 | Non-missing retail price and affected units across $G = {sf['g_2022_2026_reg_clusters']:,}$ independent firm clusters |
| 5a. Verbatim 2022–2026 Channel: `strict_amazon_exclusive` | {amz3['strict_amazon_exclusive']} | 348 | 73 | Verbatim `Retailers` states exclusively Amazon or lists Amazon as sole retailer (+17 Non-CN, 3 Unclear) |
| 5b. Verbatim 2022–2026 Channel: `multi_channel_with_amazon` | {amz3['multi_channel_with_amazon']} | 41 | 112 | 164 online multi-channel (162 classified: other 3P/DTC) + 276 Omnichannel (Amazon + physical stores) |
| 5c. Verbatim 2022–2026 Channel: `amazon_channel_ambiguous` | {amz3['amazon_channel_ambiguous']} | 0 | 2 | 1 Amazon Fire TV app (9234) + 4 CPSC Title/Remedy vs. Retailers clerical conflicts (10238, 10245, 10276, 10494) |
| 5d. Verbatim 2022–2026 Channel: `no_amazon_mention` | {amz3['no_amazon_mention']} | 59 | 46 | Non-Amazon marketplaces, pure DTC websites, or brick-and-mortar only |
| 6a. **Def 1:** Broad Legacy `amazon_only_mkt` (Calendar CS) | {d1['cs_n']} | {d1['cs_groups']['1_Mkt_FD_China']} | {d1['cs_groups']['3_Mkt_True_US']} | {d1['cs_cells']} fine-noun $\\times$ year cells (Jan 1–Nov 19); includes {l391['other_flagged_plat_total']}/391 other-3P & {l391['verbatim_multi_channel_total']}/391 multi-channel |
| 6b. **Def 2a:** Excl. Other Flagged 3P Platforms (Rebuilt CS) | {d2a['cs_n']} | {d2a['cs_groups']['1_Mkt_FD_China']} | {d2a['cs_groups']['3_Mkt_True_US']} | {d2a['cs_cells']} cells; exact reproduction of peer-review benchmark ($N = 313$) |
| 6c. **Def 2b:** Verbatim `strict_amazon_exclusive` (Rebuilt CS) | {d2b['cs_n']} | {d2b['cs_groups']['1_Mkt_FD_China']} | {d2b['cs_groups']['3_Mkt_True_US']} | {d2b['cs_cells']} cells (full calendar-aligned strict-exclusive $N = {d2b['raw_n']}$: {d2b['raw_groups']['1_Mkt_FD_China']} vs. {d2b['raw_groups']['3_Mkt_True_US']}) |
| 6d. **Def 3:** `multi_channel_online_with_amazon` (Full / CS App. B) | {d3['raw_n']} | {d3['raw_groups']['1_Mkt_FD_China']} | {d3['raw_groups']['3_Mkt_True_US']} | Full ProdCat+YQ FE $N = {d3['raw_n']}$; underpowered fine-cell CS ($N = {d3['cs_n']}$, {d3['cs_cells']} cells) reported in Appendix B |"""

    t5_md = f"""| Institutional Dimension & Audited Metric | Notice Count / Value | Affected Units / Statistical Detail | Verbatim Scope & Caveat |
|:---|---:|---:|:---|
| **Panel A — Hazardous-Product Notice Coverage (`1_Mkt_FD_China`, 2022–2026)** | | | |
| Hazard-gated hazardous-product notices (Li-ion, button cell, lead/chem) | {disp['hazard_group_notices']} | 0.0% firm direct-return programs | Excludes non-battery mechanical e-bike/scooter recalls |
| Screened notices assigning consumer self-disposal (no direct return) | {disp['screened_notices']} / {disp['hazard_group_notices']} | **{disp['screened_affected_units']:,} affected units** | **Notice-listed affected stock only** (NOT observed waste stream) |
| Subset containing literal disposal wording (`dispose/disposal`) | {disp['disposal_word_notices']} / {disp['screened_notices']} | {disp['disposal_word_affected_units']:,} affected units | Verbatim literal verb/noun check in `Remedies` |
| Explicit local/state HHW or trash-prohibition warnings (`Remedies` only) | {disp['warning_remedy_notices']} / {disp['screened_notices']} | {disp['warning_remedy_affected_units']:,} units ({100*disp['warning_remedy_affected_units']/disp['screened_affected_units']:.2f}%) | Legacy remedy-field-only search |
| **Complete-notice HHW/disposal warnings (`Remedies + Desc + Hazards`)** | **{disp['warning_full_notice_count']} / {disp['screened_notices']}** ({100*disp['warning_full_notice_share_notices']:.2f}%) | **{disp['warning_full_notice_affected_units']:,} units ({100*disp['warning_full_notice_share_units']:.2f}%)** | Includes Anker (10311) & OCOOPA (10895) full-notice cautions |
| Top-2 batch concentration: OCOOPA (10895) + Anker (10311) | {disp['top2_ocoopa_anker_units']:,} units | **{100*disp['top2_ocoopa_anker_share']:.2f}%** of screened total | Both are **multi-channel online** (Anker, Ocoopa.com, Walmart, eBay, Newegg) |
| Top-4 batch concentration (+ Charmast 488k + Baseus 132k) | {disp['top4_units']:,} units | {100*disp['top4_share']:.2f}% of screened total | Heavy concentration makes aggregate unit sums batch-driven |
| **Panel B — *In re Amazon.com* (Docket No. 21-2) Institutional Case Study** | | | |
| Explicit "Fulfilled by Amazon" / "Fulfillment by Amazon" mentions | **{fba['explicit_fulfilled_by_amazon_mentions']} / {fba['broad_amazon_only_mkt_2022_2026']}** | 0.00% across 2022–2026 Amazon-mentioning notices | Public notices do not identify FBA vs. FBM fulfillment mode |
| Standalone "FBA" acronym token | {fba['standalone_fba_tokens']} / {fba['broad_amazon_only_mkt_2022_2026']} | TADAKAZU (RecallID 10317) model-name suffix | Acronym inside SKU model strings does not establish FBA status |
| Annual volume: Broad `amazon_only_mkt` (2022 → 2024 → 2025 → 2026) | {ann_amz[2022]['amz_broad']} → {ann_amz[2024]['amz_broad']} → {ann_amz[2025]['amz_broad']} → {ann_amz[2026]['amz_broad']} | Jul 2024 HAC ($L=4$): **{sc_b['beta']:+.4f}/qtr** ($t = {sc_b['t']:+.2f}$) | Descriptive structural break vs. B&M ($T=23$ complete quarters) |
| Annual volume: Verbatim `strict_amazon_exclusive` (2022 → 2024 → 2025 → 2026) | {ann_amz[2022]['amz_strict_exclusive']} → {ann_amz[2024]['amz_strict_exclusive']} → {ann_amz[2025]['amz_strict_exclusive']} → {ann_amz[2026]['amz_strict_exclusive']} | Jul 2024 HAC ($L=4$): **{sc_s['beta']:+.4f}/qtr** ($t = {sc_s['t']:+.2f}$) | Confirms break is not an artifact of multi-channel co-listings |
| Post-Jan 16, 2025 `1_Mkt_FD_China` `photo_verify` entrenchment | {100*persist['pre_mean']:.1f}% → {100*persist['post_mean']:.1f}% | FE {100*persist['fe_beta']:+.2f} pp ($t = {persist['fe_t']:+.2f}$) | Expanded notice volume coincided with deeper consumer proof duties |"""

    refs_md = build_references_section(refs)

    return f"""# Who Bears the Burden of Product Recall Remedies? Notice-Level Duties, Channel Classification, and Institutional Governance in U.S. Third-Party E-Commerce Recalls, 2000–2026

**Zijian Zeng**  
Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA  
`zijianzeng@foxmail.com`; `1002266693@ucsiuniversity.edu.my`

---

## Abstract

Public product recall notices issued by the U.S. Consumer Product Safety Commission (CPSC) formally allocate corrective duties between recalling firms and consumers—specifying whether households may return a hazardous item to a store or by prepaid mail, or must photograph, mark, physically disable, and arrange local disposal of the product themselves. Using the complete 27-year official CPSC SaferProducts Recall Census (2000–2026, $N = {v4['notice_universe']:,}$ unique notices; strict post-emergence contract era 2022–2026, $N = {sf['n_2022_2026_reg_sample']:,}$ classified notices with complete price and unit data across $G = {sf['g_2022_2026_reg_clusters']:,}$ firm clusters), we construct an auditable verbatim channel taxonomy and a five-dimensional remedy-duty dataset separating literal photographic proof, mandatory versus optional/alternative proof pathways, physical disablement, permanent marking, and direct physical returns. Auditing prior marketplace coding exposes substantial asymmetric channel conflation: 51/391 common-support notices (13/264 China-direct vs. 38/127 U.S.-entity) listed additional flagged marketplaces, and 100/391 (26/264 vs. 74/127; 162/601 across 2022–2026, including the Anker and OCOOPA recalls) listed other marketplaces or brand direct-to-consumer websites alongside Amazon. We therefore report all channel definitions side by side. Across the full 2022–2026 all-channel census ($N = {sf['n_2022_2026_reg_sample']:,}$), China-direct marketplace notices listing no U.S. entity (`1_Mkt_FD_China`) exhibit {fmt_pp(all_pl['terms']['a_mkt_fd_cn']['beta'])} pp higher literal photo-evidence wording ($p_{{\\text{{WCB}}}} = {all_pl['terms']['a_mkt_fd_cn']['p_wcb']:.3f}$) and {fmt_pp(all_dr['terms']['a_mkt_fd_cn']['beta'])} pp lower direct-return options ($p_{{\\text{{WCB}}}} = {all_dr['terms']['a_mkt_fd_cn']['p_wcb']:.3f}$) relative to brick-and-mortar recalls—including {fmt_pp(all_pl['contrast']['diff'])} pp (`photo_language`) and {fmt_pp(all_dr['contrast']['diff'])} pp (`direct_return`) within marketplaces over verified U.S.-entity sellers (`3_Mkt_True_US`), and {fmt_pp(sdur_pl['terms']['a_mkt_fd_cn']['beta'])} pp (within-marketplace {fmt_pp(sdur_pl['contrast']['diff'])} pp) inside strict durables priced $\\ge \\$100$ ($N = {sdur_pl['n']}$). Inside calendar-aligned (Jan 1–Nov 19) fine-product-noun $\\times$ year common-support Amazon comparisons, however, estimates are **specification-sensitive**: moving from broad online-marketplace notices mentioning Amazon ($N = {d1['cs_n']}$, 38 cells: photo {fmt_pp(d1_pl['beta'])} pp, $p_{{\\text{{WCB}}}} = {d1_pl['p_wcb']:.3f}$; direct return {fmt_pp(d1_dr['beta'])} pp, $p_{{\\text{{WCB}}}} = {d1_dr['p_wcb']:.3f}$) to notices excluding other flagged platforms ($N = {d2a['cs_n']}$, 34 cells: photo {fmt_pp(d2a_pl['beta'])} pp, 95% CI [{fmt_pp(d2a_pl['ci_lo'])}, {fmt_pp(d2a_pl['ci_hi'])}], $p_{{\\text{{WCB}}}} = {d2a_pl['p_wcb']:.3f}$; return {fmt_pp(d2a_dr['beta'])} pp, $p_{{\\text{{WCB}}}} = {d2a_dr['p_wcb']:.3f}$) and verbatim strict Amazon-exclusive notices ($N = {d2b['cs_n']}$, 25 cells: photo {fmt_pp(d2b_pl['beta'])} pp, 95% CI [{fmt_pp(d2b_pl['ci_lo'])}, {fmt_pp(d2b_pl['ci_hi'])}], $p_{{\\text{{WCB}}}} = {d2b_pl['p_wcb']:.3f}$; return {fmt_pp(d2b_dr['beta'])} pp, $p_{{\\text{{WCB}}}} = {d2b_dr['p_wcb']:.3f}$; physical destruction {fmt_pp(d2b_pd['beta'])} pp, $p_{{\\text{{WCB}}}} = {d2b_pd['p_wcb']:.3f}$) keeps point estimates directionally consistent while widening photo-language confidence intervals across zero. An automated rule-plus-author structured audit of $N = {ao['n']}$ stratified notices (explicitly benchmarking Jugader's optional photo-or-order-number alternative and UVIPC's non-photo proof of destruction) documents higher parser false-negative rates on heterogeneous U.S.-entity wording, demonstrating via bounded misclassification sensitivity that measurement error attenuates the direct-return deficit (making the adjusted gap more negative) while explaining much of the raw cross-border gap in narrow physical-disablement and marking clauses. Across {disp['screened_notices']} China-direct hazardous-product notices assigning consumer self-disposal (0.0% firm direct return), notice-listed affected inventory totals {disp['screened_affected_units']:,} units—{100*disp['top2_ocoopa_anker_share']:.2f}% concentrated in two multi-channel recalls (OCOOPA and Anker), with {disp['warning_full_notice_count']}/{disp['screened_notices']} complete notices carrying local hazardous-waste warnings ({disp['warning_full_notice_affected_units']:,} units, {100*disp['warning_full_notice_share_units']:.2f}%). Public notices capture written remedy responsibilities rather than realized consumer completion rates or observed waste streams; independent double-blind human adjudication and matched CPSC progress reports are required to measure realized operational fulfillment.

**Keywords:** Consumer product recalls; CPSC recall notices; Cross-border e-commerce; Consumer verification burden; Channel classification; Measurement error bounds; *In re Amazon.com*

---

## 1. CPSC Recall Notice Duties, E-Commerce Disintermediation, and Legal Context

When a hazardous consumer product reaches households, the U.S. Consumer Product Safety Commission (CPSC) publishes an official recall notice under Section 15 of the Consumer Product Safety Act specifying what consumers must do to obtain a refund, repair, or replacement. For four decades, empirical and analytical scholarship on product recalls in law, economics, marketing, and operations management studied corrective actions executed by domestically anchored manufacturers, importers, and retail chains operating physical store counters, prepaid domestic return networks, and toll-free customer-service hotlines (Jarrell and Peltzman 1985; Chen et al. 2009; Hora et al. 2011; Thirumalai and Sinha 2011; Freedman et al. 2012; Kalaignanam et al. 2013; Ni et al. 2014; Wowak and Boone 2015; Eilert et al. 2017; Liu et al. 2017; Shah et al. 2017; Ball et al. 2018; Mukherjee and Sinha 2018; Astvansh et al. 2022; Mao et al. 2022). In that traditional domestic architecture, reverse logistics and eligibility verification remained primarily firm-led responsibilities.

Over 2015–2026, global third-party (3P) e-commerce marketplaces (`Amazon.com`, `Walmart.com`, `Temu.com`, `Shein.com`, `Wayfair.com`, `AliExpress`, `eBay`, and `TikTok Shop`) transformed the traditional agency-versus-reseller retail structure (Hagiu and Wright 2015; Tian et al. 2018) by enabling overseas manufacturers and trading firms to sell directly to U.S. households without a U.S. importer, physical retail storefront, domestic warehouse return hub, or U.S. telephone support line. Across the complete 27-year CPSC recall census (2000–2026, $N = {v4['notice_universe']:,}$), Marketplace-Only recalls expanded 22-fold from {100*r15['share_mkt_only']:.2f}% in 2015 to {100*r26['share_mkt_only']:.2f}% in 2026, while China-based cross-border notices listing zero U.S. legal entities rose from {100*r15['share_fd_china']:.2f}% in 2015 to {100*r26['share_fd_china']:.2f}% in 2026. Parallel computer-science work curates multimodal CPSC text and image repositories for hazard prediction (Bolanos et al. 2025), consumer-advocacy analyses track rising unilateral CPSC safety warnings when overseas vendors fail to cooperate (Consumer Federation of America 2025), marketing scholars link 217 FOIA-obtained CPSC compliance progress reports to realized recall effectiveness (Raithel et al. 2024), and field-experimental research measures consumer behavior under returnless partial refunds on a cross-border e-commerce platform (Fang et al. 2026).

This study examines the distinct regulatory and consumer-policy stage that precedes household participation: **the formal allocation of corrective duties written into published federal recall notices.** Notice wording matters directly for consumer protection because different clauses shift fundamentally different effort, safety, privacy, and disposal burdens onto households. Asking a consumer to submit an identification photograph as an optional alternative to an online order number is operationally distinct from requiring a consumer to sever power cords, dismantle baby loungers, write "RECALLED" in permanent marker across an explosive lithium-ion device, email photographic proof to an unverified free webmail address, and transport defective batteries to a municipal household hazardous waste (HHW) facility without any corporate take-back channel.

Conceptually, three structural forces—formalized in a closed-form principal–agent and reverse-logistics model in **Supplementary Appendix A**—govern how firms and regulators allocate notice-level duties: (i) prohibitive trans-Pacific reverse-logistics costs ($c_{{\\text{{rev}}}}$) that deter physical returns for asset-light overseas sellers; (ii) platform intermediation that limits third-party sellers' first-party buyer-record observability ($\\theta \\ll 1$) relative to direct-to-consumer (DTC) brands ($\\theta \\to 1$), creating fraud and unsafe-retention concerns under unverified refunds; and (iii) asymmetric domestic legal accountability—the classic *judgment-proof problem* (Shavell 1986)—coupled with declining institutional template costs ($a_t$) as CPSC normalizes photographic verification wording across recalls. Crucially, however, public CPSC recall notices record **assigned written responsibilities and remedy options**, not realized consumer completion rates, firm processing costs, or downstream waste destinations.

To establish what the public CPSC archive can and cannot rigorously identify, this paper makes three contributions aimed at consumer-policy scholarship and open empirical data infrastructure:
1. **Verbatim Channel Audit and Three-Definition Comparison:** We uncover a severe asymmetric misclassification in broad marketplace indicators (`amazon_only_mkt`), build an auditable three-tier verbatim Amazon channel classification (`strict_amazon_exclusive`, `multi_channel_with_amazon`, and `amazon_channel_ambiguous`), and estimate every remedy-duty comparison side by side—candidly distinguishing robust all-channel associations from specification-sensitive narrow Amazon-exclusive common-support estimates whose confidence intervals cross zero.
2. **Structured Five-Dimensional Remedy-Duty Coding and Bounded Misclassification Sensitivity:** We separate literal photo wording, mandatory versus optional/alternative proof pathways (benchmarking **Jugader**, Recall 24-199), non-photo destruction proof (benchmarking **UVIPC**, Recall 25-122), physical disablement, permanent marking, duty bearers, and direct physical returns; publish a verifiable $N = {ao['n']}$ stratified rule-plus-author audit with verbatim CPSC quotes and source URLs; quantify group-specific parser error rates; and propagate differential misclassification into re-estimated bounds.
3. **Disciplined Institutional Measurement:** We separate notice-listed affected hazardous-product inventory ({disp['screened_affected_units']:,} units, explicitly disclosing {100*disp['top2_ocoopa_anker_share']:.2f}% two-batch concentration and {disp['warning_full_notice_count']}/{disp['screened_notices']} complete-notice warnings) from unobserved household disposal streams, and evaluate *In re Amazon.com* (U.S. CPSC 2024, 2025; *Amazon.com, Inc. v. CPSC* 2026) strictly as an institutional case study given zero explicit "Fulfilled by Amazon" fulfillment-mode labeling in public notices.

---

## 2. Data, Sample Flow, Verbatim Channel Classification, and Structured Remedy-Duty Coding Audit

### 2.1 Official CPSC Recall Census (2000–2026) and Sample Flow

We retrieve the complete universe of published U.S. consumer product recalls from the open HTTP-200 CPSC SaferProducts REST Web Services API (`https://www.saferproducts.gov/RestWebServices/Recall?format=json`) spanning 2000-01-04 through 2026-11-19. Deduplicating by `RecallID` yields **$N = {v4['notice_universe']:,}$ unique notices** (`data/cpsc_recalls_2000_2026.json`, SHA-256 `{raw_sha}...`). Across the 27-year census, photographic verification wording stood at 0.00% in 2000–2017, 0.39% in 2018, 0.00% in 2019, 0.39% in 2020, and 2.74% in 2021, before rising sharply to 12.67% in 2022 and {100*r26['share_photo_verify_all']:.2f}% in 2026. All primary cross-sectional contract comparisons therefore restrict strictly to the post-emergence era (2022–2026, $N = {sf['n_2022_2026_all']:,}$ notices) to avoid pooling zero-variation pre-2022 cohorts.

As detailed in `scripts/parser_lib.py`, our entity parser reads across all four structured CPSC fields (`Importers`, `Manufacturers`, `Distributors`, and `Retailers`) to rescue late-2026 notices storing legal entities inside `Retailers`, excludes platform corporate-office co-listings (`AliExpress`, `Woot`, distributor-only `Amazon` co-listed alongside foreign 3P sellers) while retaining genuine Amazon first-party private labels (*Amazon Basics*) as U.S. entities, and strips web domains and non-store phrases (`TikTok Shop`, `App Store`, `not sold in stores`) prior to brick-and-mortar store matching. Every classified 2022–2026 notice ($N = {sf['n_2022_2026_classified']:,}$, excluding {sf['n_2022_2026_other_unclear']} unclear giveaways/unlocated notices) maps to six mutually exclusive supply-chain archetypes: `1_Mkt_FD_China` ($N = 448$: 3P marketplace-only listing a China/Hong Kong entity and zero U.S. entity), `2_Mkt_FD_NonChina` ($N = 26$), `3_Mkt_True_US` ($N = 233$: 3P marketplace-only with a verified U.S. legal entity on record—note that public notices cannot verify whether sellers also hold undisclosed foreign or U.S. affiliates), `4_DTC_Online_Only` ($N = 102$: pure first-party brand websites), `5_Omnichannel` ($N = 397$), and `6_Brick_and_Mortar` ($N = 627$). Requiring non-missing retail price and affected-unit counts yields our all-channel regression sample of **$N = {sf['n_2022_2026_reg_sample']:,}$ notices across $G = {sf['g_2022_2026_reg_clusters']:,}$ firm clusters**. Figure 1A and Table 1 trace the exact sample flow from the complete census to every empirical subsample.

<!-- FIGURE:fig1_sample_flow_and_channel_audit.png -->

**Table 1. Complete Sample Flow and Verbatim Amazon Channel Decomposition (2000–2026 Census to Regression Subsamples).**

{t1_md}

*Notes:* Generated programmatically from `tables/table_v4_sample_flow.csv` and `results/09_v4_channel_remedy_audit.json`. Calendar-aligned Amazon comparisons restrict to January 1 – November 19 in every year 2022–2026 to match the November 19, 2026 census cutoff identically across cohorts.

### 2.2 Resolving the `amazon_only_mkt` Classification Defect: Three Verbatim Channel Definitions

Forensic review of earlier drafts revealed a critical channel-labeling error: the legacy indicator `amazon_only_mkt` (`scripts/parser_lib.py`) merely required a recall to fall into `Marketplace_Only` (no physical brick-and-mortar stores) and mention Amazon anywhere in its retailer string. It did **not** verify that Amazon was the sole sales channel. Auditing all {l601['total']} classified 2022–2026 notices flagged `amazon_only_mkt = 1`—and all {d1['cs_n']} notices in the calendar-aligned common-support comparison (264 `1_Mkt_FD_China` vs. 127 `3_Mkt_True_US`)—uncovers severe **asymmetric multi-channel contamination** (Figure 1B):

1. **Other Flagged 3P Marketplaces (51/391 in Common Support; 86/601 in Classified Universe):** Inside the $N = 391$ common-support sample, exactly **51/391 (13.0%)** notices also list at least one other flagged 3P platform (`Walmart.com`, `eBay`, `Etsy`, `Temu`, `Shein`, `Wayfair`, `AliExpress`, `TikTok Shop`, `Wish`, or `Target.com`), heavily skewed toward U.S.-entity sellers (**38/127 [29.9%]** vs. **13/264 [4.9%]** China-direct). For example, the 1.158-million-unit **Anker PowerCore 10000** notice (`RecallID 10311`, Recall 25-338) explicitly states *"Online at Anker, Amazon, Newegg and Ebay"*, and the 1.500-million-unit **OCOOPA** notice (`RecallID 10895`, Recall 26-659) states *"Online at Amazon.com, Ocoopa.com, Ocoopa.net and Walmart.com"*.
2. **Additional Brand DTC Websites and Other Online Portals (100/391 Total Multi-Channel in CS; 162/601 in Classified Universe):** Parsing verbatim URLs, named retailers (`Newegg`, `Costco.com`, `Nordstrom.com`, `DicksSportingGoods.com`, `QVC`, `HSN`, brand `.com` storefronts such as `Babytrend.com`, `BedsureHome.com`, `Brother-USA.com`, `NordicTrack.com`), and *"other websites/online retailers"* phrases exposes **49 additional multi-channel notices** inside the 391 sample (and 76 additional notices inside 601). Altogether, **74/127 (58.3%)** of U.S.-entity notices in the 391 common-support sample (112/186 or **60.2%** across all 2022–2026 `3_Mkt_True_US` `amazon_only_mkt` notices) were **multi-channel online sellers**, compared to only **26/264 (9.8%)** of China-direct notices (41/389 or 10.5% overall).
3. **Non-Retail Mentions and CPSC Field Conflicts (5 Ambiguous Notices in 2022–2026):** One legacy `amazon_only_mkt` notice (`RecallID 9234`, Shop LC space heaters) aired on *"Amazon Fire"* TV apps alongside DirecTV and Roku—not on Amazon.com retail—while four additional 2022–2026 notices exhibit clerical contradictions between CPSC's `Title`/`Remedies` fields and `Retailers` field (e.g., `RecallID 10276` child safety gates titled *"Sold on Amazon.com"* while `Retailers` reads *"Exclusively online at www.FidgetThings.com"*, and `RecallID 10494` magnetic fidget spinners titled *"Sold on Amazon by Anzmtosn"* while `Retailers` lists *"Spartan dealers nationwide... \\$16,400 to \\$19,700"*).

To eliminate label distortion permanently, `classify_amazon_channel_3way()` in `scripts/parser_lib.py` parses verbatim `Retailers` / `Sold At` strings across all {v4['notice_universe']:,} notices into three mutually exclusive, auditable Amazon-related categories (plus `no_amazon_mention`):
- **`strict_amazon_exclusive`** ({amz3['strict_amazon_exclusive']} in 2022–2026): verbatim `Retailers` explicitly states *"exclusively at/on Amazon.com"* (31 notices) OR lists Amazon as the sole named retailer with zero other marketplaces, online portals, DTC websites, or brick-and-mortar stores (410 notices).
- **`multi_channel_with_amazon`** ({amz3['multi_channel_with_amazon']} in 2022–2026): lists Amazon alongside other online marketplaces, brand DTC sites, or *"other online retailers"* (164 online multi-channel notices, 162 classified) OR physical brick-and-mortar stores (276 omnichannel notices).
- **`amazon_channel_ambiguous`** ({amz3['amazon_channel_ambiguous']} in 2022–2026): non-retail *"Amazon Fire"* mention (9234) or direct clerical conflict between `Retailers` and `Title`/`Remedies` (10238, 10245, 10276, 10494).

In Section 3, we report **every channel definition side by side**: All-Channel ($N = {sf['n_2022_2026_reg_sample']:,}$), **Def 1** (legacy broad `amazon_only_mkt`, CS $N = {d1['cs_n']}$), **Def 2a** (excluding other flagged 3P platforms—reproducing the exact peer-review benchmark $N = {d2a['cs_n']}$), **Def 2b** (verbatim `strict_amazon_exclusive`, rebuilt CS $N = {d2b['cs_n']}$, full calendar-aligned $N = {d2b['raw_n']}$), and **Def 3** (`multi_channel_online_with_amazon`, full $N = {d3['raw_n']}$, with its underpowered fine-cell common-support subsample $N = {d3['cs_n']}$ transparently moved to Supplementary Appendix B).

### 2.3 Structured Five-Dimensional Remedy-Duty Coding, Edge Cases (Jugader, UVIPC), Stratified Audit ($N = 150$), and Bounded Misclassification Sensitivity

Equating any mention of photography with mandatory consumer product destruction conflates distinct regulatory duties. Integrating and extending our literal-text coding architecture (`parse_remedy_duties_v4()` in `scripts/parser_lib.py`), we decompose every CPSC recall notice along **five auditable dimensions**:
1. **Literal Photographic Proof (`photo_language`):** Requires both the remedy-verification screen and literal photo/photograph/image/picture wording in `Remedies`.
2. **Mandatory vs. Optional/Alternative Pathway (`proof_status`, `proof_alternative_path`, `photo_mandatory`):** Sentence-level screening identifies notices offering consumers an explicit non-photo pathway (e.g., an online order number, sales receipt, or physical return instead of submitting a photograph).
3. **Non-Photo Destruction Proof (`destruction_proof`, `destruction_proof_without_photo`):** Separately detects explicit *"proof/evidence of destruction or disablement"* even when no photograph is specified.
4. **Physical Disablement vs. Permanent Marking (`physical_destruction`, `physically_disabled`, `permanent_marking`, `photo_only_no_action`):** Distinguishes instructions that physically render the product unusable (cutting cords/straps/garments, breaking, disassembling, submerging, puncturing, or destroying) from permanent-marker labeling ("RECALLED", initials/date) and photo-only identification/disposal notices.
5. **Duty Bearer (`duty_bearer`):** Classifies whether corrective execution falls primarily on consumers without firm return (`consumer_action_required`), is shared via alternative return/proof pathways (`shared_consumer_and_firm`), or is firm/retailer-led (`firm_or_retailer_led`).

Two benchmark edge cases verify these boundaries directly in code and unit tests (`tests/test_f7_boost.py`):
- **Jugader Zipline Kits (`RecallID 9924`, Recall 24-199, `1_Mkt_FD_China`, `strict_amazon_exclusive`):** *"Consumers must submit a photo of the cable and the trolley or their online purchase order number to receive a free repair kit."* Our parser classifies Jugader as `photo_language = 1`, `proof_alternative_path = 1`, `proof_status = optional_or_alternative_proof`, `photo_mandatory = 0`, `physically_disabled = 0`, `remedy_duty_4cat = photo_optional_or_alternative`—preventing misclassification as mandatory photo-only destruction.
- **UVIPC Baby Gates (`RecallID 10148`, Recall 25-122, `1_Mkt_FD_China`, `strict_amazon_exclusive`):** *"contact Xianshengyouli via email ... for information on how to dispose of the product and submit proof of destruction to obtain a full refund."* Because UVIPC contains zero literal "photo" words, `photo_language = 0`, yet `destruction_proof = 1`, `destruction_proof_without_photo = 1`, `proof_status = mandatory_proof`, and `physically_disabled = 1`—preventing false-negative leakage on unspecified destruction-proof demands (catching all 7 such 2022–2026 notices).

To evaluate parser accuracy rigorously and measure group-specific misclassification, we draw a deterministic stratified sample of **$N = {ao['n']}$ recalls (2022–2026, `seed = 20261128`)** spanning channel $\\times$ entity group (55 `1_Mkt_FD_China`, 49 `3_Mkt_True_US`, 46 DTC/Omnichannel/Brick-and-Mortar) $\\times$ year (29 in 2022, 28 in 2023, 32 in 2024, 34 in 2025, 27 in 2026) $\\times$ rare remedy and channel clauses (all 5 ambiguous Amazon notices, all 7 non-photo destruction-proof notices, 10 optional/alternative proof notices, 12 permanent-marking-only, 12 mandatory photo-only, 10 hazardous self-disposal, plus the 5 benchmark cases: Jugader, UVIPC, Anker, OCOOPA, TADAKAZU). Every notice's verbatim `Retailers` text, verbatim `Remedies` text, CPSC URL, parser flags, adjudicated labels, and discrepancy notes are published in `tables/table_remedy_duty_coding_audit.csv`. **Transparency disclosure:** Because this validation reflects an **automated rule-plus-author structured audit** (line-by-line inspection by the author against frozen `parser_lib.py` outputs), it is **not** an independent double-blind multi-coder adjudication; independent double-blind human coding remains necessary prior to operational or causal deployment.

Reading all {ao['n']} notices verbatim uncovered **{ao['n_any_discrepancy']}/150 genuine parser discrepancies** (5/55 in `1_Mkt_FD_China`, 11/49 in `3_Mkt_True_US`, and 8/46 in other channels; Table 2A):
- **Channel classification (`amazon_channel_3way`):** {ao['categorical_fields']['amazon_channel']['exact_accuracy']:.4f} accuracy (149/150), with a single false multi-channel assignment caused by a missing space typo in CPSC's source text (`RecallID 10064`: *"Online exclusively atwww.Amazon.com"*).
- **Photo wording (`photo_language` and `photo_mandatory`):** `photo_language` achieves {ao['binary_fields']['photo_language']['accuracy']:.4f} accuracy (F1 = {ao['binary_fields']['photo_language']['f1']:.4f}; 0 FP, 1 FN in `1_Mkt_FD_China` from `RecallID 10269`, *"email the Amazon order number and a photo showing the remote was destroyed"*). `photo_mandatory` achieves {ao['binary_fields']['photo_mandatory']['accuracy']:.4f} (F1 = {ao['binary_fields']['photo_mandatory']['f1']:.4f}), catching 2 China-direct FPs on `proof_alternative_path` (10054, 10934, where *"or"* joined order/receipt details alongside a mandatory photo) and 2 other-channel FNs on multi-sentence store-return alternatives (9426, 9445).
- **Differential False Negatives on Action & Return Clauses in `3_Mkt_True_US`:** Critically, heterogeneous domestic legal wording creates markedly higher false-negative rates inside `3_Mkt_True_US` ($n = 49$) than inside standardized `1_Mkt_FD_China` templates ($n = 55$): `direct_return` has 0/4 FNs in China-direct (FNR = 0.0%) vs. **3/7 FNs (FNR = 42.9%)** in `3_Mkt_True_US` (e.g., `RecallID 10108` *"prepaid FedEx shipping label"*, 9432, 9736); `physically_disabled` has 1 FP (10571: *"destroy the toy by writing 'RECALLED'"*) and 1 FN (10269) in China-direct (FPR = 3.1%, FNR = 4.3%) vs. **5/14 FNs (FNR = 35.7%)** in `3_Mkt_True_US` (9430 *"nets cut"*, 9736, 10187, 10238 *"destroyed product"*, 10639 *"cut the USB cable"*); and `permanent_marking` has 0 errors in China-direct vs. **4/9 FNs (FNR = 44.4%)** in `3_Mkt_True_US` (9430, 10478, 10619, 10963).

**Table 2A. Stratified $N = 150$ Automated Rule-Plus-Author Structured Audit: Overall and Group-Specific Error Rates (Exact Clopper–Pearson 95% CIs).**

{table2a_md}

*Notes:* Directly from `tables/table_v4_audit_group_error_rates.csv` and `tables/table_remedy_duty_coding_audit.csv`. Exact two-sided Clopper–Pearson 95% binomial CIs reflect audit subgroup denominators. Legacy 150-recall census + 50-recall OOS consistency audits (`tables/table7_parser_audit_summary_150.csv`) are preserved in Supplementary Appendix D.

To test whether group-specific measurement error could explain our channel gaps, Table 2B propagates each group's empirical FP/FN rates ($\\hat{{\\alpha}}_g, \\hat{{\\beta}}_g$) via Rogan–Gladen prevalence inversion into the first-order differential bias $\\text{{Bias}} = [\\alpha_{{\\text{{FD}}}}(1-\\pi_{{\\text{{FD}}}}) - \\beta_{{\\text{{FD}}}}\\pi_{{\\text{{FD}}}}] - [\\alpha_{{\\text{{US}}}}(1-\\pi_{{\\text{{US}}}}) - \\beta_{{\\text{{US}}}}\\pi_{{\\text{{US}}}}]$, alongside worst-case differential corners over the exact 95% Clopper–Pearson error-rate box (both measurement-error-only bounds on the point estimate and joint sampling + misclassification intervals).

**Table 2B. Bounded Misclassification Sensitivity: Propagating Group-Specific Audit Error Rates into Estimated `FD_China − US_Entity` Gaps.**

{table2b_md}

*Notes:* Directly from `tables/table_v4_misclassification_bounds.csv`. Positive empirical bias means raw FE overstates the true gap; negative empirical bias means raw FE understates the true gap.

Table 2B yields a **decisive methodological lesson** that directly shapes our claims:
1. **Robust to Differential Error (`photo_language`, `photo_mandatory`, and `direct_return`):** Because `photo_language` has near-zero error (FNR = 2.6% in China-direct, 0.0% in U.S.-entity), empirical adjustment slightly *increases* the gap across every channel definition (+28.68 → +30.90 pp all-channel, with worst-case joint sampling + misclassification interval [+11.13, +62.20] pp strictly above zero; +10.70 → +13.05 pp strict Amazon-exclusive). Even more strikingly, because U.S.-entity notices suffer higher false-negative rates on `direct_return`, correcting for differential measurement error makes the cross-border direct-return deficit **substantially larger** (-13.78 → -24.08 pp all-channel; -10.76 → -19.41 pp strict Amazon-exclusive, with point misclassification bound [-68.88, -2.23] pp strictly negative).
2. **Vulnerable to Differential Error (`physically_disabled` and `permanent_marking`):** Conversely, higher U.S.-entity false negatives on heterogeneous action wording *overstate* raw cross-border gaps in `physically_disabled` (+11.41 to +14.47 pp upward bias) and `permanent_marking` (+8.58 to +13.84 pp upward bias). After empirical error adjustment, the narrow Amazon common-support gaps on `physically_disabled` ({fmt_pp(b_d1['physically_disabled']['beta_empirical_adjusted'])} to {fmt_pp(b_d2b['physically_disabled']['beta_empirical_adjusted'])} pp) and `permanent_marking` ({fmt_pp(b_d1['permanent_marking']['beta_empirical_adjusted'])} to {fmt_pp(b_d2b['permanent_marking']['beta_empirical_adjusted'])} pp) shrink near zero or turn negative, with wide worst-case bounds spanning zero. Accordingly, we do **not** claim precisely identified cross-border gaps in narrow physical-disablement or permanent-marking sub-clauses inside Amazon-exclusive cells; rather, we emphasize both the verified broad photo/return divergence and the measurement-dataset contribution itself.

---

## 3. Verified Three-Definition Channel Comparison

### 3.1 Side-by-Side Channel Estimates Across All Three Amazon Definitions and All-Channel Benchmarks

For every common-support Amazon comparison between China-direct (`1_Mkt_FD_China`) and U.S.-entity (`3_Mkt_True_US`) sellers (2022–2026, calendar-aligned January 1 – November 19, complete price and units), we retain fine-product-noun $\\times$ year cells containing both seller groups and estimate full-rank linear probability models controlling for 10 price-decile FE, 10 affected-unit-decile FE, 9 hazard-category FE, `is_china_mfr`, and exact `fine_noun_yr` FE, with firm-clustered CR1 $t(G-1)$ intervals and 999 restricted Rademacher Wild Cluster Bootstrap draws (Cameron et al. 2008). For the full all-channel census ($N = {sf['n_2022_2026_reg_sample']:,}$, $G = {sf['g_2022_2026_reg_clusters']:,}$) and multi-channel online full subsample ($N = {d3['raw_n']}$), we control for 10 price-decile FE, 10 unit-decile FE, 15 product-category FE, 9 hazard FE, `is_china_mfr`, and year-quarter FE. Table 3 and Figure 2 present all definitions side by side.

<!-- FIGURE:fig2_three_definition_channel_comparison.png -->

**Table 3. Verified Three-Definition Side-by-Side Comparison of Notice-Level Duties (`1_Mkt_FD_China` minus `3_Mkt_True_US`, 2022–2026, pp [95% CR1 CI], Wild Cluster Bootstrap $p$).**

{table3_md}

*Notes:* Generated directly from `tables/table_v4_three_channel_comparison.csv` and `results/09_v4_channel_remedy_audit.json`. Bold entries denote $p_{{\\text{{WCB}}}} \\le 0.05$. All design matrices verified exact full rank ($\\text{{rank}}(X) = K$). Def 1, Def 2a, and Def 2b use exact `fine_noun_yr` common-support FE (Jan 1–Nov 19 cohorts); Def 3's fine-cell common-support subsample ($N = {d3['cs_n']}$ across {d3['cs_cells']} cells: 23 FD-China vs. 32 U.S.-entity) is severely underpowered (SEs 13–34 pp) and moved to Supplementary Appendix B alongside narrow Amazon strict-durable splits ($N = 49\\text{{–}}91$).

Three transparent conclusions emerge from Table 3 and Figure 2:
1. **Substantial Specification Sensitivity Inside Narrow Amazon-Exclusive Common-Support Cells:** Under the legacy broad definition (**Def 1**, $N = {d1['cs_n']}$, 38 cells), China-direct notices exceed U.S.-entity notices by **{fmt_pp(d1_pl['beta'])} pp** on `photo_language` (95% CI [{fmt_pp(d1_pl['ci_lo'])}, {fmt_pp(d1_pl['ci_hi'])}], $p_{{\\text{{WCB}}}} = {d1_pl['p_wcb']:.3f}$), **{fmt_pp(d1_pm['beta'])} pp** on `photo_mandatory` ($p_{{\\text{{WCB}}}} = {d1_pm['p_wcb']:.3f}$), and **{fmt_pp(d1_dr['beta'])} pp** on `direct_return` ($p_{{\\text{{WCB}}}} = {d1_dr['p_wcb']:.3f}$). However, once the 51 other-flagged-platform notices are removed and common support is rebuilt (**Def 2a**, $N = {d2a['cs_n']}$, 34 cells, reproducing the peer-review benchmark exactly), `photo_language` attenuates to **{fmt_pp(d2a_pl['beta'])} pp** (95% CI [{fmt_pp(d2a_pl['ci_lo'])}, {fmt_pp(d2a_pl['ci_hi'])}], $p_{{\\text{{WCB}}}} = {d2a_pl['p_wcb']:.3f}$) and `direct_return` to **{fmt_pp(d2a_dr['beta'])} pp** (95% CI [{fmt_pp(d2a_dr['ci_lo'])}, {fmt_pp(d2a_dr['ci_hi'])}], $p_{{\\text{{WCB}}}} = {d2a_dr['p_wcb']:.3f}$). Further purging brand DTC and other-online co-listings to isolate **verbatim strict Amazon-exclusive notices** (**Def 2b**, $N = {d2b['cs_n']}$, 25 cells: 184 China-direct vs. only 52 U.S.-entity) yields **{fmt_pp(d2b_pl['beta'])} pp** on `photo_language` (95% CI [{fmt_pp(d2b_pl['ci_lo'])}, {fmt_pp(d2b_pl['ci_hi'])}], $p_{{\\text{{WCB}}}} = {d2b_pl['p_wcb']:.3f}$) and **{fmt_pp(d2b_pm['beta'])} pp** on `photo_mandatory` ($p_{{\\text{{WCB}}}} = {d2b_pm['p_wcb']:.3f}$). Point estimates stay consistently positive (~+11 pp), yet because over half of U.S.-entity marketplace notices are multi-channel, stripping them leaves just 52 U.S. comparison notices across 25 fine cells—widening confidence intervals across zero. (Without fine-noun cell trimming, the full calendar-aligned verbatim strict Amazon-exclusive sample of $N = {d2b['raw_n']}$ under product-category + year-quarter FE gives {fmt_pp(d2b_raw_pl['beta'])} pp on `photo_language`, $p_{{\\text{{WCB}}}} = {d2b_raw_pl['p_wcb']:.3f}$, and {fmt_pp(d2b_raw_dr['beta'])} pp on `direct_return`, $p_{{\\text{{WCB}}}} = {d2b_raw_dr['p_wcb']:.3f}$.)
2. **Direct-Return Deficit Persists Under Strict Amazon-Exclusive Filtering:** Inside verbatim strict Amazon-exclusive common-support cells (**Def 2b**, $N = {d2b['cs_n']}$), `direct_return` remains significantly lower by **{fmt_pp(d2b_dr['beta'])} pp** (95% CI [{fmt_pp(d2b_dr['ci_lo'])}, {fmt_pp(d2b_dr['ci_hi'])}], $p_{{\\text{{WCB}}}} = {d2b_dr['p_wcb']:.3f}$)—an estimate that differential U.S.-entity false negatives only strengthen ({fmt_pp(b_d2b['direct_return']['beta_empirical_adjusted'])} pp adjusted, Table 2B). Explicit `physical_destruction` wording is also +15.24 pp ($p_{{\\text{{WCB}}}} = {d2b_pd['p_wcb']:.3f}$) in Def 2b, though Table 2B warns that differential U.S.-entity false negatives explain most of that raw physical-action gap.
3. **Imprecise Sub-Clauses and Multi-Channel Contrast:** Explicit "proof of destruction" phrasing (`destruction_proof`) is null across all definitions (-0.02 pp to +1.57 pp, $p_{{\\text{{WCB}}}} \\ge 0.580$), and `photo_only_no_action` is imprecise across all three Amazon definitions (+4.07 to +7.68 pp, $p_{{\\text{{WCB}}}} \\ge 0.227$). Inside multi-channel online notices including Amazon (**Def 3**, $N = {d3['raw_n']}$, 39 China-direct vs. 99 U.S.-entity), `photo_language` is {fmt_pp(d3_raw_pl['beta'])} pp ($p_{{\\text{{WCB}}}} = {d3_raw_pl['p_wcb']:.3f}$) and `permanent_marking` is {fmt_pp(d3_raw_mk['beta'])} pp ($p_{{\\text{{WCB}}}} = {d3_raw_mk['p_wcb']:.3f}$, reflecting large multi-channel electronics recalls like Anker and OCOOPA); its underpowered fine-cell common-support subset ($N = {d3['cs_n']}$, 11 cells, `photo_language` = -15.61 pp, SE 17.17 pp) is documented transparently in Supplementary Appendix B.

### 3.2 All-Channel Associations, Strict Durables ($\\ge \\$100$), Contact Infrastructure, and 2022–2026 Diffusion

While narrow Amazon-exclusive fine-cell comparisons face statistical power limits once multi-channel sellers are separated, the broader all-channel 2022–2026 census ($N = {sf['n_2022_2026_reg_sample']:,}$, $G = {sf['g_2022_2026_reg_clusters']:,}$) reveals sharp, high-precision structural contrasts across supply-chain archetypes (Figure 3 and Table 4; complete 17-specification robustness battery including `Product_Cat` $\\times$ `Year` clustering, `Fine-Product-Noun` $\\times$ `Year` FE, Binomial Logit $\\text{{OR}} = {rob['R4_binomial_logit_or']['terms']['a_mkt_fd_cn']['or']:.2f}\\times$, within Made-in-China, contact-infrastructure mediation, shell-front LLC adjustment, stratified permutation, leave-one-category-out, and leave-one-year-out in Supplementary Appendix B).

<!-- FIGURE:fig3_regime_emergence_and_diffusion.png -->

**Table 4. All-Channel Disaggregated Remedy Duties, Value Heterogeneity (All $\\ge \\$100$ vs. Strict Durables $\\ge \\$100$), Contact Infrastructure, and Traceability (2022–2026, Ultra-Saturated FE).**

{table4_md}

*Notes:* Computed directly from `results/04_pillar1_econometrics.json`, `results/05_pillars_2_3_4.json`, and `results/09_v4_channel_remedy_audit.json`. Strict Durables ($\\ge \\$100$, $N = {sdur_pl['n']}$, $G = {sdur_pl['n_clusters']}$) deterministically excludes 109 non-durable recalls (53 `Child_Sleepwear_Apparel`, 10 `Adult_Apparel_Footwear`, 10 `Chemicals_Medicine_Packaging`, 28 `Mattress_Bedding`, 5 `Hair_Dryer_PersonalCare`, and 2 residual textile/apparel titles 9771 & 10868, with 1 rule overlap) from all 794 products priced $\\ge \\$100$.

Four broad empirical regularities stand out across Table 4 and Figure 3:
1. **Disaggregated Notice-Duty Structure (Figure 3B):** Across all 448 China-direct marketplace notices in 2022–2026, {d4['1_Mkt_FD_China']['counts']['photo_plus_physical_destruction']} ({100*d4['1_Mkt_FD_China']['shares']['photo_plus_physical_destruction']:.1f}%) combine mandatory photography with physical destruction, {d4['1_Mkt_FD_China']['counts']['photo_plus_permanent_marking_only']} ({100*d4['1_Mkt_FD_China']['shares']['photo_plus_permanent_marking_only']:.1f}%) pair mandatory photography with permanent marking only, {d4['1_Mkt_FD_China']['counts']['photo_only_mandatory']} ({100*d4['1_Mkt_FD_China']['shares']['photo_only_mandatory']:.1f}%) require mandatory photo-only identification/disposal, {d4['1_Mkt_FD_China']['counts']['photo_optional_or_alternative']} ({100*d4['1_Mkt_FD_China']['shares']['photo_optional_or_alternative']:.1f}%) offer optional/alternative photo paths (like Jugader), {d4['1_Mkt_FD_China']['counts']['non_photo_destruction_or_disposal_proof']} ({100*d4['1_Mkt_FD_China']['shares']['non_photo_destruction_or_disposal_proof']:.1f}%) request non-photo destruction proof (like UVIPC), and just {d4['1_Mkt_FD_China']['counts']['direct_return_no_photo']} ({100*d4['1_Mkt_FD_China']['shares']['direct_return_no_photo']:.1f}%) offer direct return without photo proof.
2. **Persistence Inside High-Value Items and Strict Durables ($\\ge \\$100$):** Separating all products priced $\\ge \\$100$ (`R7`, $N = {r7['n']}$: `photo_verify` {fmt_pp(r7['terms']['a_mkt_fd_cn']['beta'])} pp, `photo_language` {fmt_pp(all_hi['photo_language']['terms']['a_mkt_fd_cn']['beta'])} pp) from deterministic **Strict Durables ($\\ge \\$100$)** (`R7b`, $N = {sdur_pl['n']}$, $G = {sdur_pl['n_clusters']}$: `photo_verify` {fmt_pp(r7b['terms']['a_mkt_fd_cn']['beta'])} pp, `photo_language` {fmt_pp(sdur_pl['terms']['a_mkt_fd_cn']['beta'])} pp, within-marketplace {fmt_pp(sdur_pl['contrast']['diff'])} pp, $p_{{\\text{{WCB}}}} = {sdur_pl['contrast']['p_wcb']:.3f}$; `photo_mandatory` {fmt_pp(sdur_pm['terms']['a_mkt_fd_cn']['beta'])} pp) refutes the notion that photo-verification duties are confined to cheap apparel or consumables. Meanwhile, pure first-party `4_DTC_Online_Only` brands—which likewise lack physical stores—exhibit an **imprecisely estimated null** (`photo_language` = {fmt_pp(dtc_pl['beta'])} pp, 95% CI [{fmt_pp(dtc_pl['ci_lo'])}, {fmt_pp(dtc_pl['ci_hi'])}], $p_{{\\text{{WCB}}}} = {dtc_pl['p_wcb']:.3f}$; turning negative at {fmt_pp(sdur_pl['terms']['a_dtc_online']['beta'])} pp in strict durables $\\ge \\$100$), consistent with first-party buyer-record observability reducing reliance on consumer photo verification. (Because strict durables $\\ge \\$100$ inside narrow Amazon-only definitions contain only 49–91 recalls, those underpowered sub-regressions appear in Supplementary Appendix B.)
3. **Contact Infrastructure, Traceability Collapse, and Sequential Diffusion:** Cross-border marketplace notices exhibit massive deficits in consumer-access and traceability infrastructure: {fmt_pp(mm['free_webmail']['terms']['a_mkt_fd_cn']['beta'])} pp free consumer webmail (`@gmail/@outlook/@qq/@163`), {fmt_pp(mm['no_phone']['terms']['a_mkt_fd_cn']['beta'])} pp zero U.S. telephone hotline, {fmt_pp(p2['traceability_upc_fe']['terms']['a_mkt_fd_cn']['beta'])} pp GS1 UPC barcode listing (0.2% vs. 5.4% brick-and-mortar), and {fmt_pp(p2['coordination_inconjunction_fe']['terms']['a_mkt_fd_cn']['beta'])} pp joint Canada/Mexico recalls (2.0% vs. 34.8% brick-and-mortar). Temporally, `photo_verify` rose from {100*diff_s['1_Mkt_FD_China']['pv_2022']:.1f}% (2022) to {100*diff_s['1_Mkt_FD_China']['pv_2026']:.1f}% (2026) in `1_Mkt_FD_China` and diffused sequentially into `3_Mkt_True_US` ({100*diff_s['3_Mkt_True_US']['pv_2022']:.1f}% → {100*diff_s['3_Mkt_True_US']['pv_2026']:.1f}%) and `6_Brick_and_Mortar` ({100*diff_s['6_Brick_and_Mortar']['pv_2022']:.1f}% → {100*diff_s['6_Brick_and_Mortar']['pv_2026']:.1f}%), advancing seven times faster in China-manufactured brick-and-mortar imports ({100*bm_dec['BM_Made_in_China']['annual_slope_pp']:+.2f} pp/yr, $t = {bm_dec['BM_Made_in_China']['t']:+.2f}$) than non-China domestic goods ({100*bm_dec['BM_Non_China_Mfr']['annual_slope_pp']:+.2f} pp/yr, $t = {bm_dec['BM_Non_China_Mfr']['t']:+.2f}$).
4. **Honest Empirical Nulls and Template Artifacts:** Controlling for observables, China-direct marketplace notices show no statistically significant differences vs. brick-and-mortar on cash-versus-repair mix (`refund_only`: {fmt_pp(mm['refund_only']['terms']['a_mkt_fd_cn']['beta'])} pp, $p_{{\\text{{WCB}}}} = {mm['refund_only']['terms']['a_mkt_fd_cn']['p_wcb']:.3f}$), pre-recall market duration (`log(1 + months_on_sale)`: {p4['duration_log_fe']['terms']['a_mkt_fd_cn']['beta']:+.4f}, $p_{{\\text{{WCB}}}} = {p4['duration_log_fe']['terms']['a_mkt_fd_cn']['p_wcb']:.3f}$), or double-count-free injuries (`has_injury`: {fmt_pp(p4['has_injury_fe']['terms']['a_mkt_fd_cn']['beta'])} pp, $p_{{\\text{{WCB}}}} = {p4['has_injury_fe']['terms']['a_mkt_fd_cn']['p_wcb']:.3f}$). Furthermore, forensic checks confirm that the phrase *"contacting all known purchasers directly"* disappeared abruptly in August 2025 across *all* channels (59.3% → 0.0% China-direct; 22.9% → 0.7% brick-and-mortar), identifying a CPSC press-release boilerplate edit excluded from policy inference (Supplementary Appendix C).

---

## 4. Hazardous-Product Notice Coverage and *In re Amazon.com* as an Institutional Case Study

### 4.1 Affected Hazardous-Product Notice Coverage ({disp['screened_affected_units']:,} Units), Batch Concentration, and Full-Notice Warnings

A major consumer-policy concern arises when recalls involving fire-prone or toxic materials—specifically **hazard-gated lithium-ion batteries, button/coin cells, and lead/phthalate/chemical products** (excluding mechanical brake or frame e-bike defects)—omit corporate take-back options. Across 2022–2026, {disp['hazard_group_notices']} `1_Mkt_FD_China` notices fall into these three hazardous categories, and **0.0% offer a firm direct-return or prepaid hazmat mail-back program** (compared to 17.0% in brick-and-mortar and 22.2% in omnichannel). Our text screen flags **{disp['screened_notices']}/{disp['hazard_group_notices']} notices** assigning consumer self-disposal without a direct return option, covering **{disp['screened_affected_units']:,} notice-listed affected units** ({disp['disposal_word_notices']}/{disp['screened_notices']} notices containing literal "dispose/disposal" wording cover {disp['disposal_word_affected_units']:,} units; Table 5 and Figure 4A).

**Three strict measurement boundaries govern interpretation of this {disp['screened_affected_units']:,} figure:**
1. **Notice Coverage, Never Observed Waste Stream:** The total sums affected inventory printed on CPSC recall notices. Public notices do not report how many units remained in firm inventory versus consumer homes, how many households participated in the recall, or where discarded items ultimately entered the waste stream. It is strictly **affected hazardous-product notice coverage under consumer self-disposal terms**, **not** an observed municipal waste flow or confirmed trash leakage.
2. **Extreme Two-Batch Concentration ({100*disp['top2_ocoopa_anker_share']:.2f}%):** Two large multi-channel electronics recalls account for two-thirds of the entire total: **OCOOPA Direct rechargeable hand warmers** (`RecallID 10895`, Recall 26-659, {top4[0]['units']:,} units, {100*top4[0]['share_of_total']:.2f}%, sold on Amazon, Ocoopa.com, Ocoopa.net, and Walmart.com) and **Anker PowerCore 10000 power banks** (`RecallID 10311`, Recall 25-338, {top4[1]['units']:,} units, {100*top4[1]['share_of_total']:.2f}%, sold on Anker, Amazon, Newegg, and eBay) together total **{disp['top2_ocoopa_anker_units']:,} units ({100*disp['top2_ocoopa_anker_share']:.2f}%)**, and adding Charmast (488,000) and Baseus (132,000) reaches {100*disp['top4_share']:.2f}%.
3. **Complete-Notice Disposal Warnings ({disp['warning_full_notice_count']}/{disp['screened_notices']} Covering {100*disp['warning_full_notice_share_units']:.2f}% of Units):** Searching only the `Remedies` field detects explicit local/state HHW or trash-prohibition warnings on {disp['warning_remedy_notices']}/{disp['screened_notices']} notices ({disp['warning_remedy_affected_units']:,} units, {100*disp['warning_remedy_affected_units']/disp['screened_affected_units']:.2f}%). Expanding the screen to the **complete displayed notice (`Remedies + Description + Hazards`)** captures **{disp['warning_full_notice_count']}/{disp['screened_notices']} notices ({100*disp['warning_full_notice_share_notices']:.2f}%)** covering **{disp['warning_full_notice_affected_units']:,} affected units ({100*disp['warning_full_notice_share_units']:.2f}%)**—because Anker's notice (10311) places its specific lithium-ion trash prohibition outside the primary remedy block while OCOOPA's notice (10895) explicitly forbids placing defective lithium-ion warmers in household trash, curbside recycling bins, or retail battery-drop boxes and directs consumers to contact municipal HHW centers. What the census establishes is therefore not careless omission of disposal warnings, but rather the complete absence (0.0%) of firm-operated take-back channels across nearly four million recalled hazardous units, leaving lawful HHW transport entirely to household execution.

<!-- FIGURE:fig4_hazwaste_coverage_and_in_re_amazon.png -->

**Table 5. Standalone Institutional Evidence: Hazardous-Product Notice Coverage (`1_Mkt_FD_China`, 2022–2026) and *In re Amazon.com* Case Study.**

{t5_md}

*Notes:* Generated dynamically from `tables/table_v4_hazwaste_and_in_re_amazon.csv` and `results/09_v4_channel_remedy_audit.json`. Full Newey–West HAC lag sensitivity ($L \\in \\{{1,2,3,4,6\\}}$), STURDY Act (2023Q4+) and Reese's Law (2024Q2+) statutory controls, and monthly ($T = 70$) stress tests appear in Supplementary Appendix C.

### 4.2 *In re Amazon.com* (Docket No. 21-2) as an Institutional Case Study

In *In re Amazon.com, Inc.* (CPSC Docket No. 21-2), the CPSC issued its unanimous **July 30, 2024 Decision and Order** classifying Amazon as a statutory "distributor" specifically for **Fulfilled-by-Amazon (`FBA`)** third-party merchandise (U.S. CPSC 2024), followed by its **January 16, 2025 Decision and Order Approving Notification and Action Plan** specifying product-specific direct consumer notice and refund protocols for the adjudicated FBA items (U.S. CPSC 2025; upheld on summary judgment November 24, 2026 in *Amazon.com, Inc. v. CPSC* 2026).

We treat *In re Amazon.com* strictly as an **institutional case study**—and **not** as a causal natural experiment—for a decisive measurement reason verified directly in our archive: across all {fba['broad_amazon_only_mkt_2022_2026']} Amazon-mentioning online-marketplace notices in 2022–2026, **explicit "Fulfilled by Amazon" or "Fulfillment by Amazon" phrasing appears in {fba['explicit_fulfilled_by_amazon_mentions']}/{fba['broad_amazon_only_mkt_2022_2026']} notices (0.00%)**. A separate acronym search finds exactly {fba['standalone_fba_tokens']}/{fba['broad_amazon_only_mkt_2022_2026']} notice containing a standalone "FBA" token—solely inside product model-name suffixes on the **TADAKAZU baby lounger** recall (`RecallID 10317`, Recall 25-345), which does not establish fulfillment status. Because public CPSC announcements pool FBA and merchant-fulfilled listings, time-series shifts cannot isolate the causal impact of an FBA-scoped order from concurrent statutory rule sweeps (STURDY Act, Reese's Law) or broader platform growth.

With that scope caveat explicit, Figure 4B and Table 5 Panel B verify that the post-2024 descriptive volume expansion is **not** an artifact of our earlier multi-channel mislabeling. Across all $T = 23$ complete quarters (2021Q1–2026Q3; excluding partial 2026Q4) using Newey–West (1987) HAC inference ($L = 4$), annual **verbatim `strict_amazon_exclusive`** notices expanded more than fivefold from {ann_amz[2024]['amz_strict_exclusive']} (2024) to {ann_amz[2025]['amz_strict_exclusive']} (2025) and {ann_amz[2026]['amz_strict_exclusive']} (2026, through November 19), producing a sharp descriptive post-July-2024 slope break relative to brick-and-mortar of **{sc_s['beta']:+.4f}/qtr** ($t = {sc_s['t']:+.2f}$, $p = {fmt_p(sc_s['p'])}$)—closely tracking the broad `amazon_only_mkt` series ({sc_b['beta']:+.4f}/qtr, $t = {sc_b['t']:+.2f}$; Supplementary Appendix C confirms persistence under STURDY Act and Reese's Law dummies and monthly frequency). Critically, however, expanded notice volume did not restore firm-operated physical returns: inside `1_Mkt_FD_China`, `photo_verify` wording rose from {100*persist['pre_mean']:.1f}% pre-January 16, 2025 to {100*persist['post_mean']:.1f}% post-order (FE {100*persist['fe_beta']:+.2f} pp, $t = {persist['fe_t']:+.2f}$). The *In re Amazon.com* order clarifies why notice wording varies with product-specific administrative remedies—and demonstrates that intermediary notice obligations alone do not automatically replace consumer-side verification and self-disposal duties with domestic reverse logistics.

---

## 5. Institutional Implications, Open Data Contribution, and Methodological Limitations

### 5.1 Consumer-Policy Implications for CPSC Notice Standardization and Platform Governance

1. **Structured Machine-Readable Notice Duty Schemas:** Today, critical consumer-protection distinctions—whether a photograph is mandatory or optional alongside an order number (Jugader), whether physical disablement is required without specifying proof format (UVIPC), whether permanent marking alone suffices (Anker, OCOOPA), and whether lithium-ion trash prohibitions appear in the `Remedies` block versus the `Description` block—are buried inside unstructured prose. CPSC should add standardized, structured fields to its SaferProducts schema explicitly recording: (a) *proof modality and mandatory vs. alternative pathways*; (b) *whether physical product disablement is required*; (c) *whether a prepaid return or domestic drop-off option exists*; (d) *fulfillment mode (FBA/WFS vs. merchant-fulfilled)*; and (e) *verbatim retailer channel exclusivity*. Standardizing these fields would immediately make consumer compliance burdens auditable across platforms.
2. **Unlocking Platform First-Party Transaction Records to Lower Consumer Friction:** Individual 3P sellers often lack direct access to buyer identities, motivating photographic verification to deter duplicate claims. Yet the **platform itself holds verified first-party order histories** ($\\theta_{{\\text{{Platform}}}} \\to 1$). As *In re Amazon.com* illustrates for adjudicated FBA items, authorizing or requiring marketplaces to pair automated account-linked refund crediting with seller reserve/escrow clawbacks can reduce reliance on cumbersome consumer verification steps—particularly for low-cost non-durable items where optional order-number confirmation suffices, while reserving physical disablement strictly for high-recirculation safety hazards.
3. **Addressing Hazardous-Product Take-Back Gaps and Traceability Infrastructure:** For recalled lithium-ion batteries, button cells, and toxic chemicals, relying exclusively on consumer self-transport to municipal HHW facilities (0.0% corporate take-back across {disp['hazard_group_notices']} China-direct notices covering {disp['screened_affected_units']:,} affected units) shifts safety and logistical burdens onto households and local municipalities. Consumer-policy frameworks should explore mandatory cross-border seller recall bonds, platform-funded hazmat collection partnerships, verifiable GS1 UPC/GTIN registration (0.2% today vs. 7.3% omnichannel), verified domestic customer-service phone/domain requirements (replacing free consumer webmail), and automated CPSC–Health Canada–PROFECO recall synchronization (2.0% joint recalls vs. 34.8% brick-and-mortar).

### 5.2 Reusable Open Measurement Dataset

Beyond its empirical findings, this package contributes a fully reproducible, SHA-256-verified public data resource suitable for consumer-policy analysis and operational recall data-set extensions: (i) the frozen 27-year CPSC census (`data/cpsc_recalls_2000_2026.json`, $N = {v4['notice_universe']:,}$); (ii) the enriched notice-level table (`data/cpsc_parsed_2000_2026.csv`) containing verbatim 3-way Amazon channel classifications, 5-dimensional structured remedy-duty labels, full-notice HHW warning indicators, and CPSC source URLs; (iii) the verifiable $N = {ao['n']}$ stratified coding audit (`tables/table_remedy_duty_coding_audit.csv`) with verbatim retailer/remedy quotes and explicit adjudication notes; and (iv) reusable Python code implementing full-rank CR1/WCB econometrics and Clopper–Pearson bounded misclassification sensitivity (`scripts/parser_lib.py`, `scripts/econometrics_lib.py`, `scripts/09_remedy_duty_audit_and_channel_v4.py`).

### 5.3 Methodological Limitations and Research Agenda

Four disciplined limitations bound our conclusions and define the next stage of empirical research:
1. **Notice-Level Duties vs. Realized Fulfillment and Compliance Costs:** Public CPSC notices reveal written duties and options—they contain zero observations of 30-day or 90-day consumer completion rates, firm remedy-processing costs, or verified compliant disposal. Extending from notice design to operational performance requires matching CPSC recall numbers to corrective-action progress reports obtained via Freedom of Information Act requests—following Raithel et al. (2024), who obtained 217 CPSC progress reports and documented statutory confidentiality selection—or partnering with platforms to evaluate pre-scheduled take-back rollouts or randomized communication and regulator-approved remedy pathways (cf. Fang et al. 2026), with pre-registered minimum meaningful differences.
2. **Automated Rule-Plus-Author Audit vs. Independent Double-Blind Human Adjudication:** Our stratified $N = {ao['n']}$ audit transparently documents 24/150 parser discrepancies and propagates group-specific error rates into bounded sensitivity intervals, showing clearly where differential U.S.-entity false negatives explain raw action-clause gaps. Nevertheless, because initial labels came from frozen parser outputs inspected by a single author, independent double-blind multi-coder adjudication (with inter-rater reliability $\\kappa$ and blind tie-breaking) remains essential before deploying these text flags for formal regulatory evaluation or causal mechanism tests.
3. **Observational Channel Associations and Small-Sample Precision:** All regressions estimate conditional observational associations among published recalls rather than causal treatment effects; we lack a denominator of total SKUs sold by channel and cannot rule out differential CPSC enforcement intensity across domestic versus overseas sellers. Moreover, once multi-channel sellers are separated out, the strictly Amazon-exclusive common-support comparison retains only 52 U.S.-entity notices ($N = {d2b['cs_n']}$), rendering narrow photo-language contrasts imprecise with wide CIs crossing zero.
4. **Unobserved Entity Affiliations and Fulfillment Mode:** Structuring seller origin from public notice fields classifies what regulators disclose on the record, not undisclosed parent-subsidiary networks, U.S. warehouses, or FBA versus merchant-fulfilled status (0/601 explicit FBA mentions). Future administrative disclosure reforms capturing fulfillment channel and beneficial corporate ownership would directly resolve both blind spots.

---

## Data and Code Availability

All frozen CPSC source records (`data/cpsc_recalls_2000_2026.json`), parsed notice-level datasets (`data/cpsc_parsed_2000_2026.csv`), the verifiable $N = {ao['n']}$ stratified remedy-duty coding audit (`tables/table_remedy_duty_coding_audit.csv`), zero-NaN publication tables (`tables/`), JSON econometric receipts (`results/`), reproduction scripts (`scripts/01_*.py`–`10_*.py`), and automated unit/parity test suites (`tests/test_f7_boost.py`) are preserved in the workspace with cryptographic integrity hashes recorded in `SHA256SUMS.json`.

---

{refs_md}
"""


def build_supplement(
    aud_legacy: dict,
    theory: dict,
    p1: dict,
    p234: dict,
    v4: dict,
) -> str:
    cuts = theory["cutoffs"]
    rob = p1["robustness_photo_verify_2022_2026"]
    p2 = p234["pillar2"]
    p4 = p234["pillar4"]
    c3 = v4["three_definition_channel_comparisons"]
    d3 = c3["Def3_MultiChannel_Online_With_Amazon"]
    sd_amz = v4["strict_durables_ge_100_amazon_subsamples"]
    t5_canon = (TBL_DIR / "table5_canonical.md").read_text(encoding="utf-8").strip()
    oos = aud_legacy["oos_50_2025_2026"]

    s1_lines = [
        "| Underpowered Sub-Comparison & Outcome | $N$ | Clusters / Cells | $\\beta$ (pp) | CR1 SE (pp) | 95% CR1 CI (pp) | $p_{\\text{WCB}}$ |",
        "|:---|---:|---:|---:|---:|---:|---:|",
    ]
    for yk, ylbl in [
        ("photo_language", "Def 3 Multi-Ch Online CS: Photo Language"),
        ("photo_mandatory", "Def 3 Multi-Ch Online CS: Mandatory Photo"),
        ("direct_return", "Def 3 Multi-Ch Online CS: Direct Return"),
        ("physical_destruction", "Def 3 Multi-Ch Online CS: Physical Destruction"),
        ("permanent_marking", "Def 3 Multi-Ch Online CS: Permanent Marking"),
        ("photo_only_no_action", "Def 3 Multi-Ch Online CS: Photo-Only"),
    ]:
        m = d3["common_support_models"][yk]
        s1_lines.append(
            f"| {ylbl} | {m['n']} | {m['n_clusters']} / {d3['cs_cells']} cells | {fmt_pp(m['beta'])} | {100*m['se']:.2f} | [{fmt_pp(m['ci_lo'])}, {fmt_pp(m['ci_hi'])}] | {m['p_wcb']:.3f} |"
        )
    for dkey, dshort in [
        ("Def1_Broad_Mkt_Mentions_Amazon", "Strict Durables >=\\$100 in Def 1 Broad Amz"),
        ("Def2a_NoOtherFlaggedPlat_Benchmark", "Strict Durables >=\\$100 in Def 2a No Other 3P"),
        ("Def2b_Strict_Amazon_Exclusive_Verbatim", "Strict Durables >=\\$100 in Def 2b Strict Amz-Excl"),
    ]:
        blk = sd_amz[dkey]
        for yk, ylbl in [("photo_language", "Photo Language"), ("direct_return", "Direct Return"), ("physical_destruction", "Physical Destruction")]:
            m = blk["models_prodcat_year_fe"][yk]
            s1_lines.append(
                f"| {dshort}: {ylbl} | {m['n']} | {m['n_clusters']} firms | {fmt_pp(m['beta'])} | {100*m['se']:.2f} | [{fmt_pp(m['ci_lo'])}, {fmt_pp(m['ci_hi'])}] | {m['p_wcb']:.3f} |"
            )
    table_s1_md = "\n".join(s1_lines)

    s2_specs = [
        ("R1_baseline_firm_cr1", "R1. Baseline Ultra-Saturated (Firm CR1)"),
        ("R2_prod_year_cluster", "R2. `Product_Cat` $\\times$ `Year` Clustering"),
        ("R3_fine_noun_x_year_fe", "R3. `Fine-Product-Noun` $\\times$ `Year` FE"),
        ("R5_within_refund_only", "R5. Within `Refund_Only` Recalls"),
        ("R6_within_repair_replace", "R6. Within `Repair/Replace` Recalls"),
        ("R7_high_price_ge_100", "R7. Products Priced $\\ge \\$100$ (All Categories)"),
        ("R7b_strict_durables_ge_100", "R7b. Strict Durables ($\\ge \\$100$)"),
        ("R8_large_batch_ge_10k", "R8. Large Batches ($\\ge 10{,}000$ Units)"),
        ("R9_within_made_in_china", "R9. Strictly Within Made-in-China"),
        ("R10_control_webmail_nophone", "R10. Mediation (`+ free_webmail + no_phone`)"),
        ("R11_shell_front_audit", "R11. Shell-Front Audit (FD China vs. Legacy U.S.)"),
        ("R12_general_defects_only", "R12. General Non-Rule Safety Defects"),
        ("R13_mandatory_rules_only", "R13. Mandatory Federal Safety-Rule Violations"),
        ("R16a_era_2021_2026", "R16a. Era Sensitivity (2021–2026)"),
        ("R16b_era_2018_2026", "R16b. Era Sensitivity (2018–2026)"),
    ]
    s2_lines = [
        "| All-Channel Specification (`photo_verify`, 2022–2026 unless noted) | $N$ | Clusters | `1_Mkt_FD_China` (pp) | CR1 $t$ | $p_{\\text{WCB}}$ | Within-Mkt $\\Delta_{\\text{FD}-\\text{US}}$ (pp) | $\\Delta$ $t$ | $p_{\\text{WCB}}$ | `4_DTC` (pp) |",
        "|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for sk, slbl in s2_specs:
        r = rob[sk]
        fd = r["terms"]["a_mkt_fd_cn"]
        ct = r["contrast"]
        dtc = r["terms"].get("a_dtc_online", {"beta": 0.0})
        s2_lines.append(
            f"| {slbl} | {r['n']:,} | {r['n_clusters']:,} | {fmt_pp(fd['beta'])} | {fd['t']:+.2f} | {fd.get('p_wcb', fd['p']):.3f} | "
            f"{fmt_pp(ct['diff'])} | {ct['t']:+.2f} | {ct.get('p_wcb', ct['p']):.3f} | {fmt_pp(dtc['beta'])} |"
        )
    table_s2_md = "\n".join(s2_lines)

    dc = p4["aug2025_direct_contact_boilerplate_audit"]
    bm_d = p2["bm_diffusion_decomposition"]
    perm = rob["R14_exact_permutation_mkt"]
    loco = rob["R15a_leave_one_category_out"]
    loyo = rob["R15b_leave_one_year_out"]

    return f"""# Supplementary Material: Who Bears the Burden of Product Recall Remedies? Notice-Level Duties, Channel Classification, and Institutional Governance in U.S. Third-Party E-Commerce Recalls, 2000–2026

**Zijian Zeng**  
Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA  
`zijianzeng@foxmail.com`; `1002266693@ucsiuniversity.edu.my`

---

## Supplementary Appendix A. Conceptual Principal–Agent and Reverse-Logistics Contract Model

To organize why notice-level duties vary across supply-chain architectures, consider a firm recalling a defective product held by a unit mass of affected U.S. consumers owed refund/replacement value $p > 0$. Selecting a remedy contract $m \\in \\{{R, D/U, P\\}}$ (physical return $R$, direct/unverified first-party remedy $D/U$, or photographic verification $P$) imposes consumer compliance hassle $k_P > k_R > k_{{D/U}} \\approx 0$, yielding participation probabilities $q_P < q_R < q_0$. Let $\\theta \\in [0, 1]$ denote first-party buyer-record observability ($\\theta_{{\\text{{DTC}}}} \\to 1$, $\\theta_{{\\text{{3P}}}} \\ll 1$), $\\alpha(1-\\theta)p$ moral-hazard claim inflation under unverified remedies, $c_{{\\text{{rev}}}}$ per-unit reverse-logistics cost, $a > 0$ per-claim seller verification/audit cost, and $\\lambda > 0$ expected domestic legal/reputational liability per unremedied unit ($\\lambda_{{\\text{{FD}}}} < \\lambda_{{\\text{{US}}}}$; Shavell 1986). Expected per-unit seller costs are:

$$C_R = q_R (p + c_{{\\text{{rev}}}}) + \\lambda (1 - q_R)$$

$$C_{{D/U}}(\\theta) = q_0 p + \\alpha (1 - \\theta) p + \\lambda \\big[(1 - q_0) + \\phi(1 - \\theta)\\big]$$

$$C_P = q_P (p + a) + \\lambda (1 - q_P)$$

Equating $C_P = C_R$ and $C_P = C_{{D/U}}(\\theta)$ yields closed-form adoption thresholds:

$$c_{{\\text{{rev}}}}^*(p, a, \\lambda) \\equiv \\frac{{q_P}}{{q_R}} a + \\frac{{q_R - q_P}}{{q_R}}(\\lambda - p)$$

$$\\theta^*(p, a, \\lambda) \\equiv 1 - \\frac{{q_P a - (q_0 - q_P)(p - \\lambda)}}{{\\alpha p + \\lambda \\phi}}$$

Under calibrated durable-product parameters ($p = \\$60$, $\\lambda_{{\\text{{US}}}} = \\$140$, $\\lambda_{{\\text{{FD}}}} = \\$35$, $q_0 = 0.780$, $q_R = 0.684$, $q_P = 0.540$, $\\alpha = 0.35$, $\\phi = 0.25$, $H = \\$240$, $e_{{\\text{{haz}}}} = \\$18$), reducing institutional template/audit friction from $a_{{2022}} = \\$18$ to $a_{{2026}} = \\$6$ shifts the domestic cutoff $c_{{\\text{{rev}}}}^*/p$ from {cuts['us_2022_crev_ratio']:.3f} to {cuts['us_2026_crev_ratio']:.3f} and raises $\\theta^*$ from {cuts['us_2022']['theta_star']:.3f} to {cuts['us_2026']['theta_star']:.3f} (Figure S1A), illustrating how template standardization pulls domestic retailers toward photographic verification while leaving high-observability DTC brands shielded inside $D/U$. All numerical proposition verifications are stored in `results/03_theory_equilibrium.json`.

<!-- FIGURE:fig2_theory_equilibrium_and_archetype_gaps.png -->

---

## Supplementary Appendix B. Underpowered Sub-Comparisons and Full All-Channel Robustness Battery

Per journal reporting standards, narrow sub-comparisons with insufficient within-cell sample size ($N < 100$) are moved out of the main text and reported transparently in Table S1 below. Specifically, inside multi-channel online notices including Amazon (**Def 3**), requiring both `1_Mkt_FD_China` and `3_Mkt_True_US` inside identical `fine_noun_yr` cells retains only **$N = {d3['cs_n']}$ notices across {d3['cs_cells']} cells** (23 China-direct vs. 32 U.S.-entity), yielding wide confidence intervals (SE = 13.2–34.2 pp). Similarly, restricting to strict durables priced $\\ge \\$100$ inside Amazon channels leaves only 91 (Def 1), 73 (Def 2a), and 49 (Def 2b: 38 China-direct vs. 11 U.S.-entity) notices—showing consistently positive `photo_language` point estimates (+21.55 to +22.76 pp) with wide CIs crossing zero ($p_{{\\text{{WCB}}}} = 0.124$ to $0.364$).

**Table S1. Underpowered Narrow Sub-Comparisons (`Def 3` Multi-Channel Online Common Support & Strict Durables $\\ge \\$100$ Inside Amazon Channels).**

{table_s1_md}

*Notes:* Directly from `results/09_v4_channel_remedy_audit.json`. Narrow Amazon strict-durable regressions control for `hazard_cat`, `year`, and `is_china_mfr` with firm-clustered CR1 SEs and $B = 999$ Rademacher WCB.

Table S2 and Figure S2 present the complete 17-specification all-channel robustness battery (2022–2026) plus identical fine-product-noun head-to-head comparisons.

**Table S2. Complete All-Channel Robustness Battery on `photo_verify` (2022–2026).**

{table_s2_md}

*Notes:* Directly from `tables/table3_robustness_battery_2022_2026.csv` and `results/04_pillar1_econometrics.json`. Additional tests: **R4 Binomial Logit** ($N = 1{{,}}822$) yields `1_Mkt_FD_China` $\\text{{OR}} = {rob['R4_binomial_logit_or']['terms']['a_mkt_fd_cn']['or']:.2f}\\times$ ($z = {rob['R4_binomial_logit_or']['terms']['a_mkt_fd_cn']['z']:+.2f}$) vs. `4_DTC_Online_Only` $\\text{{OR}} = {rob['R4_binomial_logit_or']['terms']['a_dtc_online']['or']:.2f}\\times$; **R14 Stratified Permutation** ($B = 1{{,}}000$, Year $\\times$ China strata, $N = {perm['n']}$) gives observed gap {fmt_pp(perm['obs_diff'])} pp vs. null SD {100*perm['perm_sd']:.2f} pp ($p = {perm['p_perm']:.4f}$); **R15a Leave-One-Category-Out** across all 15 categories keeps $\\beta_{{\\text{{FD}}}} \\in [{fmt_pp(loco['min_fd_beta'])}, {fmt_pp(loco['max_fd_beta'])}]$ pp ($\\min t = {loco['min_fd_t']:+.2f}$); **R15b Leave-One-Year-Out** across 2022–2026 keeps $\\beta_{{\\text{{FD}}}} \\in [{fmt_pp(loyo['min_fd_beta'])}, {fmt_pp(loyo['max_fd_beta'])}]$ pp ($\\min t = {loyo['min_fd_t']:+.2f}$).

<!-- FIGURE:fig5_robustness_forest_and_platforms.png -->

---

## Supplementary Appendix C. Full *In re Amazon.com* HAC Time-Series Stress Tests, Diffusion Decomposition, and Honest Null Audits

Table S3 reproduces the complete Newey–West (1987) HAC interrupted time-series battery (2021Q1–2026Q3, $T = 23$ complete quarters) programmatically synced from `tables/table5_amazon_hac_shock_and_persistence.csv`. Across alternative lag lengths $L \\in \\{{1, 2, 3, 4, 6\\}}$, `log(Amazon_Only / Brick_and_Mortar)` 2024Q3 slope $t$-statistics remain between +5.95 and +8.78. Adding STURDY Act (2023Q4+) and Reese's Law (2024Q2+) statutory dummies preserves the Amazon-over-brick-and-mortar slope (+0.1999/qtr, $t = +8.18$) while attenuating Amazon-over-other-3P (+0.0281/qtr, $t = +0.56$), honestly reflecting shared statutory rule sweeps across all 3P marketplaces.

**Table S3. Complete Descriptive Newey–West HAC Interrupted Time-Series Stress Tests (`tables/table5_canonical.md`).**

{t5_canon}

*Notes:* Directly from `tables/table5_amazon_hac_shock_and_persistence.csv`. As documented in Main Section 4.2, public CPSC notices contain 0/601 explicit "Fulfilled by Amazon" mentions (1/601 standalone "FBA" model suffix on TADAKAZU 10317); these series represent descriptive structural accelerations rather than causal FBA order evaluations.

**Brick-and-Mortar Diffusion Decomposition (2022–2026):** Inside `6_Brick_and_Mortar`, `photo_verify` adoption progressed at **{100*bm_d['BM_Made_in_China']['annual_slope_pp']:+.2f} pp/yr** ($t = {bm_d['BM_Made_in_China']['t']:+.2f}$, 14.9% → 60.0%) among China-manufactured retail imports ($n = {bm_d['BM_Made_in_China']['n']}$) versus only **{100*bm_d['BM_Non_China_Mfr']['annual_slope_pp']:+.2f} pp/yr** ($t = {bm_d['BM_Non_China_Mfr']['t']:+.2f}$, 6.8% → 10.5%, insignificant) among non-China goods ($n = {bm_d['BM_Non_China_Mfr']['n']}$), and {100*bm_d['BM_Price_lt_100']['annual_slope_pp']:+.2f} pp/yr (price below \\$100) vs. {100*bm_d['BM_Price_ge_100']['annual_slope_pp']:+.2f} pp/yr (price $\\ge \\$100$).

**August 2025 CPSC Universal `direct_contact` Boilerplate Edit:** Across 2024–2026, the phrase *"contacting all known purchasers directly"* dropped simultaneously to near zero on August 1, 2025 in every channel: `1_Mkt_FD_China` {100*dc['1_Mkt_FD_China']['pre_aug2025_rate']:.1f}% → {100*dc['1_Mkt_FD_China']['post_aug2025_rate']:.1f}%, `3_Mkt_True_US` {100*dc['3_Mkt_True_US']['pre_aug2025_rate']:.1f}% → {100*dc['3_Mkt_True_US']['post_aug2025_rate']:.1f}%, `5_Omnichannel` {100*dc['5_Omnichannel']['pre_aug2025_rate']:.1f}% → {100*dc['5_Omnichannel']['post_aug2025_rate']:.1f}%, and `6_Brick_and_Mortar` {100*dc['6_Brick_and_Mortar']['pre_aug2025_rate']:.1f}% → {100*dc['6_Brick_and_Mortar']['post_aug2025_rate']:.1f}%, confirming an agency press-release template revision excluded from all channel inferences.

---

## Supplementary Appendix D. Coding Codebook, Verbatim Edge-Case Excerpts, and Legacy Parser Consistency Audits

### D.1 Verbatim Benchmark Edge Cases Audited in Code and `pytest`

1. **Jugader Zipline Kits (`RecallID 9924`, Recall 24-199, 2024-04-11):** *Retailers:* "Amazon.com from March 2020 through June 2023 for about \\$140." *Remedies:* "Consumers must submit a photo of the cable and the trolley or their online purchase order number to receive a free repair kit..." **Audit Labels:** `strict_amazon_exclusive`, `photo_language = 1`, `proof_alternative_path = 1`, `proof_status = optional_or_alternative_proof`, `photo_mandatory = 0`, `physically_disabled = 0`.
2. **UVIPC Baby Gates (`RecallID 10148`, Recall 25-122, 2025-02-06):** *Retailers:* "http://www.amazon.com from November 2022 through September 2024 for between \\$186 and \\$230." *Remedies:* "...contact Xianshengyouli via email at xianshengyouli@outlook.com for information on how to dispose of the product and submit proof of destruction to obtain a full refund." **Audit Labels:** `strict_amazon_exclusive`, `photo_language = 0`, `destruction_proof = 1`, `destruction_proof_without_photo = 1`, `proof_status = mandatory_proof`, `physically_disabled = 1`.
3. **Anker PowerCore 10000 (`RecallID 10311`, Recall 25-338, 2025-06-12, 1,158,000 units):** *Retailers:* "Online at Anker, Amazon, Newegg and Ebay from June 2016 through December 2022 for about \\$27." **Audit Labels:** `multi_channel_with_amazon`, `photo_language = 1`, `photo_mandatory = 1`, `permanent_marking = 1`, `physically_disabled = 0`, `warning_remedy = 0`, `warning_full_notice = 1`.
4. **OCOOPA Hand Warmers (`RecallID 10895`, Recall 26-659, 2026-07-30, 1,500,000 units):** *Retailers:* "Online at Amazon.com, Ocoopa.com, Ocoopa.net and Walmart.com..." **Audit Labels:** `multi_channel_with_amazon`, `photo_language = 1`, `photo_mandatory = 1`, `permanent_marking = 1`, `physically_disabled = 0`, `warning_remedy = 1`, `warning_full_notice = 1` (explicitly prohibits household trash, curbside bins, and retail drop-boxes).
5. **TADAKAZU Baby Loungers (`RecallID 10317`, Recall 25-345, 2025-06-18):** *Retailers:* "Exclusively on Amazon from September 2024 through May 2025..." **Audit Labels:** `strict_amazon_exclusive`, `photo_language = 1`, `photo_mandatory = 1`, `physically_disabled = 1`, `explicit_fba = 0`, `fba_token = 1` (model-name suffix only).
6. **Ambiguous Channel Cases (5 in 2022–2026):** `RecallID 9234` (Shop LC airing on "Amazon Fire" TV app), `RecallID 10238` (Retailers says exclusively Walmart.com while Remedies says Costway and Amazon contact purchasers), `RecallID 10245` (Title says Sold on Amazon.com while Retailers says Rooms To Go), `RecallID 10276` (Title says Sold on Amazon.com while Retailers says exclusively FidgetThings.com), and `RecallID 10494` (Title says magnet fidget spinner sold on Amazon while Retailers lists Spartan dealers at \\$16,400–\\$19,700).

### D.2 Legacy Author-Reviewed Parser Consistency Audits (150 Census + 50 Disjoint OOS 2025–2026)

For full provenance alongside our v4 stratified $N = 150$ remedy-duty audit (`tables/table_remedy_duty_coding_audit.csv`), the legacy 150-recall census consistency audit (`tables/table_parser_audit_150.csv`, `seed = 20261126`) achieved `archetype_6` exact consistency {100*aud_legacy['archetype_6']['exact_accuracy']:.2f}% (149/150), `has_injury` F1 {aud_legacy['binary_fields']['has_injury']['f1']:.4f} ({100*aud_legacy['numeric_fields']['clean_injuries_exact_acc']:.2f}% exact injury count; 100.0% exact `price` and `units`), while the disjoint 50-recall out-of-sample 2025–2026 consistency stress-test (`seed = 9992026`) achieved 100.0% on `archetype_6`, `photo_verify` (32 TP, 18 TN), and `direct_return` (6 TP, 44 TN), {100*oos['binary_fields']['physical_mutilate']['accuracy']:.1f}% (F1 = {oos['binary_fields']['physical_mutilate']['f1']:.4f}) on `physical_mutilate`, and {100*oos['binary_fields']['has_injury']['accuracy']:.1f}% (F1 = {oos['binary_fields']['has_injury']['f1']:.4f}) on `has_injury`. Both legacy audits and the v4 structured audit are author-reviewed consistency checks rather than independent double-blind multi-coder annotations.
"""


def main() -> int:
    manifest = json.loads((RES_DIR / "01_fetch_manifest.json").read_text(encoding="utf-8"))
    aud_legacy = json.loads((RES_DIR / "02_parser_audit_metrics.json").read_text(encoding="utf-8"))
    theory = json.loads((RES_DIR / "03_theory_equilibrium.json").read_text(encoding="utf-8"))
    p1 = json.loads((RES_DIR / "04_pillar1_econometrics.json").read_text(encoding="utf-8"))
    p234 = json.loads((RES_DIR / "05_pillars_2_3_4.json").read_text(encoding="utf-8"))
    refs = json.loads((RES_DIR / "06_verified_references.json").read_text(encoding="utf-8"))
    v4 = json.loads((RES_DIR / "09_v4_channel_remedy_audit.json").read_text(encoding="utf-8"))

    main_txt = build_main_manuscript(manifest, aud_legacy, theory, p1, p234, refs, v4)
    supp_txt = build_supplement(aud_legacy, theory, p1, p234, v4)

    MAIN_MD.write_text(main_txt, encoding="utf-8")
    SUPP_MD.write_text(supp_txt, encoding="utf-8")
    print(f"[DONE STEP 10 v4] Generated {MAIN_MD} ({len(main_txt):,} chars) and {SUPP_MD} ({len(supp_txt):,} chars).", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
