# Stage-0b Locked Amendment Protocol — Isolating the Stage-0 `95 -> 2` `G_compact` Effect

**Date Locked:** 2026-11-24 (BEFORE Stage-0b GPU execution)  
**Parent Sealed Study:** [`STAGE0_PROTOCOL.md`](../protocols/STAGE0_PROTOCOL.md) (`9c4573d847d18a683c22440390d6e9b11d44691d45321e6ede5217894ec065b6`)  
**Status:** Exploratory bounded mechanism follow-up on 24 items of the existing 100-item Stage-0 pilot split (`bfcl_future_blind_test_ids_sealed.json`, `N = 416`, remains **100% sealed and untouched**).

---

## 1. Motivation & Bounded Question

In the sealed Stage-0 pilot (`N = 100`, `Qwen/Qwen2.5-1.5B-Instruct`, `PID = 42516`), `G_optws` and `Unconstrained` achieved `95/100` BFCL inert AST accuracy (`100/100` JSON/schema valid), whereas syntax-only `G_compact` dropped to `2/100` (`100/100` JSON/schema valid; `98/100` errors all `simple_function_checker:wrong_func_name`).

Because Stage-0's prompt included a **spaced JSON example** (`{"name": "<function_name>", "arguments": ...}`), two major alternative explanations must be isolated BEFORE opening the sealed `N = 416` blind test or launching a multi-model confirmation:
1. **Prompt-vs-grammar whitespace conflict:** Does the `95 -> 2` collapse vanish once the spaced JSON example is removed (`Prompt_Neutral`, prose-only key description) or aligned to compact syntax (`Prompt_Compact`), OR does BPE boundary masking (`":` -> 269 `"`-prefixed tokens) cause collapse even under neutral or compact-matched prompts?
2. **Free-string vs. offered-menu enum function-name constraint:** Under `Prompt_Neutral`, if both grammars constrain `"name"` to the **exact same per-item canonical sorted enum of all offered functions** from `item["function"]` (never reading `ground_truth` or expected arguments, differing strictly by optional whitespace), does `G_compact_menu` recover accuracy or still degrade relative to `G_optws_menu` (especially on `multiple` where menu size is `2–3`)?

---

## 2. Outcome-Independent 24-Item Subset

- **Selection Rule:** Deterministic sort of sealed [`bfcl_stage0_pilot_dataset.json`](../data/bfcl_stage0_pilot_dataset.json) (`191e8e8c...`) strictly by `sha256("stage0b_20261124:" + id)` **without reading Stage-0 outcomes**.
- **Sample Size:** First `12` `simple_python` (offered menu size `= 1`) + first `12` `multiple` (offered menu size `= 2–3`) = **`24` items total**.
- **Persisted Receipt:** [`STAGE0B_SUBSET_24_RECEIPT.json`](../receipts/STAGE0B_SUBSET_24_RECEIPT.json) (`65bcba4a28ee39bf3ff7f4173e773c110c076a136f663cda7dcde57f928cbf46`).

---

## 3. Experimental Arms (Strictly Bounded; Zero Extra Grammar Arms)

All arms use identical `Qwen/Qwen2.5-1.5B-Instruct` verified local snapshot (`989aa7980e4cf806f80c7fef2b1adb7bc71aa306`, `bfloat16`, RTX 5060 GPU, `HF_HUB_OFFLINE=1`, `local_files_only=True`), greedy decoding, `max_new_tokens = 192`, `xgrammar 0.2.9`, exact `float64` mask normalization, identical offered tool schemas and user questions, and **zero gold identifiers**:

1. **Reused Stage-0 Baseline (`Prompt_Spaced`, reused BYTE-FOR-BYTE from sealed `stage0_pilot_per_instance.jsonl`):**
   - `spaced__unconstrained_reused`
   - `spaced__G_optws_reused` (**Matched**: spaced example + optional-ws grammar)
   - `spaced__G_compact_reused` (**Confounded / Mismatched**: spaced example + no-ws grammar)
2. **Control (A1) — Format-Neutral Prompt (`Prompt_Neutral`: describes `"name"` and `"arguments"` keys in prose ONLY, zero JSON formatting examples):**
   - `neutral__G_optws` (**Format-Neutral**, global `EBNF_G_OPTWS`)
   - `neutral__G_compact` (**Format-Neutral**, global `EBNF_G_COMPACT`)
3. **Control (A2) — Compact-Example Prompt (`Prompt_Compact`: `{"name":"<function_name>","arguments":{<key>:<value>,...}}`):**
   - `compact__G_optws` (**Superset-Compatible**, global `EBNF_G_OPTWS`)
   - `compact__G_compact` (**Matched**, global `EBNF_G_COMPACT`)
4. **Control (B) — Per-Item Offered-Menu Enum Grammar under `Prompt_Neutral`:**
   - `neutral_menu__G_optws_menu` (canonical sorted union of `item["function"]` names, optional whitespace)
   - `neutral_menu__G_compact_menu` (exact same canonical sorted union, zero whitespace)

Total new GPU decodes: `6 arms × 24 items = 144` short greedy generations, plus 3 fixed-path shared-forward teacher-force sets and a read-only 8-step prefix-logit replay on 6 items (`3 simple_python + 3 multiple`) for `Prompt_Spaced`.

---

