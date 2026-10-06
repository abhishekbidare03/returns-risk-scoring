# Kestrel Home: Returns Risk (Variant A) - Solution Plan

> **Status: LOCKED (v2, 2026-10-06).** This plan changes only if the data contradicts it. Any such change is logged in `key_findings.md` (what changed, the evidence, why) and marked here with a dated note.
>
> Working plan for the 48-hour task. It covers how we approach the problem, in what order, with which stack, and why.
> Two companion documents grow as we go:
> - **`policy.md`**: the rules we commit to (data, leakage, cleaning, costs, decisions). Written in Phase 1, updated only when a rule changes.
> - **`key_findings.md`**: a running log of what each phase found, what we decided and which alternatives we rejected.

---

## 0. The problem in one paragraph

Ritu wants a model that flags orders likely to be returned before dispatch, at "95% accuracy", so she can hold them.
The pack shows that this exact framing is unworkable:

- The base return rate is ~11.4%, so "nobody returns" already scores ~88.5% accuracy.
- The only way to reach 95%+ is to use columns that record the return after it happened (leakage).
- Holding an order doesn't prevent a return. It only causes 12% of customers to cancel.
- A ₹45 confirmation call prevents 35% of returns.

**Calls beat holds whenever the margin lost on a cancelled good order exceeds ₹375 (₹45 ÷ 0.12).** This holds even after counting the margin kept on prevented returns.

