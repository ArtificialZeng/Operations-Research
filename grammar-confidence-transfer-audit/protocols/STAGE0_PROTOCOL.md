# Stage-0 Locked Protocol: Offline Single-Turn Function-Call Confidence Transfer Across Syntax-Only JSON Grammars (`grammar_confidence_transfer_20261124`)

**Status:** LOCKED PRE-LAUNCH — written and hashed **before** running any LLM inference on the BFCL Stage-0 pilot split.  
**Core Research Question:** Does a **syntax-only JSON grammar** (compact vs. optional whitespace, expressing the exact same parsed calls) change the **confidence ordering** of correct versus incorrect function calls and cause an **abstention policy to fail when transferred between grammars**?

---

## 1. Primary Competition & Explicit Novelty Boundaries

We consult and explicitly position against five primary 2026 references and **make zero novelty claim** for grammar ablation, feasible mass, or post-mask probability identities:

1. **Ye et al. (TMLR 2026, `arXiv:2604.22985v2`) — *Uncertainty Quantification for LLM Function-Calling*:** Mandatory comparator **`G-NLL_SMT`** (Greedy Negative Log-Likelihood restricted to Semantically Meaningful Tokens: function name + argument keys + argument values). We evaluate `G-NLL_SMT` (both unmasked and post-mask, mean and sum, plus value-only SMT sensitivity subset) alongside full-sequence `G-NLL`.
2. **Parvatikar (UncertaiNLP 2026, `2026.uncertainlp-main.26`) — *Constrained Decoding Can Reverse Which Inputs Look Uncertain*:** Established first-token/masking entropy reversal under constrained decoding (not claimed as novelty here; we log `h_pre_first`, `h_post_first`, and mean entropy as reference diagnostics).
3. **Reddy et al. (`arXiv:2603.03305`) — *The Hidden Cost of Structured Generation in LLMs: Draft-Conditioned Constrained Decoding*:** Formalized feasible mass $\alpha_t$ (not claimed as novelty here; we log exact $-\log Z_t$, mean/min retained mass as reference diagnostics).
4. **`macamiri/validbutwrong` (commit `e6dd464a...`) — *Constraint Tax in Open-Weight LLMs*:** Analyzed BFCL grammar-vs-prompt validity vs. accuracy / tool suppression (not claimed as novelty here; we report AST/JSON validity vs. semantic correctness separately across unconstrained and both grammar arms).
5. **Multi-Turn Tool-Calling Calibration (`arXiv:2609.00949`):** Action-class calibration diagnostics in multi-turn BFCL (out of scope for this benign single-turn offline study, cited for calibration context).

**Algebraic Identity (Not a Novel Theorem):** For any unmasked logit vector $z_t$ and grammar mask $M_t \ni y_t$ with retained feasible mass $Z_t = \sum_{v \in M_t} p_{\text{pre}}(v \mid y_{<t})$, $\text{pre-NLL}_t = \text{post-NLL}_t - \log Z_t$ holds identically.

---

## 2. Dataset Provenance, Safety Hygiene & Tool-Family-Disjoint Split

- **Upstream Dataset:** Official BFCL v4 (`ShishirPatil/gorilla`, commit `6ea57973c7a6097fd7c5915698c54c17c5b1b6c8`, **Apache-2.0**), `BFCL_v4_simple_python.json` (`400` raw) and `BFCL_v4_multiple.json` (`200` raw) + `possible_answer/*`.
- **Safety & Benign Read-Only Hygiene:** Deterministic regex filter drops `84` examples containing mutating/destructive/financial/messaging/auth/legal/medical/sensitive verbs (`516` benign neutral read-only examples kept). Evaluation is **100% offline, inert AST checking** via official unmodified `bfcl_eval/eval_checker/ast_eval/ast_checker.py` (`Language.PYTHON`, `underscore_to_dot=False`) — **zero** actual function execution, **zero** credentials, **zero** production agents, **zero** paid APIs.
- **Tool-Family-Disjoint Partition (`BFCL_PILOT_SPLIT_RECEIPT.json`, `seed = 20261124`):** Connected-component union-find over all exact function names and normalized domain roots splits the `516` benign examples into:
  - **`pilot_dev` (`bfcl_stage0_pilot_dataset.json`, `N = 100`):** `60` `simple_python` + `40` `multiple`, spanning `70` connected tool-family clusters (`113` distinct domain roots).
  - **`future_blind_test` (`bfcl_future_blind_test_ids_sealed.json`, `N = 416`):** `74` disjoint tool-family clusters (`243` distinct domain roots), **completely sealed and uninspected** in Stage-0.
  - Hard zero-leakage assertions verified: `zero_id_overlap = True`, `zero_exact_function_name_overlap = True`, `zero_tool_family_root_overlap = True`.

---

## 3. Model, Runtime & Syntax-Only Two-Grammar Design

