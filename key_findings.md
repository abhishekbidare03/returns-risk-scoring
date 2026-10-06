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

## Plan changes

| Date | Change | Reason |
|---|---|---|
| 2026-10-06 | Phase 6: error analysis reported separately for seen vs unseen customers **and** for `prior_orders = 0` vs > 0 | User request at Phase 1 close-out; the data shows these are different groups (458 unseen customers have history, 383 seen ones show 0) |
| 2026-10-06 | Phase 2: new first item, pincode region vs customer city | User request; tests whether the pincode field is reliable before modelling regions |
| 2026-10-06 | **v2.2: Phase 3 feature list revised.** Pincode region dropped (→ `city`/`metro`); tenure dropped; hour/weekday/festive dropped; `value_vs_list` and `warranty_months` dropped as redundant; weak fields → Phase 4 ablation candidates; tenure removed from the snapshot ablation | **Data contradicted the plan** (Phase 2): `440` = all 12 non-metro cities (8.4% Nagpur); tenure AUC 0.504 + PSI 0.60; hour/weekday/season flat; warranty = family; value = list × qty × (1 − discount) |
| 2026-10-06 | Spring-pilot figures corrected to deduplicated 10.9% / 12.1% / 11.5% | Pre-work numbers included duplicate rows; conclusion unchanged |
