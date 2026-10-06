# Predictions check (Phase 7)

Model: `models/model.joblib` (version 2026-10-06), trained Apr 2025 – Jun 2026. File: `outputs/predictions.csv` (order_id, score).

| Check | Result |
|---|---|
| rows == 2,096 | PASS |
| one row per order_id | PASS |
| same IDs and order as sample_submission | PASS |
| no NaN | PASS |
| scores in [0, 1] | PASS |
| no fallbacks needed | PASS |

## File fingerprint

SHA-256 of `outputs/predictions.csv`: `e9fd178769fd391fae978b56cf7ed67c1521bd4b73aa7315e37311ed4ab7092d`

If the submitted file gives the same SHA-256, it is byte-for-byte the file these checks were run on. Any change, including opening and re-saving it in Excel, gives a different value. Verify with:

- Windows (PowerShell): `Get-FileHash outputs\predictions.csv -Algorithm SHA256`
- macOS: `shasum -a 256 outputs/predictions.csv`
- Linux: `sha256sum outputs/predictions.csv`

## Score distribution: test vs walk-forward out-of-fold

|  | test (Jul-Sep 2026) | walk-forward OOF |
|---|---|---|
| p5 | 0.0172 | 0.0171 |
| p25 | 0.0376 | 0.037 |
| p50 | 0.0721 | 0.0701 |
| p75 | 0.139 | 0.1365 |
| p90 | 0.261 | 0.2464 |
| p95 | 0.3759 | 0.3577 |
| mean | 0.1156 | 0.1117 |

Kolmogorov–Smirnov distance 0.017 (p = 0.72). Mean predicted return rate on test: **11.6%** (training return rate 11.4%).

## Share at or above the 13.7% call cutoff

- **25.5%** of test orders (vs the **25%** assumed in Phase 5): 535 orders over 92 days = **5.8 calls/day**.

| month | orders | share_called | calls_per_day | mean_score |
|---|---|---|---|---|
| 2026-07 | 668 | 0.243 | 5.226 | 0.116 |
| 2026-08 | 733 | 0.258 | 6.097 | 0.113 |
| 2026-09 | 695 | 0.265 | 6.133 | 0.118 |