- **Single Local Small Open Model:** `Qwen/Qwen2.5-1.5B-Instruct` (**Apache-2.0**), deterministic greedy decoding (`do_sample=False`, `max_new_tokens=192`), exact HF commit hash, dtype, device, and runtime versions/licenses (`xgrammar 0.2.9` Apache-2.0, `transformers 5.24.0` Apache-2.0, `torch` BSD-3-Clause) persisted in output metadata.
- **Two Syntax-Only JSON Call EBNF Grammars (`grammar_utils.py`):**
  - **`G_compact`:** Strict compact JSON `{"name":"<str>","arguments":{...}}` with zero whitespace outside JSON string literals.
  - **`G_optws`:** Identical JSON call syntax allowing standard RFC-8259 optional whitespace `ws ::= [ \t\n\r]*` around all structural punctuation.
  - **Invariants:** Identical parsed JSON call space, identical prompt (`build_messages`), **zero access** to expected arguments, tool schemas, tool IDs, or ground-truth outputs, and exact inclusion $L(G_{\text{compact}}) \subset L(G_{\text{optws}})$.

---

## 4. Pre-Launch Fixture Gate & SHA-256 Manifest

- **Fixture Gate (`STAGE0_ALGEBRA_AND_GRAMMAR_FIXTURE_RECEIPT.json`):** `all_fixtures_passed = True`.
  - Exact float64 algebraic identity residual on shared fixed path: `max_abs_err = 3.55e-15 < 1e-12` for both `G_compact` and `G_optws`.
  - Strict mask subset invariant $M_t(G_{\text{compact}}) \subseteq M_t(G_{\text{optws}})$ on all steps, with strictly larger retained mass for `G_optws` on `21/23` steps (`max_logZ_gap = 10.5528`).
  - Consistent Ye et al. SMT token-span extraction verified across compact and spaced forms; official BFCL inert `ast_checker` passed `7/7` unit tests.

| File | Bytes | SHA-256 |
|---|---:|---|
| `build_bfcl_pilot_split.py` | 11,360 | `24256c697b7ad68c777aeb82a2ad39039367432198e0c793957f908546877f90` |
| `BFCL_PILOT_SPLIT_RECEIPT.json` | 12,185 | `3d6e0be091e3f6a85c7985dcb29b364268df1e6d039f86895daf309e13943f57` |
| `bfcl_stage0_pilot_dataset.json` | 209,128 | `191e8e8c8c9c00f0f7dacd0a98b6f592b02e878e444da0016e99f1e31c1cd446` |
| `bfcl_future_blind_test_ids_sealed.json` | 10,249 | `64268a3c286eaacd45f51a470cb619ff3027019e27f7f5632b7d1f7a56139e0a` |
| `grammar_utils.py` | 18,204 | `d063e5e347bf2928f1c6f22becafd67611f711842960276e1399359dab966423` |
| `verify_grammar_mask_algebra.py` | 10,899 | `e48745d4b7217ca3bce3d209d14d79bea15e1ae08a102dbc0d92d921baea0dd8` |
| `STAGE0_ALGEBRA_AND_GRAMMAR_FIXTURE_RECEIPT.json` | 1,981 | `e4945f6a42bc2959783506f908e32bdb4d6e66b827b8c507459ab84d60ca34ef` |
| `stage0_grammar_confidence_pilot.py` | 33,153 | `4f366ffb06617f2fcb2f36661c6c9b503096a47dd709450603faf095da9a7cb9` |

---

## 5. Prespecified Stage-0 Pilot Evaluations & Power Rules

1. **Fixed-Path Paired Scoring (Same Forward Pass):** For every `G_compact` generated path accepted and terminated by both `G_compact` and `G_optws`, score under **one shared unmasked forward pass** using exact float64 masks for both grammars and identical token-subset indices (`all`, `SMT_ye26`, `SMT_val`, `syntax`).
2. **All-Generated-Cases Evaluation (`N = 100`, Zero Cherry-Picking):** Separately generate and evaluate **all `100` pilot examples** under **(a) Unconstrained greedy**, **(b) `G_compact` constrained greedy**, and **(c) `G_optws` constrained greedy** — including all changed paths, parse failures, and truncations (non-parseable SMT assigned maximum uncertainty so all `100` examples remain in the denominator).
3. **Metrics & Pilot Power Discipline:** Report JSON/schema validity vs. BFCL AST correctness, AUROC, AURC, selective risk at `80%` coverage, Spearman $\rho$ / Kendall $\tau$ rank correlation, cross-grammar threshold transfer (`G_compact -> G_optws` and `G_optws -> G_compact` at `80%` source coverage), cluster bootstrap by `tool_family_cluster` (`2,000` resamples), and explicit power / underpowered-pilot assessment.
4. **Gate to Full Held-Out Transfer Test:** **Do NOT touch `future_blind_test` (`N = 416`) or train/select a second model** in Stage-0; proceed to the blind held-out transfer test + second model only after review of Stage-0 pilot results.
