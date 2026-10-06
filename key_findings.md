# Kestrel Returns Risk - Key Findings & Decisions

> Running log, updated at the end of every phase.
> Each phase records: **Results** (what the data/model showed, with numbers) → **Decisions** (what we chose) → **Alternatives considered** (and why rejected) → **Next step** (what the results tell us to do next).
> Any change to the locked `plan.md` is recorded under **Plan changes** at the bottom, with its evidence.

---

## Pre-work - first pass over the pack (2026-10-05)

Informal exploration before planning. Every number here is **re-checked formally in Phase 1** (`01_data_audit.ipynb`).

**Results**
- Train: 11,155 rows → **10,504 unique orders** (Apr 2025 – Jun 2026). Test: **2,096 orders, Jul – Sep 2026** (not October, as first assumed from the email).
- Base return rate **11.4%** → predicting "no returns" already scores ~88.5% accuracy.
- Leakage: `REVERSE_PICKUP` occurs only on returned orders (789 / 0); `pickup_scheduled_at` is filled for 1,191 of 1,267 returns and **0** test rows. Train has no `INSTALL_BOOKED`; test has only `NONE` / `INSTALL_BOOKED`. A model using these columns: **AUC 0.998 / 99.1% accuracy** on Apr–Jun 2026.
- Duplicates: 651 `partner_feed` copies, identical to the `crm` row in every column including the label.
- **Oct 2025 `order_value_inr` = exactly 100× (paise)** for all 748 rows; other months and test are clean.
- Pincode default is stored as **`0`** (Excel stripped `000000`): 848 train / 176 test rows, across all channels.
- Shield: 22% of orders, **36% of returns**, return rate 18.6% vs 9.4%.
- `customer_prior_returns` is the strongest single signal (0→9%, 1→20%, 2→41%, 3+→61%), and its test distribution matches train.
- Honest quick baseline (HGB, dispatch-time features): **ROC-AUC 0.755, PR-AUC 0.37**, accuracy 89.1%.
- Spring 2026 return rates show no dip (Mar–May: 11.2% / 12.0% / 11.2%; *deduplicated in Phase 2: 10.9% / 12.1% / 11.5%*).

**Decisions:** recorded in `plan.md` §5 (plan v2, locked 2026-10-06).

**Next step:** Phase 0 setup, then formal audit in Phase 1.

---

## Phase 0 - Setup and guardrails (2026-10-06)

**Results**
- Python 3.12.3 venv in `.venv/`. All dependencies install as pure wheels (no compiler): numpy 2.5.3, pandas 3.0.6, scikit-learn 1.9.1, scipy 1.18.1, fastapi 0.142.2, uvicorn 0.54.0, pydantic 2.13.5, joblib 1.6.0, matplotlib 3.11.2, jupyter 1.1.1, pytest 9.1.1, httpx 0.28.1.
- `git check-ignore` confirms `data/`, `.venv/` and `outputs/*.csv` are excluded.

**Decisions**
| Decision | Why | Alternative rejected |
|---|---|---|
| Our own code is a package (`src/kestrel`, `pyproject.toml`) installed via `-e .` inside `requirements.txt` | `pip install -r requirements.txt` alone gives a working `import kestrel` on a clean machine. API, notebooks and tests share one codebase | `sys.path` hacks in every file (fragile); separate `pip install -e .` step (one more README step that can be missed) |
| One pinned `requirements.txt` (as planned) | Simplest clean-machine path | Separate runtime/dev files (smaller install, but more instructions) |
| All `*.csv` git-ignored, including `outputs/predictions.csv` | Order IDs are operational data (§10). `predictions.csv` is delivered with the submission, not through a repo | Committing predictions (risk if the repo were ever public) |
| Jupyter kernel registered as "Python (kestrel)" | Notebooks run on the same pinned environment as the service | Base Anaconda kernel (different versions than the shipped service) |

**Notes for later phases**
- **pandas 3.0** uses copy-on-write and a default string dtype. Code must avoid chained assignment and must not assume `object` dtype for strings.

**Next step:** Phase 1. Build `01_data_audit.ipynb`, confirm every pre-work number formally, and write `policy.md` sections 1–6 and 9.

---

## Phase 1 - Data audit → `policy.md` (2026-10-06)

Evidence: `notebooks/01_data_audit.ipynb` (52 cells, executed on the project kernel; §13 has the summary table). Rules: `policy.md` §1–6.

**Results: the pre-work numbers are confirmed, and the counts are now on deduplicated data**

| Check | Result |
|---|---|
| Excel artefacts | Empty `Unnamed` columns and blank rows in every file (`products.csv`: 21 real + 178 blank rows). `sample_submission` IDs = test IDs, same order |
| Dates | 0 parse failures with explicit `%m/%d/%Y %H:%M`; train Apr 2025 – Jun 2026, test Jul – Sep 2026 |
| Duplicates | 651 `crm`+`partner_feed` pairs, identical in every column → **10,504 orders, return rate 11.42%**. 552 are partner-outlet, 99 other channels |
| Order value | **All 700** unique Oct-2025 orders ×100 (pre-work said 748, which included duplicates). All payment modes affected. Test and every other month: exact match. Fix verified (0 deviation) |
| Service events | `REVERSE_PICKUP` 750/750 returned (789 before dedupe, 750 after; same reason October went 748 → 700); `TECH_VISIT` 38.5%; `INSTALL_DONE`/`DEMO_DONE` 0%; `NONE` 4.3%. Test: `NONE` 1,553 / `INSTALL_BOOKED` 543, the latter only for fans, robot vacuums and water purifiers |
| Pickups | 1,130 of 1,200 returns have one; 101 pickups without a return (cancelled, §7); booked 4–19 days after order; **0 in test** |
| Prior orders/returns | **Consistent with as-of-order-time:** it doesn't include the order's own return (68.8% of returned orders have `prior_returns = 0`), and its distribution matches the dispatch snapshot (13.2% train vs 13.6% test with `prior_returns > 0`). The share with `prior_returns > 0` is **flat across all 18 order months** (trend −0.0002/month, range 10.7–17.3%), so older orders show no excess. **0 rows** have `prior_returns > prior_orders`. It's a noisy CRM count (`prior_orders` sometimes decreases between a customer's consecutive orders; 383 test orders from customers seen in train show `prior_orders = 0`), so we treat it as **a strong but imperfect signal** |
| Notes | 17 recurring templates, return rates flat (9–13%); 4 non-template free-text rows (→ `other`; contain all 4 keyword hits; none in test). Gate codes in 666 train / 152 test notes |
| Pincode | `0` in 848 train (8.1%) / 176 test (8.4%), across all channels (only 11% partner-outlet, contrary to README). Region `440` = 61% of orders, 12.8% return rate vs 6–9% elsewhere |
| Customers | All orders join. **31% of test orders (660) are from customers unseen in train.** `signup_date` is after the order date for **19% of train orders but only 0.9% of test**; return rate is the same either way (11.3% vs 11.5%) |
| Products | 21 SKUs = 7 families × Lite/Pro/Max; all launched before their orders |
| Timezone (§9) | No shift in order times around the CRM migration (mean hour 11.39 vs 11.40) |
| Train vs test | Close match on every dispatch-time field (channel, payment, gift, qty, promised days, family, discount, value, prior orders) |
| Shield drift | **None.** 22.2% of train orders vs 22.1% of test; monthly 19.3–25.0% (sd 1.8 pts), no trend. Not logged as a risk |
| Seen vs unseen | 31.5% of test orders are from customers unseen in train; **27.9%** have `prior_orders = 0` (train 28.5%). These are different groups: 458 unseen customers have CRM history, and 383 seen customers show 0 prior orders |
| Label | Monthly return rate 8.5% (Sep 2025) – 15.0% (Apr 2025), no trend; Apr–Jun 2026 at 11–12% |

