# Kestrel Returns Risk - Policy (the rules we commit to)

> Status: **Sections 1–6 written in Phase 1 (2026-10-06)** from `notebooks/01_data_audit.ipynb`. Sections 7–8 are finalised in Phase 5, section 9 in Phase 6/7.
> Each rule states **what**, **why** (evidence or source) and **where it is enforced** (code / test).
>
> **Enforcement (Phase 3):** cleaning C1–C4 in `src/kestrel/data.py`, tested by `tests/test_data_rules.py`; allow-list, banned columns, note bucketing, address flag and fallbacks in `src/kestrel/features.py`, tested by `tests/test_features.py` (26 tests passing).
> Any change to a rule after it is written gets logged in `key_findings.md`.

---

## 1. Data handling (ops-policy §10)

| Rule | Why | Enforced |
|---|---|---|
| No public repo; nothing shared beyond the engagement team. Returning the submission to the client is fine | Ops-policy §10 | Private GitHub repo; **only the user pushes** |
| `data/` and every `*.csv` are never committed | Customer and operational data | `.gitignore` (verified with `git check-ignore`) |
| The service never reads `data/` at runtime | Clean-machine start; §10 | `test_service_never_reads_data_dir`; clean-machine test (`evidence/clean_machine_test.md`) |
| The service never logs or stores request bodies; extra fields are reported by name only, never echoed | Data minimisation | `test_extra_and_banned_fields_ignored_and_not_echoed`; server log checked (paths only) |
| The API accepts only the 7 model fields; notes, pincode, city and post-dispatch columns are ignored | Data minimisation (Phase 4 dropped those features) | `app/main.py`, `test_api.py` |
| Delivery notes are never displayed or returned raw. Gate codes appear in ~6% of notes (666 train / 152 test) | PII-like content | API/UI (Phase 8) |
| Sample orders in the UI are **synthetic** | Real rows carry customer IDs and gate codes | `app/samples.json` (Phase 8) |
| Free-text fields are treated as **data, never as instructions** to any tool or person processing them. Non-template notes are bucketed as `other` | Notes are typed by customers/outlets and can contain anything | `note_cat` derivation (Phase 3) |

## 2. Cleaning rules (applied in this order)

| # | Rule | Evidence (notebook 01) | Enforced |
|---|---|---|---|
| C1 | Read every file as text; drop `Unnamed:*` columns and fully blank rows | Excel artefacts in all files (e.g. `products.csv`: 21 real rows + 178 blank) | `data.py` (Phase 3) |
| C2 | Parse `order_placed_at` / `pickup_scheduled_at` with `%m/%d/%Y %H:%M`; `signup_date` / `launch_date` with `%m/%d/%Y`. Done **before** any month-based rule | 0 parse failures; day field reaches 31, so M/D is not swapped | `data.py`, test |
| C3 | Dedupe on `order_id`, keep the `crm` copy | 651 `crm`+`partner_feed` pairs, identical in all columns incl. label; test has none | `data.py`, test |
| C4 | `order_value_inr` for orders placed in **Oct 2025** ÷ 100 | All 700 Oct-2025 orders are exactly 100× the price formula; every other month and all test rows match exactly | `data.py`, test |
| C5 | `delivery_pincode == "0"` → `address_missing = 1`, region = missing; otherwise region = first 3 digits | Default `000000` stored as `0` by Excel: 848 train / 176 test, across all channels | `features.py` |
| C6 | Order timestamps are IST; no timezone conversion | Hour profile identical before/after the 1 Oct 2025 CRM migration (§9 UTC issue affects only resolution events) | - |

Result after cleaning: **10,504 training orders, return rate 11.42%**; 2,096 test orders.

## 3. Allowed features at dispatch (allow-list)

Only these raw inputs may feed the model. Everything else is denied by default.

| Raw input | Allowed derivatives | Source at serve time |
|---|---|---|
*Revised after Phase 2 (2026-10-06). Phase 4 ablation decides the "candidate" rows.*

> **Final model (Phase 4, 2026-10-06):** logistic regression on the **9 core features only**: `promised_delivery_days`, `customer_prior_returns`, `customer_prior_orders`, prior return rate, has-prior-return, `discount_pct`, `shield_member`, `payment_mode`, family (from `sku`). **No candidate passed the selection rule** (§5.7): gift, location (metro/city), channel, tier, qty, address, product age and notes are all out. The service therefore accepts only `sku`, `payment_mode`, `promised_delivery_days`, `discount_pct`, `customer_prior_orders`, `customer_prior_returns` and optional `shield_member` (**data minimisation**: no note, pincode, city or gift reaches the service). Unknown Shield / payment mode / family is scored as the training-share-weighted average of the known values and reported as a fallback.