**The real deliverable is a pre-dispatch risk score plus a rupee-based action policy (call the top X% the team can handle; don't hold).** That policy should be honest about accuracy, protect Shield customers, and run fully offline at ₹0 per order.

What the graders value most is **approach and judgement**, then a small system that works. Every phase below produces evidence for that.

---

## 1. Guiding principles (these drive every decision)

1. **Dispatch-time truth only.** A feature is allowed only if it exists in the warehouse snapshot at dispatch (`test_unlabelled.csv`). If train and test disagree on a column's meaning, the column is out.
2. **Validate like we'll be scored.** Use a time-based split (train on the past, test on the future), never a random split. The test set is Jul–Sep 2026, after all training data.
3. **Rupees over accuracy.** Model quality is measured with ROC-AUC / PR-AUC / calibration. Business value is measured in ₹ net savings at a chosen action threshold.
4. **Offline, free, reproducible.** No paid API. Everything runs from the README on a clean machine with `pip install` + one command.
5. **Small and running beats large and broken.** Add complexity only if it measurably wins in validation.
6. **Decide, write it down, explain why.** Each ambiguity gets a line in `policy.md` (the rule) and in `key_findings.md` (the evidence and the alternatives).
7. **Data handling (ops-policy §10).** No public repo, and nothing shared beyond the engagement team. Returning the submission to the client is fine. `data/` is git-ignored. The service never reads `data/` at runtime. Gate codes and notes are masked on screen, and sample orders are synthetic.

---

## 2. Recommended stack, and why

| Layer | Choice | Why this | Alternatives considered |
|---|---|---|---|
| Language | **Python 3.11/3.12** | Standard for tabular ML; already installed | R (weaker for the service part) |
| Data | **pandas** | Small data (~13k rows), so nothing heavier is needed | polars / DuckDB (overkill here) |
| Models | **scikit-learn**: `LogisticRegression` + `HistGradientBoostingClassifier` | Pure pip wheels, no compiler, installs cleanly on any OS. HGB handles categoricals and missing values natively and is on par with LightGBM at this size | LightGBM/XGBoost (extra dependency, little gain on 10k rows); CatBoost (heavy); deep learning / TabNet (no benefit on small tabular data, hard to explain) |
| Calibration | **Sigmoid (Platt)**, fitted on the walk-forward out-of-fold predictions, then applied to the model retrained on all data | ₹ thresholds need real probabilities. Sigmoid is stable with ~260 validation returns and is strictly monotonic, so AUC is unchanged | Isotonic (jumpy with few positives; creates ties that can shift AUC); `CalibratedClassifierCV` with random folds (ignores time order) |
| Explanations / reasons | **Local, deterministic reason codes.** LR: coefficient × value. HGB: swap each feature to a typical value and measure the score drop. Top contributions are mapped to plain-English templates | ₹0 per order, works offline, auditable, **no `shap` dependency**, answers Farhan's "no per-order model bill" | `shap` (extra dependency, uncertain HGB support); LLM-written reasons (cost per call, needs a key, can hallucinate) |
| Notebooks | **Jupyter** (`.ipynb`) | Visible analysis trail for graders | Scripts only (less readable evidence) |
| API | **FastAPI + Uvicorn** | One file, automatic JSON validation via Pydantic, free `/docs` page, one-command start | Flask (manual validation); Streamlit (no clean JSON endpoint, so it fails the "one endpoint" requirement on its own) |
| Screen | **Single static `index.html` + vanilla JS**, served by FastAPI | No Node or build step. Same process and port as the API, so a clean-machine start is trivial | React/Vite (build tooling = more ways to fail on a clean machine); Streamlit (second process) |
| Model artifact | `joblib` + `model_meta.json` (features, threshold, version, validation metrics, calibrator params, **embedded 21-row product catalogue**) | Simple, versioned, inspectable. The service needs nothing from `data/` | MLflow (overkill) |
| Tests / evidence | **pytest** (data rules, leakage guard, API contract, no-`data/` start) + generated backtest report | "Evidence that it works, and how often it does not" | Manual screenshots only |
| Packaging | `requirements.txt` (pinned) + `venv`; optional `Dockerfile` | A clean machine needs only Python | Conda env (heavier); Docker-only (not every grader has Docker) |

**The final model is chosen by evidence, not up front.** If logistic regression is within ~0.01 AUC of gradient boosting, we ship LR: simpler, better calibrated and directly explainable. Otherwise we ship HGB with swap-based reasons.

---

## 3. Target project structure

```
Task2/
├── plan.md                    # this file (locked)
├── policy.md                  # rules: data, leakage, cleaning, costs, decisions (Phase 1)
├── key_findings.md            # running log: results, decisions, alternatives (every phase)
├── README.md                  # clean-machine setup + run instructions
├── memo.md  (+ memo.pdf)      # one-page, non-technical memo to Ritu
├── submission-form.md         # completed submission form
├── requirements.txt
├── .gitignore                 # data/, .venv/, any file with raw customer rows
│
├── data/                      # provided pack - never committed; needed ONLY for retraining
│
├── notebooks/
│   ├── 01_data_audit.ipynb        # integrity, leakage, duplicates, value bugs
│   ├── 02_eda.ipynb               # drivers of returns, segments, stability over time
│   ├── 03_modeling.ipynb          # baselines → LR → HGB, time-based validation, leak simulation
│   ├── 04_decision_economics.ipynb# ₹ policy: call / hold / ship, margin & capacity sensitivity
│   └── 05_error_analysis.ipynb    # where and how often it is wrong
│
├── src/kestrel/
│   ├── config.py              # paths, costs (₹1,150 / ₹45 / 12% / 35%), allowed columns
│   ├── data.py                # load + clean (dedupe, paise fix, pincode, Excel artifacts)
│   ├── features.py            # dispatch-time feature builder (shared by train AND API)
│   ├── train.py               # trains, calibrates (sigmoid on OOF), saves model + metadata
│   ├── predict.py             # batch scoring → outputs/predictions.csv
│   ├── economics.py           # expected ₹ value per action, thresholds, capacity table
│   └── reasons.py             # contributions → plain-English reason codes
│
├── app/
│   ├── main.py                # FastAPI: POST /score, GET /health, serves the screen
│   ├── samples.json           # SYNTHETIC sample orders (no real rows, no gate codes)
│   └── static/index.html      # the one screen
│
├── models/
│   ├── model.joblib
│   └── model_meta.json        # incl. product catalogue (21 rows) + calibrator params
│
├── outputs/
│   └── predictions.csv        # final submission (order_id, score)
│
├── evidence/
│   ├── backtest_report.md     # metrics, monthly stability, ₹ results, failure rates
│   └── figures/               # PR curve, calibration, lift, ₹ vs threshold
│
└── tests/
    ├── test_data_rules.py     # no leaky columns, dedupe, paise fix, etc.
    ├── test_features.py       # train/serve parity
    └── test_api.py            # endpoint contract, bad input, fallbacks, starts without data/
```

Two key design rules:
1. **`features.py` is the single source of truth.** The training pipeline and the API call the same function, so the model can't see different inputs in production than in training.
2. **The service starts from the repo alone:** `model.joblib` + `model_meta.json` (with the product catalogue) + `samples.json`. It never reads `data/` at runtime.

---

## 4. Phase-by-phase plan

Each phase lists its **goal, steps, outputs**, and **what goes into `key_findings.md`**.
Rough time budget is given out of 48h, leaving buffer for the recording and the form.

---

### Phase 0 - Setup and guardrails (~1h)

**Goal:** a reproducible workspace that respects data handling from minute one.

Steps:
1. Create the folder structure above, a `venv` and a pinned `requirements.txt` (pandas, numpy, scikit-learn, fastapi, uvicorn, pydantic, joblib, matplotlib, jupyter, pytest).
2. `git init` with a `.gitignore` that excludes `data/`, `.venv/` and any file containing raw customer rows. If the code goes on GitHub, the repo is **private** (ops-policy §10).
3. Create empty `policy.md` and `key_findings.md` with their section skeletons.

Output: runnable environment, empty docs.

---

### Phase 1 - Data audit → `policy.md` (~4h)

**Goal:** know exactly what each column means at dispatch time, find every data defect, and write the rules.

Notebook: `01_data_audit.ipynb`

Checks (preliminary results from the first pass are already in brackets; the notebook confirms them formally):

| Check | Method | Status so far |
|---|---|---|
| File parsing | Excel artifacts: empty trailing columns, blank last row, stripped leading zeros | Found: trailing cols, blank last row, pincode `000000` → `0` |
| Dates | Explicit `format="%m/%d/%Y %H:%M"`; count parse failures; confirm day values > 12 appear. **Done before the paise check** so months are right | Only parse failure = the blank Excel row |
| Time ranges | min/max `order_placed_at` per file | Train Apr 2025 – Jun 2026; **test Jul – Sep 2026** |
| Duplicates | `order_id` dup count, column-by-column diff within pairs | 651 dup pairs, all identical incl. label; test has none |
| Order value | `order_value_inr / (list_price × qty × (1 − disc))` by month | **Oct 2025 = exactly ×100 (paise)**; all other months = 1.00; test clean |
| Leakage: service events | crosstab `last_service_event_type × returned`; train vs test distribution | `REVERSE_PICKUP` = 100% returns; `TECH_VISIT` 38%; train has no `INSTALL_BOOKED`, test has only `NONE`/`INSTALL_BOOKED` → **drop** |
| Leakage: pickups | `pickup_scheduled_at` vs returned; test fill rate | 1,191/1,267 returns have a pickup; test has 0 → **drop** |
| Leakage: prior returns | recompute from history; compare train vs test distributions | Looks as-of-order-time (test distribution matches train) → **keep**, document the evidence |
| Leakage: delivery notes | return rate by note template; scan for post-delivery words | Flat across templates, no leakage; contains gate codes → **mask in UI** |
| Pincode default | count `0`, channel mix, return rate | 848 train / 176 test; spread across all channels → `address_missing` flag |
| Customers table | Shield rate, `signup_date` vs order date | 1,999 orders before the customer's own signup date → snapshot table, quality issue; Shield status at order time can't be verified |
| Timezone (§9) | order hour distribution before/after 1 Oct 2025 | No shift in order times; UTC issue only affects resolution events (which we drop) |
| Label sanity | return rate by month | 8–15%, stable; no obvious label drift |

**Output: `policy.md`**, with these sections:
1. **Data handling:** no public repo, nothing beyond the engagement team (returning the submission to the client is fine); `data/` never committed; service never reads `data/`; notes/gate codes masked; samples synthetic.
2. **Cleaning rules:** parse dates with explicit `%m/%d/%Y %H:%M` (the only failure is the blank Excel row, which is dropped); dedupe on `order_id` (copies are identical, keep `crm`); divide Oct 2025 `order_value_inr` by 100; pincode `0` → `address_missing=1`; drop Excel artifact columns.
3. **Allowed features at dispatch:** an explicit allow-list. Everything else is denied by default.
4. **Banned columns and why:** `last_service_event_type`, `pickup_scheduled_at`, `source`, `order_id`, raw `delivery_note` text.
5. **Banned practices:** target-encoding `customer_id`, or any customer statistic computed from training labels (e.g. a customer's return rate in train); random-split validation; tuning on the final holdout.
6. **Cost assumptions:** ₹1,150 per return (policy §4, Finance-owned) with ₹600 as a sensitivity case; call ₹45 with 35% prevention; hold → 12% cancellation; margin assumption for lost orders (set in Phase 5, with sensitivity).
7. **Decision rules:** call the top X% the team can handle; don't hold (finalised in Phase 5).
8. **Shield rule:** "call, don't hold" applies to everyone; Shield is an additional reason never to hold.
9. **Model governance:** retrain cadence, monitoring, and what triggers a review.

**`key_findings.md` entry:** each defect, its evidence (numbers) and the decision taken, plus the alternatives (e.g. "rebuild order value from list price" vs "divide by 100": both give the same result; dividing is simpler and keeps real rounding).

---

### Phase 2 - EDA and insights (~4h)

**Goal:** understand what really drives returns, using only dispatch-time information, and check stability over time.

Notebook: `02_eda.ipynb`

Analyses:
1. **Univariate return rates with counts and confidence intervals** for channel, payment mode, product family/SKU, discount bands, order value bands, gift, qty, promised delivery days, address missing, hour/weekday, pincode region (first 3 digits), prior orders, prior returns, Shield, customer tenure, product age (`launch_date`), warranty months.
2. **Key interactions:** Shield × prior returns; family × channel; COD × discount; gift × family.
3. **Stability over time:** return rate and top drivers by month, plus the festive-season effect (Oct–Nov 2025). Does the Jul–Sep 2025 pattern resemble what test (Jul–Sep 2026) will look like?
4. **Train vs test shift:** compare every feature's distribution (channel, family, Shield share, value, etc.). The model can only be as good as this match.
5. **Order value distribution by family** (median and spread). Feeds the margin decision in Phase 5.
6. **Recording the stakeholders' claims (already answered):**
   - Meenal's claim: **Shield = 36% of returns / 22% of orders, with a ~2× return rate** (18.6% vs 9.4%). "Most returns" is not accurate, but Shield customers do return twice as often.
   - Ritu's "95% accuracy": the all-zero baseline already gets ~88.5%.
   - Spring call pilot: **no visible dip** (Mar–May 2026: 11.2% / 12.0% / 11.2% vs 11.4% overall). We use the policy's 35%. Closed, no longer an open question.

Already known: `customer_prior_returns` is the strongest single signal (0→9%, 1→20%, 2→41%, 3+→61%).

**Output:** 5–8 charts saved to `evidence/figures/`; insights in `key_findings.md`.

---

### Phase 3 - Feature pipeline (~3h)

**Goal:** one leakage-proof feature builder used by training, batch scoring and the API.

`src/kestrel/data.py` + `features.py`:
- **Inputs passed with the order:** `shield_member`, `city`, `state` are fields of the order record, as the warehouse system would pass them, with an `"unknown"` fallback. **Training** joins them from `customers.csv`; **serving** never looks them up.
- **Product details** come from the catalogue embedded in `model_meta.json` (family, list price, warranty, launch date). An unknown SKU falls back to family/global defaults.
- Engineered features (each must be computable from a single JSON record + the embedded catalogue):
  - `prior_return_rate` = prior_returns / max(prior_orders, 1), and `has_prior_return`
  - `effective_discount`, `order_value_clean`, `value_vs_list` ratio
  - `address_missing`, `note_present`, note category (template bucket, never raw text)
  - `hour`, `weekday`, `is_festive_window` (only if Phase 2 shows it matters)
  - `customer_tenure_days`, **guarded**: negative or impossible values (order before signup) are clipped/flagged per `policy.md`
  - `product_age_days` at order time
  - `pincode_region` (first 3 digits, with rare levels grouped)
- **Leakage guard:** an assertion that the feature list ⊆ allow-list in `policy.md`. A unit test fails if a banned column sneaks in.
- **Train/serve parity test:** score test rows through the batch path and through the API path; the scores must match exactly.
- **Snapshot-risk ablation (runs in Phase 4):** with vs without `shield_member` and tenure. Document how much the model relies on them, since both come from a snapshot table.

**`key_findings.md`:** which engineered features help (ablation in Phase 4) and which were dropped.

---

### Phase 4 - Modelling and validation (~6h)

**Goal:** the best honest model, and an honest estimate of how it will score on Jul–Sep 2026.

Notebook: `03_modeling.ipynb`

**Validation design:**
- **Main holdout:** train Apr 2025 – Mar 2026, validate Apr – Jun 2026 (the latest 3 months, closest to test).
- **Walk-forward backtest:** expanding window, 3-month folds (e.g. validate on Oct–Dec, Jan–Mar, Apr–Jun) to show **how stable** the metric is, not just one number. The out-of-fold predictions from these folds also train the calibrator.
- Same-season check: how the model does on Jul–Sep 2025, the season matching test.

**Model ladder** (each must beat the previous one to be kept):
1. Base rate (AUC 0.5): the floor.
2. **Rule baseline:** prior returns + Shield score (preliminary AUC ~0.66). The "a spreadsheet could do this" bar.
3. **Logistic regression** (one-hot + scaled, regularised).
4. **HistGradientBoosting** (preliminary AUC ~0.755, PR-AUC ~0.37).
5. Light tuning (depth, learning rate, iterations, L2) on walk-forward folds only. No tuning on the final holdout.
6. **Calibration:** sigmoid, fitted on walk-forward out-of-fold predictions; checked with reliability curves and Brier score. Not isotonic (too few positives, and its ties can shift AUC).

**Leak simulation (key evidence, replaces the "collapse on test" idea).** Test has no labels, so this is the only way to measure the collapse:
1. Train the same model **with** the leaky columns (`last_service_event_type`, `pickup_scheduled_at`) and score Apr–Jun validation → AUC ~0.998.
2. Set those columns in Apr–Jun to what the warehouse sees at dispatch (`NONE` / `INSTALL_BOOKED` by family as in test, no pickup) and re-score with the same leaky model.
3. Report **AUC before vs after** ("0.998 in testing → X at dispatch"), next to the honest model's AUC.

**Ablations:** drop Shield, drop tenure, drop prior returns, drop engineered features → shows what matters and how much we rely on the snapshot table. Also needed for "what we threw away".

**Metrics reported:** ROC-AUC, PR-AUC, Brier, lift and precision/recall in the top 5% / 10% / 20%, accuracy (only to show why it's misleading), and ₹ value (Phase 5).

**Output:** the chosen model + `model_meta.json`; a validation table in `key_findings.md` covering every model tried, its score, and why it was kept or discarded.

---

### Phase 5 - Decision economics: from score to action (~4h)

**Goal:** turn probabilities into a ₹-optimal, Shield-aware action policy. This answers what Ritu should actually do.

Notebook: `04_decision_economics.ipynb`, code in `src/kestrel/economics.py`

**Per-order expected value**, with p = calibrated return probability, C = ₹1,150, m = margin lost on a cancelled good order:

| Action | Expected saving | Expected cost |
|---|---|---|
| Ship | 0 | 0 |
| **Call** | conservative: 0.35 · p · C ≈ **₹402·p**; true: 0.35 · p · (C + m), because a prevented return also keeps the sale's margin | ₹45 |
| **Hold** | 0.12 · p · C ≈ **₹138·p** (only cancellations avoid a return) | 0.12 · (1−p) · m on good orders, plus handling/delay and goodwill/Shield harm |

- Call break-even: **p > 11.2%** at ₹1,150 using the conservative figure. Because the true saving includes margin, **11.2% is an upper bound** on the real break-even. At ₹600 it is p > 21.4%.
- Call − hold = 264.5·p − 45 + 0.12·(1−p)·m, which is positive for every p **when m > ₹375** (₹45 ÷ 0.12). Holds also carry handling and goodwill costs this sum ignores, so the condition is conservative.

Steps:
1. **Margin assumption (the one open decision, see §5a):** check the median order value overall and by family. Apply 15 / 25 / 35% margin and show what share of orders clear the ₹375 condition. If 15% of a typical order is well above ₹375, "calls beat holds" is safe under any reasonable margin. If cheap families (e.g. fans, small appliances) fall below it, state the conclusion per family; that's worth one line in the memo.
2. Compute net ₹ on the validation set for: ship-all, hold-top-k (Ritu's ask), call-above-threshold, call-top-k.
3. **Capacity table:** the PDF gives no call-capacity figure, so frame the action as **"call the top X% of orders the team can handle"**. Table: calls/day (and % of orders) vs returns prevented vs ₹ saved net. Show where marginal ₹ per call drops below zero.
4. **Sensitivity:** return cost ₹600 vs ₹1,150; prevention 25/35/45%; hold cancellation 12%; margin 15/25/35%.
5. **Shield rule (simplified):** "call, don't hold" applies to everyone. Shield is an extra reason never to hold (free returns, highest lifetime value, Meenal's warning). Report the share of flagged orders that are Shield.
6. **Translate to Ritu's language:** "Of the orders we flag, X% actually come back (vs 11% normally); calling the top Y% saves ₹Z per month net."

**Output:** final decision rules into `policy.md`; ₹ results and alternatives (hold vs call vs hybrid vs do nothing) into `key_findings.md`.

---

### Phase 6 - Error analysis and evidence (~3h)

**Goal:** "Evidence that it works, and how often it does not."

Notebook: `05_error_analysis.ipynb` → `evidence/backtest_report.md`

Contents:
1. **At the chosen capacity cut-off, on unseen months:** confusion matrix in plain words: how many flagged orders were fine (false alarms), how many returns we missed, and their ₹ meaning.
2. **Stability:** metric per month and per walk-forward fold (spread, worst month).
3. **Segment performance:** by family, channel, Shield, new vs repeat customers. Where the model is weak (e.g. first-time customers with no history).
4. **Calibration:** predicted vs actual return rate per score decile.
5. **Failure gallery:** 5–10 concrete orders the model got confidently wrong, and why (anonymised).
6. **Leak simulation result** from Phase 4 (AUC before vs after).
7. **Automated checks:** `pytest` results (data rules, leakage guard, parity, API contract, no-`data/` start).
8. **Expected test score:** **ROC-AUC and PR-AUC, each as a range** from the walk-forward spread (preliminary ROC-AUC ≈ 0.74–0.77). PR-AUC depends on the test period's return rate, so it's stated with that caveat. Also list reasons it could be lower (season shift, Shield mix change, customers new to the test period).

---

### Phase 7 - Final training and `predictions.csv` (~1h)

1. Retrain the chosen configuration on **all** cleaned train data (Apr 2025 – Jun 2026).
2. Apply the **sigmoid calibrator fitted on walk-forward out-of-fold predictions** (no recalibration on in-sample data).
3. Score `test_unlabelled.csv` through the same pipeline → `outputs/predictions.csv`. **Submit the sigmoid-calibrated scores** (identical AUC to raw scores, and consistent with what the API returns).
4. Checks: exactly one row per `order_id`; same IDs and order as `sample_submission.csv`; no NaN; scores in [0,1]; no Excel artifact columns; score distribution compared with validation.
5. Write the **expected ROC-AUC and PR-AUC ranges with reasoning** for the submission form (from Phase 6).

---

### Phase 8 - The service: API + one screen (~5h)

**Goal:** a small thing that runs.

**API (`app/main.py`, FastAPI):**
- `POST /score`: takes one order as JSON and returns the model output plus reasons.
  - Input: dispatch-time order fields, plus **optional `shield_member`, `city`, `state`** (passed with the order, as the warehouse system would). Missing → `"unknown"` fallback. Extra or banned fields (e.g. `pickup_scheduled_at`) are ignored with a warning.
  - Output:
  ```json
  {
    "order_id": "SAMPLE-001",
    "return_probability": 0.27,
    "risk_band": "High",
    "recommended_action": "CALL",
    "expected_value_inr": {"call": 63.6, "hold": -41.0, "ship": 0},
    "reasons": [
      "Customer returned 2 of their last 4 orders",
      "Robot vacuums are returned ~2x more often than average",
      "Order paid by cash on delivery"
    ],
    "shield_member": true,
    "fallbacks_used": [],
    "warnings": [],
    "note": "Don't hold: call instead. Shield member, so holding is especially costly.",
    "model_version": "2026-10-xx"
  }
  ```
  - `fallbacks_used` lists any field that fell back to "unknown"/defaults (e.g. `["shield_member", "sku → family default"]`), so the employee knows the score rests on less information.
  - `recommended_action` reflects "call the top X% the team can handle" (the capacity cut-off from Phase 5), never "hold".
- `GET /health`: model loaded, version, validation metrics.
- `GET /`: serves the screen. `GET /docs`: auto Swagger, free from FastAPI.
- Input validation via Pydantic: clear 422 messages.
- **No model API is used.** If an optional LLM summary is ever added, it is off by default and disabled with a polite message when no key is present. The default build uses no LLM.

**Reasons (`src/kestrel/reasons.py`):** LR → coefficient × value; HGB → swap-to-typical-value score drop. Take the top positive contributions and map them to templates written for an ops employee (no jargon, no raw coefficients). Also include the top "lowering risk" factor, for balance.

**Screen (`app/static/index.html`):**
- Pick a **synthetic** sample from `app/samples.json` (no real rows, no gate codes) or fill the form manually.
- "Score" button → calls `/score` → shows the probability gauge, risk band, recommended action, reasons, ₹ expected value and any fallbacks used.
- Delivery notes are never echoed back raw.

**Tests:** `tests/test_api.py` (valid request, missing field, banned field, unknown SKU, missing `shield_member` → fallback reported, **service starts with `data/` absent**) and the parity test from Phase 3.

**Clean-machine run (README):** needs only the repo: `model.joblib` + `model_meta.json` (with product catalogue) + `samples.json`.
```
python -m venv .venv && .venv\Scripts\activate   (or source .venv/bin/activate)
pip install -r requirements.txt
uvicorn app.main:app --port 8000   # open http://localhost:8000
```
The README says pack files go in `data/` **only for retraining** (`python -m kestrel.train`). We test this in a fresh folder/venv with no `data/` before submitting. Optional `Dockerfile` as a second route.

---

### Phase 9 - One-page memo to Ritu (~2h)

`memo.md` → `memo.pdf`. Non-technical. One page.

1. **The decision:** don't hold flagged orders. **Call the top X% the team can handle.** Holding loses customers (12% cancel) and saves far less than a call.
2. **The number:** "95% accuracy" isn't the right measure (doing nothing scores ~89%). The honest number to take to the board: *"Of the orders we flag, ~X% come back, about 3× the normal rate; calling the top Y% of orders catches ~Z% of all returns."*
3. **The rupees:** net ₹ saved per month at ₹1,150 per return (and at ₹600); cost of the calls; why calls beat holds whenever a lost sale costs more than ₹375 in margin (true for typical Kestrel orders, per Phase 5; one line per family if cheap families differ).
4. **Shield, gently:** Shield customers are 22% of orders and 36% of returns. Not most returns, but they do return about twice as often. Calling them is fine; holding them is not.
5. **Next week:** a 2–4 week controlled pilot. Call the top-risk orders in one group, leave a matched control group alone, and measure returns and ₹.
6. **Ask for Tanmay:** save the service status as it was at dispatch, or keep the full event history (not just the latest event), and fix the Oct 2025 paise values in the source.

---

### Phase 10 - Recording, form, final checks (~3h)

1. **Screen recording (≤3 min, no slides)**, scripted around:
   - *What we tried:* naive model with all columns → 0.998 AUC / 99% "accuracy" → leak simulation drops it to X at dispatch.
   - *What we changed:* dispatch-time features only, data fixes (paise, dedupe, pincode), ₹-based policy instead of accuracy, calls instead of holds.
   - *What we threw away:* leaky columns, accuracy as the metric, holding as the action, isotonic calibration, `shap`, LLM-generated reasons, any model that didn't beat simpler ones.
   - Live demo of the screen calling the endpoint.
2. **`submission-form.md`:** fully filled, including expected ROC-AUC/PR-AUC ranges with reasoning, AI tools used and their cost, what we discarded, and the decisions log (linking `policy.md` / `key_findings.md`). If the form isn't in the pack, we create it covering every item the brief asks for.
3. **Final checklist** (below).

---

## 5. Decisions already taken

| Ambiguity | Decision | Why | Alternative rejected |
|---|---|---|---|
| Service/pickup columns | Drop | Recorded after dispatch; test snapshot has none | Keep only "dispatch-like" values (train has no `INSTALL_BOOKED` to learn from) |
| Duplicate rows | Dedupe on `order_id` | Copies identical incl. label; avoids double-weighting and train/val bleed | Keep both (biases partner orders) |
| Oct 2025 order values | ÷100 | Exactly ×100 in every row | Rebuild from list price (same result, more assumptions) |
| Pincode `0` | `address_missing` flag | It's a system default, not a place | Treat as a region (meaningless) |
| Dates | Explicit `%m/%d/%Y %H:%M` | Excel-saved files; only failure is the blank row | Auto-parsing (risk of D/M swaps) |
| Return cost | ₹1,150 (policy §4, Finance) + ₹600 sensitivity | Official, owned figure | ₹600 (Ritu's informal count) |
| Metric | ROC-AUC / PR-AUC + ₹ net savings | Accuracy is uninformative at 11% base rate | Accuracy (misleading) |
| **Action** | **Call the top X% the team can handle; don't hold anyone** (Shield = extra reason) | Calls beat holds whenever lost margin > ₹375; call capacity unknown | Hold everything flagged (Ritu's ask); "call everyone above 11.2%" (may exceed capacity) |
| **Calibration** | Sigmoid on walk-forward OOF predictions, applied to the all-data model | ~260 validation returns; strictly monotonic, so AUC unchanged | Isotonic (jumpy, ties); recalibrating in-sample |
| **Reasons** | LR: coef × value; HGB: swap-to-typical score drop; plain-English templates | ₹0/order, offline, no extra dependency | `shap`; LLM-written reasons |
| **Leak proof** | Simulate dispatch values on Apr–Jun validation; AUC before vs after | Test has no labels, so it can't be measured there | "Show collapse on test" (not measurable) |
| **Customer data at runtime** | Passed as input with the order (`shield_member`, `city`, `state`), "unknown" fallback; not looked up | Clean-machine start + §10 | Lookup from `customers.csv` (breaks without `data/`) |
| Product data at runtime | 21-row catalogue embedded in `model_meta.json` | No customer data; service needs nothing from `data/` | Reading `products.csv` at runtime |
| Sample orders | Synthetic (`app/samples.json`) | Real rows contain customer IDs and gate codes | Real test rows |
| Validation | Time-based + walk-forward | Test is a future period | Random K-fold (optimistic) |
| Stack | Python + scikit-learn + FastAPI + static HTML | Fewest moving parts on a clean machine | LightGBM / React / Streamlit |

### 5a. One decision still open

**Margin on a cancelled good order.** Neither the pack nor the reviews pin it down. In Phase 5: check the median order value (overall and by family) and apply 15 / 25 / 35%.
- If 15% of a typical order is well above ₹375 → "calls beat holds" is safe under any reasonable margin; say so with confidence.
- If cheap families fall below ₹375 → state the conclusion per family; one line in the memo.

The result and the chosen assumption are logged in `key_findings.md` and `policy.md`.

---

## 6. Risks and how we handle them

| Risk | Mitigation |
|---|---|
| Season shift (test = Jul–Sep 2026; training has only one Jul–Sep) | Same-season backtest; report ranges, not points |
| `customers.csv` is a snapshot (Shield/signup may postdate orders) | Tenure guard; ablation with/without Shield and tenure; document reliance honestly |
| Margin unknown for hold economics | Explicit assumption + 15/25/35% sensitivity; check against the ₹375 condition by family |
| **Unknown call capacity** (not in the PDF) | Frame the action as "top X% the team can handle"; capacity table (calls/day vs ₹ saved) so Ritu picks X |
| **Calibration with only ~260 validation returns** | Sigmoid (2 parameters) instead of isotonic; fit on walk-forward OOF predictions (more positives); reliability curve in evidence |
| Over-engineering the service | Phase 8 time-boxed; core API + screen first, polish last |
| Clean-machine start failure | Pinned requirements, pre-trained model + catalogue shipped, tested in a fresh venv with no `data/` |
| PII exposure | `data/` git-ignored, private repo, synthetic samples, notes masked |

---

## 7. Deliverables checklist (definition of done)

- [ ] `outputs/predictions.csv`: 2,096 rows, one per `order_id`, matches sample shape, sigmoid-calibrated scores in [0,1]
- [ ] Expected ROC-AUC and PR-AUC ranges + reasoning written in the form
- [ ] API: `POST /score` returns score + action + plain-English reasons + fallbacks used
- [ ] Screen calls the endpoint
- [ ] Starts from README on a clean machine, no API key needed
- [ ] **Service starts without `data/`** (tested)
- [ ] **Synthetic samples only**: no real rows or gate codes in the repo or the UI
- [ ] Evidence: `evidence/backtest_report.md` + figures + passing `pytest`
- [ ] **Leak-simulation AUC (before vs after) reported**
- [ ] `memo.md/pdf`: one page, decision / number / rupees / next week
- [ ] Screen recording ≤ 3 min (tried / changed / threw away)
- [ ] `submission-form.md` fully filled (incl. AI tools used, cost, discarded)
- [ ] `policy.md` and `key_findings.md` complete and consistent with the final model

---

## 8. Rough timeline (48h)

| Hours | Phase |
|---|---|
| 0–1 | Phase 0: setup |
| 1–5 | Phase 1: audit → `policy.md` |
| 5–9 | Phase 2: EDA |
| 9–12 | Phase 3: feature pipeline |
| 12–18 | Phase 4: modelling |
| 18–22 | Phase 5: economics |
| 22–25 | Phase 6: evidence |
| 25–26 | Phase 7: predictions |
| 26–31 | Phase 8: service |
| 31–33 | Phase 9: memo |
| 33–36 | Phase 10: recording + form |
| 36–48 | Buffer, clean-machine test, review, rest |

---

## Change log

| Date | Version | Change | Reason / evidence |
|---|---|---|---|
| 2026-10-05 | v1 | Initial plan | First data pass |
| 2026-10-06 | v2 (locked) | Review corrections: ₹375 margin condition, §10 wording, sigmoid OOF calibration, swap-based reasons, synthetic samples, embedded catalogue, runtime inputs for customer fields, leak simulation on validation, capacity framing, Tanmay ask, spring pilot closed | External plan review |

*Any later change: add a row here and a matching entry in `key_findings.md`.*