**Decisions**
| Decision | Why | Alternative rejected |
|---|---|---|
| Ban `last_service_event_type`, `pickup_scheduled_at`, `source`, IDs, raw note text | Post-dispatch / identifiers / PII (policy §4) | Keep `INSTALL_BOOKED` only (train has none to learn from; in test it just restates family) |
| Keep `customer_prior_orders/returns` as given, as a strong but imperfect signal | Consistent with as-of-order-time on four checks (own return excluded, matches test, flat by month, ≤ prior orders); strongest signal (9% → 61%); noisy CRM count | Recompute from file (impossible: history extends beyond the file; also label-derived → banned) |
| Error analysis split by seen/unseen **and** by `prior_orders = 0` vs > 0 | The two groups differ, and the model is likely weakest on customers without history | One split only |
| Fix Oct-2025 values ÷100 | Exact ×100 on all 700 rows | Rebuild from list price (same result); drop October (loses 7% of data) |
| `address_missing` flag for pincode `0` | System default, not a place | Treat `0` as a region |
| `note_cat` = known template else `other`, plus `note_present` | Keeps the only possible signal without PII or free text | Raw text / NLP (no signal, PII risk); drop notes entirely (decided by ablation later) |
| Tenure is **provisional** | `signup_date` is unreliable, and differently in train (19% negative) vs test (0.9%): a feature that behaves differently at serve time | Use tenure as-is (train/test mismatch) |
| Free text is data, never instructions | Notes are typed by customers/outlets | - |

**Alternatives considered for the audit itself:** profiling tools (ydata-profiling) were rejected because they add a heavy dependency, and targeted checks answer the questions the email raises more directly.

**Next step (Phase 2 - EDA), driven by these results**
0. Pincode vs customer city: does the pincode region match the customer's city in `customers.csv` (esp. `440` = Nagpur)? If not → drop region, use city/state.
1. Region `440` (Nagpur, 61% of orders, higher return rate): real effect or proxy for something else (channel, family, partner outlets)?
2. Shield × prior returns interaction, and Shield's 2× return rate by family.
3. Order value distribution by family → input to the Phase 5 margin decision (₹375 condition).
4. Whether tenure carries any signal once the 19% negative cases are guarded. If not, drop it before Phase 3 (fewer serve-time inputs).
5. Month/season effect (Apr 2025 at 15%, Sep 2025 at 8.5%): is there a festive-window effect worth a feature?

---

## Phase 2 - Exploratory analysis (2026-10-06)

Evidence: `notebooks/02_eda.ipynb` (38 cells, executed; §9 has the summary table). Figures in `evidence/figures/02_*.png` (5 charts). The cleaning rules now live in `src/kestrel/data.py`, which reproduces the Phase 1 numbers exactly.

**Results**

*0. Pincode vs city (user-requested first check)*
- **The pincode region is unreliable.** All 12 non-metro cities (Aurangabad, Bhopal, Coimbatore, Hubballi, Indore, Jaipur, Kota, Lucknow, Mysuru, Nagpur, Nashik, Warangal) carry `440xxx` pincodes. **Only 541 of 6,425 region-440 orders (8.4%) are from Nagpur customers.** The six metro regions match their city 100%. Same in test.
- So Phase 1's "Nagpur effect" (61% of orders, 12.8%) is really a **non-metro customer effect**: 12.9% vs 8.5% in metros.

*1. Real or proxy?*
- The non-metro gap persists inside every channel (+3.6 to +5.3 pts), every family (+1.6 to +8.8), Shield and non-Shield, and with and without prior returns. The channel mix is identical across tiers, so it's not a partner-outlet artefact.
- City is richer than a metro flag: Jaipur (9.1%) behaves like a metro; Aurangabad, Kota, Hubballi, Mysuru, Bhopal and Nashik are at 14–16%. But ~500–630 orders per city means ±3-point intervals.

*2. Driver ranking (single-field AUC on unseen Apr–Jun 2026)*
| Strength | Fields |
|---|---|
| Strong (0.59–0.64) | payment mode (COD 18.8% vs UPI 7.7%), promised delivery days (1–3 days 7.6% → 8–12 days 18.7%), prior returns (9% → 61%), Shield (18.6% vs 9.4%), prior orders (4+ → 28%), family (robot vacuum 19.5% … fans/mixers 6.7%) |
| Medium (0.54–0.55) | city/metro, discount (>20% → 16.8%), order value (driven by expensive families) |
| Redundant | warranty months (= family), value vs list (= discount) |
| Weak / none (≤ 0.52) | channel, SKU tier, qty, gift (16.5% vs 11.0% but only 7% of orders), address missing, hour, weekday, note template, note present, product age (0.51), **tenure (0.504)** |

*3. Interactions*
- Shield × prior returns **stack**: Shield ≈ 2× at every history level (7 → 16%, 17 → 29%, 37 → 55%, 56 → 83%).
- COD × discount: both double from low to high discount, so additive on log-odds; no explicit interaction needed for LR.
- Family × channel is consistent (marketplace highest, partner lowest). Gift × family is noisy.