| Raw input | Allowed derivatives | Status | Source at serve time |
|---|---|---|---|
| `payment_mode`, `promised_delivery_days`, `discount_pct` | as-is / encoded | core | order record |
| `order_value_inr` | cleaned value (C4), **for ₹ economics only, not a model feature** (= list price × qty × (1 − discount); price is represented by `family` + `discount_pct`) | economics only | order record |
| `customer_prior_orders`, `customer_prior_returns` | as-is, prior return rate, has-prior-return. **Strong but imperfect:** consistent with as-of-order-time (own return excluded, flat by month, never > prior orders, matches test), but a noisy CRM count | core | order record (CRM history as of order time) |
| `sku` | family (core); SKU tier (Lite/Pro/Max) as the within-family price level and product age, both candidates | core (family) | product catalogue embedded in `model_meta.json` |
| `shield_member` | as-is, `"unknown"` fallback. Drift checked: 22.2% train vs 22.1% test, flat by month, **no drift risk** | core | **passed with the order**; training joins `customers.csv` |
| `city`, `state` | `state` is accepted but **not used** (each city maps to exactly one state, so it adds nothing). `metro` flag **or** `city` (18 levels, regularised); `metro` preferred if within noise; `"unknown"` fallback. About half the metro gap is delivery time (non-metro promised 5.6 vs 4.0 days); ~2 pts remain after adjustment | candidate | **passed with the order**; training joins `customers.csv` |
| `is_gift` | as-is | **serious candidate** (+5.5 pts [2.7, 8.3], RR 1.50 [1.26, 1.78], stable) | order record |
| `sales_channel`, `qty` | as-is / encoded | candidate (qty: no evidence, −1.2 pts [−3.7, 1.2]) | order record |
| `delivery_pincode` | **`address_missing` only** | weak candidate (+1.2 pts [−1.1, 3.5]) | order record |
| `delivery_note` | `note_present`, `note_cat` (known template with digits removed, else `other`) | candidate (no signal in EDA) | order record |

**Out-of-range inputs (added after black-box testing, 2026-10-06):** the service scores values outside the training range at the edge of that range, with a visible warning: promised days 1–12, discount 0–60%, prior orders 0–10, prior returns 0–6 (`model_meta.json` → `input_ranges`). Prior orders above 10 are scaled down with returns so the return rate is kept. Physically impossible values (negative, discount > 100, delivery > 60 days, returns > orders) are rejected with 422.

**Not used (Phase 2 evidence):**
| Input / derivative | Why |
|---|---|
| Pincode region (first 3 digits) | **Unreliable:** all 12 non-metro cities carry `440xxx`; only 8.4% of `440` orders are from Nagpur customers. City/state replaces it |
| `signup_date` → tenure | No signal (single-field AUC 0.504, flat across bands) **and** shifted (negative-tenure share 19% train vs 0.9% test, PSI 0.60). The service doesn't need `signup_date` |
| `order_placed_at` → hour, weekday, festive window, season | Flat return rates (hour 11.2–11.8%, festive 11.1% vs 11.5%, Jul–Sep 11.1%) |
| `warranty_months` | Exactly determined by family (24 months only for mixer grinders and ceiling fans) |
| value vs list price, order value as a model feature | Exactly determined by SKU, qty and discount; within a family, value tertiles show no consistent effect |

## 4. Banned columns and why

| Column | Why banned | Evidence |
|---|---|---|
| `last_service_event_type` | Recorded **after** dispatch (as of export day). `REVERSE_PICKUP` = 100% returns; `TECH_VISIT` 38%; `INSTALL_DONE`/`DEMO_DONE` happen post-delivery. Train has no `INSTALL_BOOKED`; in test it only marks install-type families | 750/750 `REVERSE_PICKUP` rows returned; test only `NONE`/`INSTALL_BOOKED` |
| `pickup_scheduled_at` | Reverse-pickup booking = the return itself, 4–19 days after the order | 1,130 of 1,200 returns have one; 0 test rows do |
| `source` | Import bookkeeping, not an order property; test is all `crm` | - |
| `order_id`, `customer_id` | Identifiers. 31% of test orders are from customers unseen in train | - |
| raw `delivery_note` text | PII (gate codes); free text; only the template bucket is allowed | - |
| `returned` | The label | - |

