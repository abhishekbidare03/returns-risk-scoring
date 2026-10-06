# Clean-machine test (Phase 8, 2026-10-06)

**Goal:** prove the service starts from the README alone, without `data/`, `outputs/`, an existing virtual environment, an API key or network services beyond `pip`.

## Setup
- Copied only what a fresh clone contains (`git ls-files --cached --others --exclude-standard`) into a new folder. Checked: **no `data/`, no `outputs/`, no `.venv`, no `logs.md`**. The only CSV present is `evidence/margin_crossover_15pct.csv` (aggregates).
- Used **Python 3.13.5** (`py -3.13`), a different interpreter from the 3.12 used for development, to test portability.
- Followed the README's Windows commands exactly.

## Attempt 1: failed, fixed
`pip install -r requirements.txt` stopped with `OSError: [Errno 2] No such file or directory: …\.venv\Lib\site-packages\jupyterlab\galata\…` and pip's hint about **Windows long-path support**. JupyterLab ships files whose full path exceeds Windows' default 260-character limit when the project sits in a deep folder. The service doesn't need Jupyter.

**Fix:** `requirements.txt` now holds only what the service, training and tests need (numpy, pandas, scikit-learn, scipy, joblib, fastapi, uvicorn, pydantic, pytest, httpx, and the project via `-e .`). `requirements-dev.txt` adds matplotlib + Jupyter for the notebooks, with a note about long paths. Also found: the pinned numpy 2.5 / scipy 1.18 need **Python ≥ 3.12**, so the README says "3.12 or 3.13" (not 3.11), and `pyproject.toml` says `requires-python >= 3.12`.

## Attempt 2: passed (fresh copy, fresh venv)
| Step | Result |
|---|---|
| `py -3.13 -m venv .venv` | OK |
| `.venv\Scripts\python -m pip install -r requirements.txt` | **OK in 107 s**, exit 0, venv 363 MB |
| `.venv\Scripts\python -m uvicorn app.main:app --port 8000` | Started; loads only `models/model.joblib` + `models/model_meta.json` |
| `GET /health` | 200, model 2026-10-06, `"llm": "none"`, `"external_api": "none"` |
| `GET /` (the screen) | 200 |
| `GET /samples` | 200, 7 synthetic orders |
| `POST /score` (sample 1) | 200, probability **0.8447**, identical to the development machine (Python 3.12) |
| `POST /score` with `payment_mode: "upi"` | 422, allowed values listed |
| Screen in headless Microsoft Edge, samples 3, 5, 6, 7 | Renders: probability, band, "× typical", CALL/SHIP + note, ₹ call value, reasons, fallback notice. Light and dark themes; phone width (500 px) without overflow |
| `python -m pytest` inside the clean copy | **93 passed, 9 skipped** (the 9 need `data/` and skip as designed) |
| Server log | 10 `POST /score` lines with **path and status only**: no request bodies logged |

Screenshots: `figures/08_screen_call.png` (light, CALL), `figures/08_screen_fallback.png` (dark, Shield unknown), `figures/08_screen_mobile.png` (phone width).

**Not tested here:** macOS/Linux (no such machine available). The commands are standard (`python3 -m venv`, `source .venv/bin/activate`), and every dependency is a pure wheel published for macOS and Linux.