*4. Tenure:* no signal and the only shifted field (PSI 0.60) → dropped.

*5. Stability:* no trend over 15 months; **no festive (11.1% vs 11.5%) or Jul–Sep season effect (11.1%)**. Main drivers keep their direction every quarter. Some family drift (air fryer 14.3% → 10.7%, water purifier 17.8% → 12.6%, cooktop 7.8% → 10.6%, from 2025-Q2 to 2026-Q2).

*6. Train vs test:* every dispatch-time field PSI < 0.012. The test quarter looks like training.

*7. Margin input for Phase 5:* median order ₹4,440. At 25%/35% margin **99.8–100%** of orders clear the ₹375 calls-beat-holds condition. At 15% margin 83.6% clear, but **room heaters (median ₹2,324, 35% clear) and induction cooktops (₹2,789, 65%) don't**.

*8. Stakeholder claims:* Shield = 22.2% of orders / **36.1% of returns** / 2.0× rate. "No returns" = **88.6%** accuracy. Spring 2026 (deduplicated): 10.9% / 12.1% / 11.5%, no dip. *(Correction: the pre-work quoted 11.2/12.0/11.2 including duplicate rows.)*

**Decisions**
| Decision | Why | Alternative rejected |
|---|---|---|
| **Drop pincode region; use `city` or `metro`** (passed with the order) | Region `440` covers 12 cities; city matches metro pincodes 100% and is the real location | Keep region (encodes "non-metro", wrongly labelled Nagpur); use full 6-digit pincode (978 pincodes are shared across cities, too sparse) |
| `city` vs `metro` decided in Phase 4 by validation | City has more signal but noisy per-city estimates | Fix one now without evidence |
| **Drop tenure** | AUC 0.504 and PSI 0.60; also removes `signup_date` from the API | Keep with guard (adds a shifted input for no gain) |
| Drop hour, weekday, festive/season flags | Flat return rates | Keep "just in case" (noise, more API inputs) |
| Drop `warranty_months`, value-vs-list | Exactly determined by family / discount | Keep (redundant columns confuse LR coefficients and the reasons) |
| Core features: payment mode, promised days, prior returns/orders (+ rate, has-return), Shield, family, discount, order value | Strongest, stable over time | - |
| Weak fields (channel, tier, qty, gift, address missing, product age, notes) → Phase 4 ablation | Small or uncertain gains; each kept only if it helps on unseen months | Include all (overfitting, harder reasons) or drop all now (might lose a small real gain) |
| Test recency weighting in Phase 4 | Some family-level drift | Train only on recent months (throws away data) |

**Alternatives considered for the analysis itself:** tree-based feature importance was rejected as the main ranking because it's in-sample and favours high-cardinality fields. The single-field AUC is judged on later unseen months instead.

**Plan changes (data contradicted the plan):** see the v2.2 row below and in `plan.md`.

**Next step (Phase 3 - feature pipeline), driven by these results**
1. `features.py` builds the core set + candidates from one order record + the embedded catalogue. `city` and `shield_member` are inputs with an `"unknown"` fallback; no tenure, no pincode region, no time-of-day.
2. Leakage guard test against the `policy.md` §3 allow-list; train/serve parity test.
3. Then Phase 4: model ladder, with ablations for `city` vs `metro`, each candidate field, Shield, and recency weighting.

---

## Phase 2 follow-ups - before Phase 3 (2026-10-06)

Evidence: `notebooks/02_eda.ipynb` §10 (56 cells, executed); `evidence/margin_crossover_15pct.csv`.

**Results**

*Holdout discipline.* The Phase 2 single-field AUC ranking was computed on **Apr–Jun 2026, the final holdout**. Re-run on three walk-forward folds ending Mar 2026 (Jul–Sep 25, Oct–Dec 25, Jan–Mar 26): every field dropped for lack of signal stays at coin-flip level on **all three** folds (tenure 0.49–0.51, hour 0.48–0.51, weekday 0.49–0.51, notes 0.47–0.53, address missing 0.49–0.52, tier 0.47–0.52, qty 0.50–0.51). The drops are safe because they fail on any period. Strong drivers are strong on every fold (family 0.62–0.65, payment 0.60–0.62, promised days 0.59–0.60, prior returns 0.58–0.64, Shield 0.57–0.58).

*City confound.*
| Adjusted for | Metro gap | Reading |
|---|---|---|
| nothing | 4.3 pts | - |
| payment mode (COD vs prepaid) | **4.4 ± 1.2** | Not a COD proxy: COD share is the same in both tiers (30.4% vs 29.8%) |
| promised-delivery band | **2.1 ± 1.3** | About half is delivery time: non-metro promised 5.6 vs 4.0 days; gap is **0** at 1–3 days and +7.9 at 8–12 days |
| payment × promise × family | **1.9 ± 1.3** | Small residual location effect; interval nearly touches zero |

*Order value.* Within each family, return rates are flat across SKU tiers and value tertiles (air fryer 11.8 / 12.4 / 11.8%; room heater 11.9 / 11.4 / 11.7%). There's a slight, inconsistent rise in a few families at low discount (robot vacuum 15.5 → 18.9%, but mixer grinder falls).

*Rare flags (effect size, 95% interval).* **Gift: +5.5 pts [2.7, 8.3], risk ratio 1.50 [1.26, 1.78]**, the same in both training halves (17.7 vs 11.1%; 17.0 vs 10.8%), and +6.5 ± 3.0 pts after adjusting for family × payment (Apr 2025 – Mar 2026 only). Address missing +1.2 [−1.1, 3.5]; qty = 2: −1.2 [−3.7, 1.2]; discount = 0 and note `other` too rare to judge.

*Margin.* Crossover risk p× (above which a call beats a hold) vs call break-even p_call, at 15% margin: median room heater p× 0.9% vs p_call 8.6%; median cooktop 0% vs 8.2%. **Worst case**, the cheapest room heater (₹880): 9.9% vs 10.0% (true accounting) or 11.7% vs 11.2% (conservative, ignoring the margin a prevented return keeps), a sliver covering 1–2 orders before any hold handling or goodwill cost. All orders: 100% (true) / 99.8–100% (conservative) at 10–25% margin. *(A first version of this check had a sign bug for expensive orders in the conservative variant (robot vacuums showed 5.9%); fixed: when call − hold is already positive at p = 0, the crossover is 0.)*

