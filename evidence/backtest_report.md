# Backtest report: does it work, and how often does it not?

**Model:** logistic regression on 9 dispatch-time fields (promised delivery days, customer's prior returns / prior orders / return rate / has-returned, discount, Shield, payment mode, product family), sigmoid-calibrated.
**Action:** call orders with predicted return risk **≥ 13.7%** (≈ the riskiest 25%); never hold.
**How it was tested:** every number below comes from orders the model **had not seen**: three walk-forward quarters (train on the past, score the next quarter) plus one holdout quarter scored **exactly once** after all choices were frozen. Details: `notebooks/03_modeling.ipynb`, `03b_holdout_and_final.ipynb`, `04_decision_economics.ipynb`, `05_error_analysis.ipynb`.

---

## 1. It works: ranking quality on unseen quarters

| Quarter (unseen) | Orders | Return rate | ROC-AUC | PR-AUC | Of the top 10% risk, returned | Share of all returns in the top 20% |
|---|---|---|---|---|---|---|
| Jul–Sep 2025 | 2,157 | 11.1% | 0.800 | 0.419 | 46% | 57% |
| Oct–Dec 2025 | 2,082 | 10.8% | 0.770 | 0.344 | 37% | 56% |
| Jan–Mar 2026 | 2,126 | 11.6% | 0.766 | 0.376 | 40% | 53% |
| **Apr–Jun 2026 (holdout, scored once)** | 2,126 | 11.5% | **0.787** | **0.421** | **44%** | **58%** |

- Monthly ROC-AUC across the nine walk-forward months: **0.741–0.821** (sd 0.029), no downward drift.

**Model ladder** (walk-forward ROC-AUC, Jul–Sep 25 / Oct–Dec 25 / Jan–Mar 26; every step had to beat the previous one by ≥ 0.005 on ≥ 2 of 3 quarters, with rules fixed before running):

| Step | ROC-AUC per quarter | Mean | Mean PR-AUC | Outcome |
|---|---|---|---|---|
| Base rate (same score for every order) | 0.500 / 0.500 / 0.500 | 0.500 | 0.112 | Floor |
| Rule: lookup of prior returns × Shield | 0.673 / 0.649 / 0.658 | 0.660 | 0.228 | The "spreadsheet" bar |
| **Logistic regression, 9 features** | **0.800 / 0.770 / 0.766** | **0.778** | **0.380** | **Shipped** |
| Gradient boosting (HGB), default | 0.727 / 0.732 / 0.723 | 0.727 | 0.290 | Overfits at ~10k orders |
| HGB, monotonic constraints + tuned (best of 24) | 0.786 / 0.760 / 0.762 | 0.769 | 0.342 | Worse than LR on every quarter → rejected (needed > +0.01) |
| LR + any of 10 candidate fields (gift, location, channel, notes, …) | best: gift +0.005 / −0.001 / +0.004 | ≤ 0.781 | - | None passed the rule |
- **Calibrated:** risk deciles run from 1.7% to 40.6% predicted vs 1.3% to 40.7% actual on the walk-forward folds; on the holdout, 11.0% predicted vs 11.5% actual overall, and 40.2% vs 43.7% in the top decile (`figures/03_calibration_oof.png`, `03b_calibration_holdout.png`).

**Expected score on the test quarter (Jul–Sep 2026): ROC-AUC 0.77–0.80** (point estimate ~0.78), **PR-AUC 0.34–0.42** at an ~11% return rate. Why this range:
- it spans all four unseen quarters (three walk-forward + the holdout), including **Jul–Sep 2025, the same season a year earlier (0.800)**;
- the holdout (0.787), scored once after every choice was frozen, sits inside the walk-forward range, so selection didn't inflate the estimate;
- the test quarter looks like training on every model input (population stability index < 0.012 for every field; Shield share 22.1% vs 22.2%), and its scores look like the walk-forward scores (`predictions_check.md`);
- PR-AUC moves with the quarter's return rate (about 3.2–3.8× it), hence the wider range;
- downside risks: more customers without CRM history (the weakest segment), a shift in Shield status, or a season effect one year of history can't show.

## 2. Why "95% accuracy" was never the right bar, measured

- A model that predicts "nobody returns" is **88.4–88.6% accurate**. Ours is 89.4% accurate at a 0.5 threshold, which says almost nothing about its value.
- **Leak simulation** (Jan–Mar 2026 quarter, `03_modeling.ipynb` §8): the same model types trained **with** the two post-dispatch columns (service event, pickup date), then scored on the data as exported vs on what the warehouse actually sees at dispatch (no pickup; `INSTALL_BOOKED` for fans/vacuums/purifiers, `NONE` otherwise):

| Model | AUC as exported | Accuracy as exported | **AUC at dispatch (real use)** | Orders flagged at 0.5, at dispatch |
|---|---|---|---|---|
| LR + leaky columns | 0.997 | 99.3% | **0.711** | 0.05% |
| HGB + leaky columns | 0.995 | 99.3% | **0.681** | 0.05% |
| **Honest model (shipped)** | - | - | **0.766** | - |

The leaky model *looks* like the "95%+" that was promised, then does worse than the honest model in real use, because those columns record the return after it happens. ("Nobody returns" scores 88.4% accuracy on this quarter.)

## 3. How often it is wrong, at the operating point

Per month, at the export's volume (~700 orders), from the walk-forward folds:

| | Returned | Kept |
|---|---|---|
| **Called** (risk ≥ 13.7%), ~175/month | **~48** (27%) | **~127 false alarms** (73%) |
| Shipped without a call, ~525/month | ~30 missed returns | ~494 |

- **73% of calls are false alarms.** Each costs ₹45 and a courtesy call, already counted in the net figure (~₹5,700/month). This is acceptable *only because the action is a call*. Under a hold, each would carry a 12% cancellation risk, which is why holding the top 10% loses ~₹10,400/month while calling it earns ~₹8,300.
- **39% of returns (~30/month) are not flagged.** They are handled exactly as today; the model adds no cost there.
- **10% of returns get a risk below 5%** (cheap, prepaid orders from customers with no prior returns). These orders look like the lowest-risk orders on every field available at dispatch, so no model using this data can separate them.
- **Value at this operating point:** ~16.7 returns avoided/month, **~₹11,400/month net (₹16,300 per 1,000 orders)**, conservative (`04_decision_economics.ipynb`).

## 4. Where it is weaker (segments, walk-forward folds)

| Segment | ROC-AUC [95% interval] | Note |
|---|---|---|
| All orders | 0.778 | - |
| Customer **new to the model** / seen in training | 0.781 / 0.771 | No weakness for new customers: the model uses CRM history, not identity |
| **No CRM history** (`prior_orders = 0`, 28% of orders) | **0.745** [0.704, 0.784] | Weakest group; catches only **46%** of its returns at the cutoff (vs 66% with history) |
| Shield / not Shield | 0.764 / 0.767 | Same quality and calibration; Shield is called more because it returns ~2× more |
| Room heater / robot vacuum | 0.724 / 0.726 | Weakest families; robot vacuums **under-predicted by 3.4 pts** (rising return rate) |
| Ceiling fan / partner outlet | 0.828 / 0.831 | Strongest |

Chart: `figures/05_segment_auc.png`.

## 5. Known limitations

1. **Gift orders are under-predicted by 7.2 points** (10.5% predicted vs 17.7% actual, walk-forward folds). The gift flag missed the pre-declared selection bar by a hair (+0.005 / −0.001 / +0.004 AUC). Rough cost: ~10 gift orders/month that a gift-aware score would call, worth **~₹260/month**, about 2% of the policy's value. Cheap to add later.
2. **Channel is not in the model:** partner-outlet orders over-predicted by 2.7 pts, marketplace under-predicted by 2.2 pts (channel improved AUC on only 1 of 3 folds).
3. **Shield comes from a snapshot table** (`customers.csv` may show today's status, not the status at order time). Removing it costs 0.009–0.021 AUC on every fold, so the model relies on it. If the warehouse feed passes Shield status as of the order, this risk goes away.
4. **The 35% call-prevention rate is the least certain input** (one spring pilot; no dip visible in the data). The ₹ figures scale with it: at 25% the top-25% call policy still nets ~₹5,900/month; at ₹600 per return *and* 25% prevention it turns slightly negative. Hence a controlled pilot first.
5. **The ₹ check on the holdout was skipped.** It needed the Apr–Jun predictions from the single holdout run, which were kept in memory only (aggregates were saved); the holdout notebook is not re-run by rule. The ₹ figures rest on the walk-forward folds.
6. **History coefficients:** the negative coefficient on prior return rate (and the near-zero one on prior orders) is **collinearity among the four customer-history features, not an error**. They move together, so individually they aren't interpretable, which is why the service merges them into one "customer history" reason.
7. Fold models were trained on 3–9 months; the shipped model uses 15. Walk-forward figures are, if anything, slightly pessimistic.

## 6. Automated checks

`python -m pytest`: **76 passed**:
- **Cleaning rules** on the real pack: dedupe → 10,504 orders, Oct-2025 paise fix, dates, IDs match the sample submission.
- **Leakage guard:** no banned column is an input or a feature. Injecting `REVERSE_PICKUP`, a pickup date or the label leaves the features unchanged. The feature code reads no files.
- **Privacy:** gate-code digits and free text never survive into the features.
- **Train/serve parity:** 150 orders scored one at a time equal the batch scores.
- **Unknown values:** an unknown Shield, payment mode or family scores strictly between its known versions (Shield = the exact 22/78 weighted average) and is reported as a fallback.
- **Economics:** formulas, break-evens (11.2%, 21.4%), "calls beat holds" (true accounting, margin ≥ 15%; conservative accounting at the 13.7% cutoff), and the stored decision never calls below break-even.

## 7. Reproduce

```
pip install -r requirements.txt          # Python 3.11/3.12
python -m pytest                         # 76 tests (data-dependent ones skip without data/)
python -m kestrel.train                  # retrain from data/ -> identical models/model.joblib
cd notebooks && jupyter nbconvert --to notebook --execute --inplace 01_data_audit.ipynb 02_eda.ipynb 03_modeling.ipynb 04_decision_economics.ipynb 05_error_analysis.ipynb
# 03b_holdout_and_final.ipynb is the one-time holdout run - read it, don't re-execute it
```