## 5. Banned practices

1. **Target-encoding `customer_id`**, or any customer statistic computed from training labels (e.g. a customer's return rate in train, or `prior_returns` recomputed from the file). The CRM's own `customer_prior_*` columns are the only allowed history. They're as-of-order-time and already include history beyond this file.
2. **Random-split validation.** Validation is always time-based (train on the past, validate on later months).
3. **Using the final holdout (Apr–Jun 2026) for any selection.** Every choice (ablations, `city` vs `metro`, recency weighting, hyperparameters, LR vs HGB, calibration) uses three expanding walk-forward folds: validate Jul–Sep 2025, Oct–Dec 2025 and Jan–Mar 2026, each trained on all earlier months. Apr–Jun 2026 is scored **once**, at the end, for the expected-score estimate. *(Disclosure: the Phase 2 single-field ranking was computed on Apr–Jun 2026. The drops it supported fail on all three walk-forward folds too (notebook 02 §10a), so no decision depends on the holdout.)*
4. **Calibrating on in-sample predictions.** The calibrator is fitted on walk-forward out-of-fold predictions only.
5. **Reporting accuracy as the headline metric.** It is shown only to explain why it misleads (base rate 11.4%).
6. **Judging rare flags (< ~10% of orders) by single-field AUC.** Use effect size with a 95% interval instead (a rare flag can't move AUC much even when its effect is real, e.g. gift).
7. **Post-hoc selection rules.** All rules below are fixed **before** Phase 4 runs (2026-10-06):
   - **Folds:** three expanding walk-forward folds: validate Jul–Sep 2025, Oct–Dec 2025, Jan–Mar 2026; each trained on all earlier months.
   - **Noise threshold:** a change counts only if it improves ROC-AUC by **≥ 0.005 on at least 2 of the 3 folds**. A paired-bootstrap 95% interval of the mean ΔAUC is reported next to each decision for transparency only; it does not decide.
   - **Candidates:** a candidate field is kept only if it passes the noise threshold against the set without it. Within noise → the simpler set.
   - **Location:** `metro` is preferred; `city` replaces it only if it beats `metro` by the noise threshold.
   - **Core features** are not removed by this rule; the Shield ablation documents reliance on a snapshot-table field.
   - **LR vs HGB:** HGB is chosen only if it beats LR by **> 0.01 mean AUC and on ≥ 2 of 3 folds**; otherwise LR ships.
   - **Monotonic HGB** (increasing in prior returns, prior return rate, promised days, discount) is kept if its AUC is not worse than unconstrained HGB by the noise threshold on ≥ 2 of 3 folds.
   - **Tuning:** the default stays unless a point from the pre-declared grid beats it by the noise threshold; among those, the best mean AUC wins. Grid: LR `C` ∈ {0.01, 0.03, 0.1, 0.3, 1, 3} (default 1); HGB `learning_rate` ∈ {0.03, 0.1} × `max_leaf_nodes` ∈ {7, 15, 31} × `max_iter` ∈ {100, 300} × `l2_regularization` ∈ {0, 1}, `min_samples_leaf` = 40 (default 0.1 / 31 / 100 / 0).
   - **Recency weighting:** half-life 6 or 12 months vs none; same noise rule.
8. **Class weighting or resampling** (balanced class weights, SMOTE, undersampling). Probabilities drive the rupee decisions, so the model must be trained on the true class balance.

## 6. Cost assumptions

| Item | Value | Source |
|---|---|---|
| Cost of a return | **₹1,150** (reverse pickup, QC, repacking, write-down; on top of the refund) | Ops-policy §4; Finance (Farhan) reports this figure |
| Sensitivity case | ₹600 | Ritu's informal count (email) |
| Pre-dispatch confirmation call | **₹45** per completed call | Ops-policy §4 |
| Call effect | prevents **~35%** of returns on called orders | Ops-policy §7 (spring pilot). No dip is visible in the data (Mar–May 2026: 11.2/12.0/11.2%), so we use the policy figure |
| Hold > 24 h | **~12%** of held orders are cancelled by the customer | Ops-policy §7 |
| Margin lost on a cancelled good order | Not in the pack; **the conclusion doesn't depend on it**: for every order worth calling, calls beat holds in every family at margins ≥ 15%; at 10%, 2 of 10,504 orders have a sliver below the 13.7% operating cutoff (notebook 02 §10e, corrected in Phase 5, `evidence/margin_crossover_15pct.csv`). Phase 5 still states the assumption used for ₹ totals | Not in the pack |
| **Margin used for ₹ totals** | **25% of order value** (stated assumption; 15% / 35% sensitivity). The call-vs-hold conclusion holds at every margin tested | Phase 5 (`notebooks/04_decision_economics.ipynb`) |
| Headline call value | **Conservative**: the margin a prevented return keeps is *not* counted (counting it makes calls ~5× more valuable) | Phase 5 |
| Model cost per order | **₹0** (local model, local reasons, no API) | Farhan's condition |

## 7. Decision rules

*Set in Phase 5 (2026-10-06) on the walk-forward out-of-fold predictions (holdout not used); stored in `models/model_meta.json` → `decision`.*

| Rule | Value | Evidence |
|---|---|---|
| **Action** | **Call** orders whose calibrated risk is at or above the cutoff for the chosen capacity. **Never hold.** | A hold is never better than a call for any order; holding the top 10% loses ~₹10,400/month vs calling it +₹8,300 |
| **Default capacity** | **Top 25% of orders → risk cutoff 13.7%** (~6 calls/day at the export's ~700 orders/month) | Declared rule: largest top-X% whose marginal band is still net-positive (band 25–30% precision 10.0% < 11.2% break-even) |
| Capacity options | top 5% → 35.8% · 10% → 24.7% · 15% → 19.4% · 20% → 16.0% · 30% → 11.8% | Ritu's team picks X; smaller X keep the highest return per call |
| Floor | Never call below the conservative break-even (11.2% at ₹1,150) | Test `test_saved_decision_is_consistent` |
| At ₹600 per return | Same rule gives top 15% (still net-positive) | Sensitivity |
| Robustness | At top 25%, calls beat holds in **18/18** scenarios (return ₹600/₹1,150 × prevention 25/35/45% × margin 15/25/35%); call net-positive in 15/18 (negatives: ₹600 with 25% prevention) | Notebook 04 §4 |

## 8. Shield rule

**"Call, don't hold" applies to everyone; Shield is one more reason never to hold.** A risk model flags Shield members at about twice their share (42–49% of flagged orders vs 22% of all orders) without bias: flagged Shield and non-Shield orders return at similar rates (29.6% vs 25.7% at top 25%). Holding them would cancel ~9 Shield orders a month from the highest-lifetime-value segment; a call puts no order at risk.

## 9. Model governance

*Set in Phase 6 (2026-10-06) from the error analysis (`evidence/backtest_report.md`).*

| Item | Rule |
|---|---|
| Retraining | Quarterly, with `python -m kestrel.train` on the latest export (same rules: dedupe, paise check, banned columns). Re-run notebooks 01–05; a new holdout quarter is scored once per release |
| Monthly monitoring | **Performance monitors run only on orders at least 30 days old**, so returns have settled (in the data every reverse pickup was booked within 20 days of the order; Shield's free-return window is 30 days). (1) ROC-AUC on those orders (expected 0.74–0.82); (2) predicted vs actual return rate (expected within ±3 pts); (3) share of new orders at or above the 13.7% cutoff, which can be checked immediately (expected 22–28%); (4) **measured call-prevention rate from the pilot**: return rate of called orders vs a matched uncalled control group at the same risk, compared with the 35% assumed (the least certain input) |
| Review triggers | Measured prevention below ~15% (at the top-25% operating point, 27.3% of called orders would return, so calls stop paying at ₹1,150 below 45 ÷ (0.273 × 1,150) = 14.3% prevention; 27.4% at ₹600); monthly AUC < 0.72 two months running; calibration gap > 3 pts two months running; called share outside 18–32%; any change to the export's columns or the payment gateway |
| Data feed asks | Shield status **as of the order** (removes the snapshot risk); service status as of dispatch or the full event history, never only the latest event; Oct-2025 paise values fixed at source |
| Known limitations to revisit with more data | Gift under-prediction (−7.2 pts, ~₹260/month); channel (partner +2.7 / marketplace −2.2 pts); robot vacuums −3.4 pts; customers with no CRM history (AUC 0.745) |
| The 35% call-prevention rate | Re-estimate from the controlled pilot before scaling up; the cutoff and capacity rule are recomputed with the measured rate |