**Decisions**
| Decision | Why | Alternative rejected |
|---|---|---|
| **All selection on walk-forward folds ending Mar 2026; Apr–Jun 2026 scored once at the end** (policy §5.3) | Keeps the expected-score estimate honest | Keep using Apr–Jun for choices (optimistic estimate) |
| **Ablation rule fixed in advance:** keep a candidate only if it improves AUC on ≥ 2 of 3 folds; within noise → simpler set (policy §5.7) | Prevents choosing on one lucky average | Mean-only rule (one fold can carry it) |
| Location: candidate; **`metro` preferred over `city` if within noise**; reasons worded neutrally ("orders delivered to this area… especially with longer delivery times") | About half the gap is delivery time; the residual is small and uncertain | Present it as a customer trait; drop location without testing |
| **Price represented once: `family` + `discount_pct`**; `order_value_inr` economics-only; SKU tier a candidate | Value = list × qty × (1 − discount); overlapping columns split one effect across LR coefficients and reasons; within-family value is flat | Order value as the feature (mixes family and discount into one number, hiding which drives the reason) |
| **Gift = serious candidate**; rare flags judged by effect size, not AUC (policy §5.6) | Real, stable +5.5 pts effect that AUC hides at 7% prevalence | Drop gift on its AUC of 0.50–0.53 |
| Address missing, qty: weak candidates (no evidence of an effect) | Intervals include zero | - |
| **Margin resolved: for every order worth acting on, calls beat holds in every family at margins ≥ 15%; at 10% only 2 of 10,504 orders have a sliver, below the operating cutoff** (corrected in Phase 5) | Crossover below call break-even everywhere | Per-family caveat in the memo (no longer needed) |
| Phase 8: if note and address features are dropped, remove `delivery_note` and `delivery_pincode` from the API inputs (privacy improvement) | Data minimisation | Accept and ignore them |

*(Corrected in Phase 5: exact count, no rounding. At **≥ 15% margin no order** has a window where a hold beats a paying call (true accounting). At **10% margin, 2 of 10,504 orders** (19 under conservative accounting), the cheapest room heaters, have a narrow window up to 12.0% (13.6%) risk where a hold edges a call by a few rupees, all **below the 13.7% operating cutoff**, so the policy never meets them. The earlier "100.0%" was rounding.)*

**Implication for Phase 5:** under the true accounting, calling pays from p ≈ 3–9% (depending on order value), which is below the 11.4% base rate. **Call capacity, not break-even, is the binding limit**, which supports "call the top X% the team can handle".

**Next step:** Phase 3, the feature pipeline (`features.py` + leakage guard + parity test).

---

## Phase 3 - Feature pipeline (2026-10-06)

Code: `src/kestrel/features.py` (+ constants in `config.py`); tests: `tests/test_features.py`, `tests/test_data_rules.py`, `tests/conftest.py`.

**Results**
- `build_features(records, catalogue)` turns raw order records into **19 features** (7 core numeric, 2 core categorical, 6 candidate numeric, 4 candidate categorical) plus a per-row list of fallbacks. Runs in 0.24 s on all 12,600 orders.
- On the real pack: **0 NaNs and 0 fallbacks** in train and test. Shield share 22.2%, metro share 33.5%, product age 63–1,130 days.
- **26 tests pass** (4 s): cleaning rules C1–C4 on the real pack; no banned column is a feature or an input; **injecting leaky values (`REVERSE_PICKUP`, a pickup date, the label) leaves the features unchanged**; the feature module reads no files; fallbacks for missing Shield/city, unknown SKU and unknown payment mode; raw note text never survives (gate-code digits removed, free text → `other`); pincode `0`/`000000`/missing → `address_missing`; **train/serve parity: 150 test orders fed one at a time as JSON-like payloads give exactly the batch features.**

**Decisions**
| Decision | Why | Alternative rejected |
|---|---|---|
| Builder returns tidy features (numbers with NaN, categories with `"unknown"`); **encoding and imputation live in the model pipeline** | LR and HGB share one feature contract; unknown values are imputed the same way in training and serving | One-hot inside `features.py` (would tie the contract to one model type) |
| Inputs are an explicit **allow-list** (`records.reindex(ALLOWED_INPUTS)`); anything else is dropped before any logic | Banned or unexpected fields can't leak in, whatever the caller sends | Drop a deny-list of banned names (misses new leaky fields) |
| Unknown values are **never guessed silently**: Shield/city → NaN/`unknown` (imputed by the pipeline), unknown SKU → family from the SKU code, and each case is listed in `fallbacks` | The API must tell the employee when a score rests on less information | Fill with defaults without reporting |
| Missing `qty` → 1, missing `is_gift` → not a gift, missing pincode → address missing | Natural defaults for optional fields | Treat as errors (would reject valid minimal orders) |
| `state` accepted but unused | Each city maps to exactly one state (redundant) | Use state as well as city |
| Training builds records the same way the API will (orders + `shield_member`/`city`/`state` joined from `customers.csv`) and uses the same catalogue | Single path, so parity holds by construction | Separate training feature code |
| Product catalogue as a plain dict (`catalogue_from_products`), JSON-ready for `model_meta.json` | Service starts without `data/` | Ship `products.csv` |

**Alternatives considered:** sklearn `FunctionTransformer` wrapping the builder inside the pipeline. Rejected for now because the API needs the fallback list as well as the features, and a plain function is easier to test. Revisit if Phase 8 wants a single `pipeline.predict(records)` call.

**Next step:** Phase 4. `03_modeling.ipynb` on walk-forward folds ending Mar 2026: rule baseline → LR → HGB, the ablation rule fixed in policy §5.7, `metro` vs `city`, gift, recency weighting, Shield ablation, sigmoid calibration on out-of-fold predictions, the leak simulation, then Apr–Jun 2026 scored once.

---

## Phase 4 - Modelling and validation (2026-10-06)

Evidence: `notebooks/03_modeling.ipynb` (selection; **never reads Apr–Jun 2026**), `notebooks/03b_holdout_and_final.ipynb` (one-time holdout + final fit), `src/kestrel/model.py`, `src/kestrel/train.py`, `tests/test_model.py`. Figures: `evidence/figures/03_calibration_oof.png`, `03b_calibration_holdout.png`. Rules were written into `policy.md` §5.7 and `plan.md` (v2.4) **before** anything ran; every decision below is computed by code from them.