## 4. Pre-Launch Verification Gates (All PASSED Prior to Lock)

Verified in [`STAGE0B_FIXTURE_RECEIPT.json`](../receipts/STAGE0B_FIXTURE_RECEIPT.json) (`04ee945695311cc738406e5a769556b14ed0bbc7e8212b85ac86cdc36d456d65`):
- `neutral_prompt_has_no_json_format_example = True`
- `compact_prompt_has_compact_example = True`
- `menu_enum_independent_of_ground_truth = True` (replacing `ground_truth` produces bit-identical EBNF strings)
- `all_offered_names_accepted_by_both_menu_grammars = True`
- `spaced_json_rejected_by_compact_menu_accepted_by_optws_menu = True` (whitespace-only difference, identical parsed AST space)
- `unoffered_name_rejected_by_both_menu_grammars = True`
- `all_24_item_menu_grammars_compiled_cleanly = True`
- Exact float64 algebra identity `|pre_nll - (post_nll - log_retained_mass)| <= 3.55e-15 < 1e-12`

---

## 5. Prespecified Reporting & Statistical Guardrails

1. **Zero dropped failures:** Every raw string, stop reason, JSON/schema validity flag, and inert BFCL AST verdict is persisted in `stage0b_outputs/stage0b_per_instance.jsonl`.
2. **Exact mutually exclusive 5-way partition (`sum == N`):**
   - `ast_correct`
   - `unknown_func_not_in_menu` (valid JSON+envelope, tool name NOT in `item["function"]`)
   - `offered_but_wrong_func` (tool name in `item["function"]`, NOT in `ground_truth`)
   - `right_func_wrong_args` (tool name matches `ground_truth`, BFCL inert AST failed on arguments)
   - `parse_or_envelope_fail`
3. **Category stratification:** Report BOTH overall (`N = 24`) AND split `simple_python` (`n = 12`, menu size `1`) vs. `multiple` (`n = 12`, menu size `2–3`).
4. **Matched vs. confounded prompt cell table:** Report all 8 grammar cells grouped by prompt-grammar alignment.
5. **Prefix-logit timing & inspection of the first tool-name token:** Record steps `0..7` GPU forward time (`ms`), mask time (`ms`), `n_allowed_tokens`, `retained_mass`, and top-5 unmasked vs. post-mask probabilities across all 4 prompt/grammar families, pinpointing the exact step where the first character of `"name"` enters the token stream.
6. **Strict separation & small-minority instability flag:**
   - Keep `fixed_path_paired_shared_forward_SEPARATE` strictly separate from `free_generation_all_24`.
   - Flag ANY conditional confidence metric (`AUROC`, `AURC`, `risk@80%`) with `conditional_metrics_unstable = True` whenever `min(n_correct, n_error) <= 5`.
7. **Hard exclusions:** No fitting/retuning, no opening `bfcl_future_blind_test_ids_sealed.json`, no modifying any Stage-0 file (all Stage-0 SHA-256 hashes asserted before AND after run), no external publication, papers, or media.

---

## 6. Locked Pre-Launch SHA-256 Manifest

| File | SHA-256 |
|---|---|
| `bfcl_stage0_pilot_dataset.json` (sealed Stage-0) | `191e8e8c8c9c00f0f7dacd0a98b6f592b02e878e444da0016e99f1e31c1cd446` |
| `bfcl_future_blind_test_ids_sealed.json` (sealed, UNTOUCHED) | `64268a3c286eaacd45f51a470cb619ff3027019e27f7f5632b7d1f7a56139e0a` |
| `grammar_utils.py` (sealed Stage-0) | `d063e5e347bf2928f1c6f22becafd67611f711842960276e1399359dab966423` |
| `STAGE0_PROTOCOL.md` (sealed Stage-0) | `9c4573d847d18a683c22440390d6e9b11d44691d45321e6ede5217894ec065b6` |
| `MODEL_TRANSPORT_RECEIPT.json` (sealed Stage-0) | `74cdd02fae04f8328eef6a323f3e80e2f02d52a2b0f8d200c2674b629071c8ad` |
| `stage0_pilot_outputs/stage0_pilot_per_instance.jsonl` (sealed Stage-0) | `06c90359910592d3d43916c50479abadc15a5cac2d9600ada8b2b0e2566b6aa8` |
| `stage0_pilot_outputs/stage0_pilot_summary.json` (sealed Stage-0) | `a39963f0cf7d00a1ef4c2c0864708883a7f01072e364580c6e7fd3d4e7b8af6c` |
| `select_stage0b_subset_and_verify.py` (Stage-0b selector/fixture) | `0a0d9b95cedc580b8fdff00ac44277b6e0409c411dcc0dc4138a1fed168defa1` |
| `STAGE0B_SUBSET_24_RECEIPT.json` (Stage-0b 24 IDs) | `65bcba4a28ee39bf3ff7f4173e773c110c076a136f663cda7dcde57f928cbf46` |
| `STAGE0B_FIXTURE_RECEIPT.json` (Stage-0b fixture gate) | `04ee945695311cc738406e5a769556b14ed0bbc7e8212b85ac86cdc36d456d65` |
| `stage0b_mechanism_followup.py` (Stage-0b runner) | `9c866ba0f08080f57556ec92dc8fc0af6274a814a2a93ded2e55bfc3d57cbb1a` |
