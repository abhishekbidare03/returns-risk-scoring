# Kestrel Home: pre-dispatch returns risk

Scores each order **before dispatch** for its chance of being returned, and recommends one of two actions:
**CALL** (a ₹45 confirmation call) for the riskiest ~25% of orders, or **SHIP** as normal. Orders are never held.
Runs entirely on your machine: no API key, no external service, no AI model in the product.

| Deliverable | Where |
|---|---|
| Predictions for `test_unlabelled.csv` | `outputs/predictions.csv` (created by `python -m kestrel.predict`; not in git, delivered with the submission) |
| Working service: one endpoint + one screen | `app/` (this README) |
| Evidence that it works, and how often it doesn't | `evidence/backtest_report.md`, `evidence/predictions_check.md`, `notebooks/` |
| Memo to Ritu | `memo.md` (Phase 9) |
| Decisions and rules | `key_findings.md` (what we found and decided, phase by phase), `policy.md` (rules), `plan.md` |

---

## Run the service

Needs **Python 3.12 or 3.13** (the pinned numpy 2.5 / scipy 1.18 don't support 3.11). Run the commands from the repository folder. Nothing from `data/` is needed to run the service.

### Windows (PowerShell or Command Prompt)

```
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --port 8000
```

(If `py -3.12` isn't available, use any Python 3.12/3.13, e.g. `python -m venv .venv`. Calling `.venv\Scripts\python` directly avoids PowerShell's activation-script policy.)

### macOS / Linux

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

Then open **http://localhost:8000**. Pick a sample order (synthetic) or type one in, and press **Score order**. `http://localhost:8000/?sample=1` opens sample 1 directly. API docs: http://localhost:8000/docs.

`pip install -r requirements.txt` installs only what the service and tests need, plus this project's code (`src/kestrel`, via `-e .`). No compiler is needed.

---

## The endpoint

`POST /score`: one order as JSON. Seven fields (only these are used):

| Field | Required | Values |
|---|---|---|
| `sku` | yes | Kestrel SKU, e.g. `KH-AF-01` |
| `payment_mode` | no | `cod`, `emi`, `prepaid_card`, `prepaid_upi`, `unknown` |
| `promised_delivery_days` | yes | integer 1–60 |
| `discount_pct` | yes | 0–100 |
| `customer_prior_orders` | yes | integer ≥ 0 |
| `customer_prior_returns` | yes | integer, ≤ prior orders |
| `shield_member` | no | `Y`, `N`, `unknown` |
| `order_id` | no | echoed back |

```
curl -X POST http://localhost:8000/score -H "Content-Type: application/json" -d "{\"sku\":\"KH-RV-02\",\"payment_mode\":\"cod\",\"promised_delivery_days\":8,\"discount_pct\":18,\"customer_prior_orders\":3,\"customer_prior_returns\":1,\"shield_member\":\"Y\"}"
```

Returns the return probability, a risk band (**Low** < 7%, **Medium** 7–13.7%, **High** ≥ 13.7%), how it compares with a typical order, **CALL / SHIP**, the expected ₹ value of calling, 2–3 reasons raising the risk and 1 lowering it, and the model version.

- **Missing or invalid required fields** → HTTP 422 naming the field. A typo in a category (e.g. `"upi"`) → 422 listing the allowed values.
- **Unknown Shield status or payment mode** (missing or `"unknown"`), or an **unknown SKU** → still scored, using the training-average for that field, and listed in `fallbacks_used`.
- **Any other field** (delivery notes, pincode, post-dispatch columns, …) → ignored, listed by name in `ignored_fields`. Values are never echoed back.
- The service doesn't log or store request bodies. `GET /health` shows the model version, cutoff and validation scores.

---

## Retrain, re-score and reproduce (needs the data pack)

Put the pack files in `data/` (`train.csv`, `test_unlabelled.csv`, `customers.csv`, `products.csv`, `sample_submission.csv`), then:

```
python -m pytest                    # 102 tests; data-dependent ones are skipped without data/
python -m kestrel.train             # rebuilds models/model.joblib + model_meta.json (identical model)
python -m kestrel.predict           # writes outputs/predictions.csv + evidence/predictions_check.md
```

(On Windows prefix with `.venv\Scripts\`, e.g. `.venv\Scripts\python -m pytest`.)

The notebooks need the extra packages in `requirements-dev.txt` (`pip install -r requirements-dev.txt`; Jupyter + matplotlib). On Windows, JupyterLab may need [long-path support](https://pip.pypa.io/warnings/enable-long-paths) if the project sits in a deep folder; the service doesn't. The analysis is in `notebooks/` and is meant to be read in order: 01 data audit → 02 exploration → 03 model selection → 03b one-time holdout (**read it, don't re-run it**) → 04 rupee economics → 05 error analysis.

---

## What's inside

```
app/            FastAPI service (main.py), the screen (static/index.html), synthetic samples (samples.json)
src/kestrel/    data cleaning, features, model, training, economics, reasons, scoring service, predictions
models/         model.joblib (4.6 KB logistic regression) + model_meta.json (config, metrics, product catalogue, decision rule)
notebooks/      the analysis, phase by phase
evidence/       backtest report, predictions check, figures
tests/          102 tests: cleaning, leakage guard, features, model, economics, API, predictions
```

**Data handling (ops-policy §10):** `data/` and every CSV with order rows are git-ignored. The service, screen and samples contain no customer data. Sample orders are synthetic.