**Setup.** Selection data Apr 2025 – Mar 2026 (8,378 orders). Folds: validate Jul–Sep 2025 (train 2,013 orders), Oct–Dec 2025 (train 4,170), Jan–Mar 2026 (train 6,252); ~2,100 orders and 225–247 returns per fold. No class weighting or resampling.

### Every model tried (64 configurations; ROC-AUC per fold Jul–Sep / Oct–Dec / Jan–Mar)
| Model | AUC per fold | Mean AUC | Mean PR-AUC | Verdict |
|---|---|---|---|---|
| Base rate (constant) | 0.500 / 0.500 / 0.500 | 0.500 | 0.112 | Floor |
| Rule: prior returns × Shield lookup | 0.673 / 0.649 / 0.658 | 0.660 | 0.228 | "Spreadsheet" bar |
| **LR, 9 core features** | **0.800 / 0.770 / 0.766** | **0.778** | **0.380** | **Chosen** (+0.118 over rule, every fold) |
| HGB, core, default | 0.727 / 0.732 / 0.723 | 0.727 | 0.290 | Overfits at this size |
| LR core + one candidate (8 runs) | best: gift +0.005 / −0.001 / +0.004; channel +0.002 / +0.001 / +0.007 | ≤ 0.781 | - | **None passes** (≥ 0.005 on ≥ 2/3 folds) |
| HGB core + one candidate (8 runs, check) | gift +0.012 / +0.004 / +0.008; product age −0.039 on one fold | - | - | Larger swings both ways |
| LR core + metro / + city | 0.802 / 0.770 / 0.763; 0.795 / 0.770 / 0.762 | 0.778; 0.776 | - | **No location** (metro −0.0001, city −0.0027) |
| HGB core + metro / + city | 0.737 / 0.740 / 0.731; 0.733 / 0.730 / 0.724 | 0.736; 0.729 | - | Check only |
| LR selected − Shield | 0.791 / 0.748 / 0.751 | 0.763 | 0.355 | **Shield costs 0.009 / 0.021 / 0.015**: kept (core), reliance documented |
| LR, recency half-life 6 m / 12 m | 0.800 / 0.771 / 0.766; 0.800 / 0.770 / 0.766 | 0.779; 0.779 | - | Dropped (≤ +0.001) |
| HGB selected, monotonic | 0.769 / 0.745 / 0.729 | 0.748 | 0.323 | Monotonic beats unconstrained by +0.021 → kept for HGB |
| LR grid C ∈ {0.01 … 3} (6) | flat from C = 0.3 to 3; C = 0.01 → 0.764 | 0.764–0.778 | - | **Default C = 1 stays** (no point passes) |
| HGB grid (24, monotonic) | best lr 0.03 / 7 leaves / 100 iter: 0.786 / 0.760 / 0.762 | 0.769 | 0.342 | Best HGB |
| **LR vs tuned HGB** | HGB − LR: −0.014 / −0.009 / −0.004 (bootstrap [−0.016, −0.003]) | - | - | **LR ships** (HGB needed > +0.01) |

### Results
- **Chosen model: logistic regression (C = 1) on 9 features**: promised delivery days, prior returns, prior orders, prior return rate, has-prior-return, discount, Shield, payment mode, family. Price is represented once (family + discount); no location, gift, channel, notes, address, tier, qty or product age.
- **Gift** has a real +5.5-point effect (Phase 2) but missed the bar by a hair (+0.0048 and +0.0043 on two folds). It touches 7% of orders and barely changes the ranking, so the pre-declared rule drops it. Recorded as a near-miss.
- **Location** adds nothing once delivery days are in the model, consistent with Phase 2 §10b (half the metro gap is delivery time).
- **Calibration:** fold slopes 1.08 / 0.93 / 0.96, so fold 1 is not clearly less confident (criterion > 0.2) and the calibrator uses all three folds: a = 0.986, b = −0.068, close to the identity, because LR on the true class balance is already calibrated. OOF deciles run from 1.7% to 40.6% on the diagonal.
- **Leak simulation (Jan–Mar 2026 fold):** LR with the post-dispatch columns gets **AUC 0.997, 99.3% accuracy** as exported. With dispatch-time values (`INSTALL_BOOKED` for fans/vacuums/purifiers, `NONE` otherwise, no pickup) it drops to **0.711**, below the honest model's 0.766, and flags **0.05%** of orders at 0.5. HGB: 0.995 → 0.681. ("Nobody returns" = 88.4% accuracy on this fold.)
- **Unknown values** (explicit, not imputer defaults; `ReturnRiskModel.predict_proba`): an unknown Shield / payment mode / family is scored as the training-share-weighted average of its known versions (Shield 22.2 / 77.8; payment UPI 37 / COD 30 / card 20 / EMI 12; families ~14% each), and still listed in `fallbacks`. Tests confirm each unknown scores strictly between its known versions; Shield equals the 22/78 average exactly. City, metro and gift need no handling because they aren't in the model.

### One-time holdout (Apr–Jun 2026, scored once on 2026-10-06 12:34 in `03b`)
Trained Apr 2025 – Mar 2026 with the walk-forward calibrator; 2,126 orders, 245 returns (11.5%).

| Metric | Jul–Sep 25 | Oct–Dec 25 | Jan–Mar 26 | **Apr–Jun 26 (holdout)** |
|---|---|---|---|---|
| ROC-AUC | 0.800 | 0.770 | 0.766 | **0.787** |
| PR-AUC | 0.419 | 0.344 | 0.376 | **0.421** |
| Brier | 0.080 | 0.084 | 0.088 | **0.084** |
| Top 5%: precision / recall | 58% / 26% | 42% / 20% | 54% / 23% | **58% / 25%** |
| Top 10%: precision / recall | 46% / 41% | 37% / 34% | 40% / 35% | **44% / 38%** |
| Top 20%: precision / recall | 31% / 57% | 30% / 56% | 31% / 53% | **33% / 58%** |

Holdout calibration: mean predicted 11.0% vs actual 11.5%; the top decile is 40.2% predicted vs 43.7% actual. Accuracy at 0.5 is 89.4% vs 88.5% for "nobody returns", which is why accuracy isn't the metric.

**Expected score on the test quarter (Jul–Sep 2026):** **ROC-AUC 0.77–0.80** (point estimate ~0.78; range = the 3 folds + holdout, which includes the same season a year earlier at 0.800). **PR-AUC 0.34–0.42** at an ~11% return rate; PR-AUC scales with the test quarter's return rate, roughly 3.2–3.8× the base rate. Risks to the downside: more first-time customers, a Shield-status shift, or season effects not seen in one year of history.

