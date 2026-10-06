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
- Spring 2026 return rates show no dip (Mar–May: 11.2% / 12.0% / 11.2%).

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

## Plan changes

_None so far. Plan v2 locked 2026-10-06._