**Final model** retrained on all 15 months (Apr 2025 – Jun 2026) with the same configuration and calibrator: `models/model.joblib` (4.6 KB, no customer data) + `models/model_meta.json` (config, calibrator, unknown-value weights, metrics, 21-row catalogue). `python -m kestrel.train` reproduces it exactly (verified). Largest effects (log-odds per +1 SD or vs the average category): prior returns +0.56, robot vacuum +0.54, promised days +0.44, Shield +0.39, COD +0.34, discount +0.24; prepaid UPI −0.82, ceiling fan −0.82, mixer −0.80.

### Decisions
| Decision | Why | Alternative rejected |
|---|---|---|
| **Ship LR (C = 1), 9 core features** | Best on every fold; HGB worse even after tuning and monotonic constraints; exact, explainable contributions | HGB (−0.009 mean); LR + candidates (none passes) |
| Drop gift, location, channel, notes, address, tier, qty, product age | Pre-declared rule: none improves AUC ≥ 0.005 on ≥ 2/3 folds | Keep gift on its effect size (the rule was fixed in advance; Phase 2 marked it a candidate, not a pass) |
| Keep Shield, document reliance (−0.015 AUC without it) | Core driver; snapshot risk is disclosed, not hidden | Drop for snapshot risk (loses real signal on every fold) |
| No recency weighting; default C | Within noise | - |
| Calibrator on all three folds (a = 0.986, b = −0.068) | Fold 1 not less confident by the declared criterion | Folds 2–3 only |
| Separate notebook for the holdout, run once after selection was frozen; config asserted unchanged | Makes "touched exactly once" auditable | Holdout section inside the selection notebook (re-runs during development) |
| Phase 7 is now just scoring + checks | The final all-data model already exists | Retrain again in Phase 7 |

**Consequences for later phases**
- **Phase 8, data minimisation (triggered):** notes, address, city, gift, qty and channel are not in the model, so the API needs only `sku`, `payment_mode`, `promised_delivery_days`, `discount_pct`, `customer_prior_orders`, `customer_prior_returns` and an optional `shield_member`. **`delivery_note`, `delivery_pincode`, `city`/`state`, `is_gift`, `qty` and `sales_channel` are removed from the API inputs**: a privacy improvement (no gate codes, addresses or location reach the service).
- **Phase 8, reasons:** the four history features are correlated (prior return rate gets a negative coefficient once prior returns and has-prior-return are in). Their contributions must be **summed into one "customer history" reason**, not shown separately.
- **Phase 5:** calibrated probabilities are trustworthy (holdout mean 11.0% vs 11.5%; top decile 40% vs 44%). Capacity table from the top-k precision/recall above.

**Next step:** Phase 5, the decision economics (call capacity table, ₹ net per month, sensitivity, Shield share of flagged orders).

---

## Phase 5 - Decision economics (2026-10-06)

Evidence: `notebooks/04_decision_economics.ipynb`, `src/kestrel/economics.py`, `tests/test_economics.py`; figures `evidence/figures/04_call_vs_hold_net.png`, `04_call_capacity.png`. Data: walk-forward out-of-fold predictions of the chosen model (6,365 orders, Jul 2025 – Mar 2026), calibrated (mean predicted 11.2% = actual 11.2%). ₹ figures use **what actually happened** to those orders. **The holdout was not used.** Monthly figures use the export's volume (~699 orders/month); per-1,000-order figures scale to any volume.

**Assumptions:** return ₹1,150 (₹600 sensitivity); call ₹45, prevents 35%; hold → 12% cancel; **margin 25% of order value (assumption, 15/35% sensitivity)**; headline call value ignores the margin a prevented return keeps (conservative). **Declared before computing:** default capacity = largest top-X% whose marginal band is still net-positive.

**Results**
All figures per month at the export's volume (~699 orders/month); per-1,000-order figures scale to any volume.

| Policy (realised, walk-forward folds) | Share of orders actioned | Precision | Returns avoided / month | Good orders lost / month | Net ₹ / month | Net ₹ per 1,000 orders |
|---|---|---|---|---|---|---|
| Ship everything (today) | 0% | - | 0 | 0 | 0 | 0 |
| **Ritu's ask: hold top 10%** | 10% | 41% | 3.4 | 5.0 | **−10,400** | −14,800 |
| Hold top 20% | 20% | 31% | 5.2 | 11.6 | −26,500 | −37,900 |
| Call top 10% | 10% | 41% | 10.0 | 0 | +8,300 | +11,900 |
| **Call top 25% (recommended default)** | 25% | 27% | 16.7 | 0 | **+11,400** | **+16,300** |
| Call everyone above break-even (11.2%) | 32% | 24% | 18.5 | 0 | +11,200 | +16,000 |

*(Units fixed after Phase 5 sign-off: an earlier version mixed 9-month totals with per-month figures.)*

**Scale framing (for the memo):** ~**78 returns/month** at the export's volume cost **~₹89,800/month** (₹1,150 each). Calling the top 25% avoids ~16.7 of them, **~21% (about 1 in 5)**, and nets **~13% of the monthly return cost** (conservative; ~₹11,400). **The 35% prevention rate is the least certain input** (a single spring pilot, no visible dip in the data), which is why the next-week action is a controlled pilot, not a roll-out.

- **Break-evens:** a call pays above **11.2%** risk (₹1,150) or 21.4% (₹600); counting kept margin, a median order pays from 5.7%. **32% of orders** are above 11.2%, so capacity, not break-even, binds.
- **Holds never win:** for 0.00% of orders is a hold better than a call; a hold beats doing nothing for only 1.8%. Holding loses because the cancelled good orders are disproportionately high-value (robot vacuums, purifiers dominate the top decile), and their lost margin outweighs ₹1,150 × 12% of the returns.
- **Capacity curve:** value climbs to ~10–15% of orders, flattens at 20–30%, and the 25–30% band is already slightly negative (band precision 10.0%). **Top 10% earns 73% of the top-25% value with 40% of the calls; top 5% earns 50%.**
- **Recommended default: top 25%** (risk ≥ **13.7%**): ~175 calls/month, ~6/day; 27% of called orders would otherwise return (2.4× base rate); covers **61% of all returns**; avoids ~17 returns/month; **net ~₹11,400/month = ₹16,300 per 1,000 orders**. At ₹600: same rule → top 15%, ₹2,900/month. Counting kept margin: ~₹61,400/month.
- **Sensitivity (top 25%):** calls beat holds in **18/18** scenarios; call net-positive in **15/18** (the 3 negatives: ₹600 per return with only 25% prevention). Holds lose ₹18,600–55,400/month in every scenario.
- **Shield:** 42–49% of flagged orders are Shield vs 22% overall, with similar precision (29.6% vs 25.7% at top 25%), so there's no bias, just higher risk. Holding at top 25% would cancel ~9 Shield orders a month. By family, robot vacuums (48% flagged) and purifiers (39%) dominate the call list.

**Correction to Phase 2 §10e (found by a Phase 5 test):** the margin claim was stated "at any margin ≥ 10%". The exact count: at **≥ 15% margin, no order** has a window where a hold beats a paying call. At **10%**, **2 of 10,504** orders (19 under conservative accounting), the cheapest room heaters, have a narrow window up to 12.0% (13.6%) risk, all **below the 13.7% operating cutoff**. The earlier "100.0%" was rounding. Corrected in `key_findings.md`, `policy.md`, `plan.md` and notebook 02's reading; the test now asserts the precise claim.

**Decisions**
| Decision | Why | Alternative rejected |
|---|---|---|
| **Call, never hold** | Holds lose money at every capacity and in every sensitivity scenario | Ritu's hold (−₹10,400/month at top 10%); hybrid call+hold (holds never beat calls for any order) |
| **Default top 25% (cutoff 13.7%)**, with a capacity menu (5–30%) | Declared rule; capacity unknown, so Ritu's team picks X | "Call everyone above 11.2%" (32% of orders, no extra value: band 25–30% is negative) |
| Headline ₹ conservative (kept margin not counted); 25% margin for hold losses | Under-promise; the conclusion doesn't depend on it | Count kept margin in the headline (5× larger, rests on an unverified margin) |
| ₹ judged on realised outcomes, not predicted probabilities | Doesn't depend on calibration | Expected values only |
| Decision stored in `model_meta.json` (`decision`: cutoff, capacity menu, costs) | The API reads one source of truth | Hard-code the cutoff in the API |
| Shield: same "call, don't hold" rule | No bias in precision; a call puts no order at risk | Exempt Shield from calls (would skip 42–49% of the best-value calls) |

**For the memo (Phase 9):** the number for the board is *"Of the orders we call, about 1 in 4 would otherwise have come back (2.4× normal), and those orders hold 61% of all returns"*, not "95% accuracy". The rupees: ~₹16,300 net per 1,000 orders (conservative), vs ~−₹14,800 for holding the top 10%.

**Next step:** Phase 6, evidence and error analysis (backtest report, segment performance incl. seen/unseen and `prior_orders = 0`, gift-order calibration on OOF as a known limitation with its ₹ effect, history-coefficient note, failure gallery, expected-score write-up).

---

## Phase 6 - Evidence and error analysis (2026-10-06)

Evidence: **`evidence/backtest_report.md`** (the "evidence that it works, and how often it does not" deliverable), `notebooks/05_error_analysis.ipynb`, `evidence/figures/05_segment_auc.png`. Data: walk-forward out-of-fold predictions; the holdout appears only as the aggregates stored by its single run.

**Results**
- **Works:** ROC-AUC 0.800 / 0.770 / 0.766 on the walk-forward quarters, 0.787 on the holdout; **monthly AUC 0.741–0.821** (sd 0.029), no drift. Calibrated (deciles 1.7–40.6% predicted vs 1.3–40.7% actual). The share called per month stays at 22–28%, so the 13.7% cutoff behaves like "top ~25%".
- **How often it's wrong (per month, operating point):** ~175 calls → ~48 to customers who would have returned, **~127 false alarms (73%)** at ₹45 each (~₹5,700/month, already in the net); **~30 returns/month (39%) not flagged**, handled as today. **10% of returns score below 5%** (cheap prepaid orders, no prior returns). These orders look like the lowest-risk orders on every field available at dispatch, so no model using this data can separate them.
- **Segments:** new-to-model customers 0.781 vs seen 0.771 (no weakness). **No CRM history (`prior_orders = 0`): weakest, AUC 0.745 [0.704, 0.784], recall at cutoff 46% vs 66%.** Shield 0.764 vs 0.767, same calibration. Weakest families: room heater 0.724, robot vacuum 0.726. Strongest: ceiling fan 0.828, partner outlet 0.831.
- **Gift calibration (OOF, known limitation):** gift orders **under-predicted by 7.2 pts** (10.5% vs 17.7%, ×1.69). A gift-aware score would add ~10 gift calls/month worth **~₹260/month** (~2% of policy value). Small: gifts are 7% of orders, and 22% of them are already called (precision 47%).
- **Other calibration gaps:** robot vacuum −3.4 pts (rising return rate); partner outlet +2.7, marketplace −2.2 (channel not in the model); EMI +2.0.
- **Failure gallery:** confident false alarms are customers with 2–4 prior returns out of 4–5 orders who kept this one (right on average, wrong individually); confident misses are cheap prepaid orders with no history.
- **History coefficients:** the negative prior-return-rate coefficient is collinearity among the four history features, not an error, so reasons merge them (line in `03b` and in the report).
- **Holdout ₹ check: skipped.** The Apr–Jun predictions were never saved, and `03b` is not re-run.
- **76 tests pass**, run from inside the notebook.

**Decisions**
| Decision | Why | Alternative rejected |
|---|---|---|
| Ship as is; record gift, channel, robot-vacuum and no-history gaps as known limitations | Each is small in ₹ (gift ~₹260/month) or failed the selection rule; re-opening selection after seeing the holdout would break the protocol | Add gift/channel now (post-hoc change after the holdout was spent) |
| Governance in `policy.md` §9: quarterly retrain, three monthly monitors with review triggers, data-feed asks | Makes "how often it doesn't work" operational | No monitoring |
| Report written for a non-notebook reader | It's a deliverable on its own | Point graders at notebooks |

**Next step:** Phase 7, scoring `test_unlabelled.csv` → `outputs/predictions.csv`, with checks incl. the share above the 13.7% cutoff vs the 25% assumed.

---

## Phase 7 - Predictions (2026-10-06)

Code: `src/kestrel/predict.py` (`python -m kestrel.predict`); test: `tests/test_predictions.py`; evidence: **`evidence/predictions_check.md`**.

**Results**
- `outputs/predictions.csv`: **2,096 rows, one per `order_id`, same IDs and order as `sample_submission.csv`, columns `order_id, score`, no NaN, all scores in [0, 1]**. All checks PASS, and the run asserts them. No fallbacks were needed for any test order.
- `outputs/test_scored_detail.csv` (git-ignored, like all `outputs/*.csv`): score, recommended action (CALL/SHIP) and fallbacks per order, so later checks never need a re-run.
- **Score distribution matches the walk-forward scores:** median 0.072 vs 0.070, p90 0.261 vs 0.246, mean **11.6%** vs 11.2%; Kolmogorov–Smirnov distance **0.017 (p = 0.72)**.
- **Share at or above the 13.7% cutoff: 25.5%** (vs the 25% assumed) → 535 calls over 92 days = **5.8 calls/day**. By month: Jul 24.3% (5.2/day), Aug 25.8% (6.1/day), Sep 26.5% (6.1/day).
- Re-running the script reproduces identical scores. 77 tests pass.

**Decisions**
| Decision | Why | Alternative rejected |
|---|---|---|
| Submit the calibrated probability as `score` | Same AUC as the raw score; consistent with the API and the ₹ rule | Raw score or rank |
| Test orders get `shield_member` joined from `customers.csv`, as the warehouse feed would pass it | Same path as training (parity) | Leave Shield unknown (would average it and lose signal) |
| Checks recorded in a committed evidence file; predictions stay out of git | Order IDs are operational data (§10); the CSV is delivered with the submission | Commit `predictions.csv` |
| No tabulate dependency (small markdown helper) | Keeps the install minimal | Add `tabulate` |

**Expected score, ready for the submission form:**
> **ROC-AUC 0.77–0.80 (best guess ~0.78); PR-AUC 0.34–0.42** at an ~11% return rate.
> Why: the model was chosen on three walk-forward quarters (train on the past, score the next quarter): ROC-AUC 0.800 / 0.770 / 0.766, PR-AUC 0.42 / 0.34 / 0.38. A fourth quarter (Apr–Jun 2026) was held out and scored exactly once after every choice was frozen: ROC-AUC 0.787, PR-AUC 0.421, inside the walk-forward range, so selection didn't inflate the estimate. The range includes Jul–Sep 2025, the same season as the test quarter a year earlier (0.800). The test quarter looks like training on every model input (population stability index < 0.012 per field; Shield share 22.1% vs 22.2%), and its predicted scores match the walk-forward scores (KS 0.017, mean 11.6% vs 11.2%). PR-AUC depends on the quarter's return rate (about 3.2–3.8× it), hence its wider range. Downside risks: more customers without order history (the weakest segment, AUC 0.745), a shift in Shield status, or a season effect one year of data can't show.

**Next step:** Phase 8, the service (FastAPI `POST /score` with the 7-field input, CALL/SHIP from `model_meta.json`, merged history reason, neutral wording, fallbacks; one screen; synthetic samples; runs without `data/`), then the "service behaviour" section of the report.

---

## Plan changes

| Date | Change | Reason |
|---|---|---|
| 2026-10-06 | Phase 6: error analysis reported separately for seen vs unseen customers **and** for `prior_orders = 0` vs > 0 | User request at Phase 1 close-out; the data shows these are different groups (458 unseen customers have history, 383 seen ones show 0) |
| 2026-10-06 | Phase 2: new first item, pincode region vs customer city | User request; tests whether the pincode field is reliable before modelling regions |
| 2026-10-06 | **v2.2: Phase 3 feature list revised.** Pincode region dropped (→ `city`/`metro`); tenure dropped; hour/weekday/festive dropped; `value_vs_list` and `warranty_months` dropped as redundant; weak fields → Phase 4 ablation candidates; tenure removed from the snapshot ablation | **Data contradicted the plan** (Phase 2): `440` = all 12 non-metro cities (8.4% Nagpur); tenure AUC 0.504 + PSI 0.60; hour/weekday/season flat; warranty = family; value = list × qty × (1 − discount) |
| 2026-10-06 | Spring-pilot figures corrected to deduplicated 10.9% / 12.1% / 11.5% | Pre-work numbers included duplicate rows; conclusion unchanged |
| 2026-10-06 | **v2.3:** selection only on walk-forward folds ending Mar 2026; ablation rule fixed in advance; metro preferred within noise; price = family + discount (order value economics-only); gift a serious candidate; §5a margin resolved; Phase 8 neutral location wording + data minimisation | User sign-off on Phase 2 + Phase 2 §10 evidence (city gap halves within delivery bands; within-family value flat; gift +5.5 pts; crossover < call break-even) |
| 2026-10-06 | **v2.4:** Phase 4 rules fixed before running (noise threshold, LR-vs-HGB rule, no class weighting, declared grid, run order, calibration-fold criterion, unknown-value averaging, one-time holdout); gift/qty defaults reported as fallbacks | User instructions before Phase 4 |
| 2026-10-06 | **v2.5:** holdout in a separate notebook (03b) run once; final all-data model saved in Phase 4 (Phase 7 = scoring + checks); API inputs reduced to the 7 fields the model uses (data minimisation triggered); history reasons grouped | Phase 4 results: LR on 9 core features, no candidate kept; correlated history coefficients |
| 2026-10-06 | **v2.6:** Phase 6 adds a gift-order calibration check (OOF) as a known limitation and the history-coefficient note | User notes at Phase 4 sign-off |
| 2026-10-06 | **v2.7:** decision stored in `model_meta.json` (`decision`); default capacity top 25% (cutoff 13.7%); API `recommended_action` = CALL at/above the cutoff, else SHIP, never HOLD; margin claim corrected (≥ 15%; 2 orders at 10%) | Phase 5 results; a Phase 5 test exposed rounding in the Phase 2 claim |
| 2026-10-06 | **v2.8:** Phase 5 table in consistent per-month units; Phase 7 reports the test share above the 13.7% cutoff (calls/day vs the 25% assumed); Phase 6 holdout ₹ check **skipped** (Apr–Jun predictions were never saved, and re-running `03b` isn't allowed); Phase 9 scale framing | User notes at Phase 5 sign-off |
| 2026-10-06 | **v2.9:** report made standalone (model ladder, leak table, expected-score reasons); monitors only on orders ≥ 30 days old + a measured-prevention monitor (trigger < ~15%: calls stop paying below 14.3% at the operating point); Phase 8 adds a service-behaviour section; Phase 7 saves a detail file | User notes at Phase 6 sign-off |
