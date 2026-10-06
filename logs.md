# Work Log

> Chronological record of what was done, by whom (user / Claude), and which files changed.
> Findings and decisions live in `key_findings.md`; this file is the activity trail (also feeds the "What you used / what you discarded" section of the submission form).

---

## 2026-10-05

| # | Who | What | Files |
|---|---|---|---|
| 1 | User | Shared task brief and data pack; wrote their own first reading of README + email thread | - |
| 2 | Claude | Read README, email thread, ops-policy.pdf, all CSV heads | `data/*` (read only) |
| 3 | Claude | Exploratory checks with throwaway scripts (in session scratchpad, not in repo): date ranges, leakage crosstabs, duplicates, order-value ratio by month, pincode, prior returns, Shield, timestamps, quick baseline + leaky model | scratchpad `eda1–5.py` (discarded; formal version → Phase 1 notebook) |
| 4 | Claude | Reviewed the user's 10-point reading against the data: ~70% confirmed; corrected test period (Jul–Sep 2026, not Oct), paise bug location (train Oct 2025), pincode stored as `0`; added PDF items (§9 CRM/UTC, §7 cancelled pickups, §10 data handling) | - |
| 5 | Claude | Wrote solution plan v1 | `plan.md` |

## 2026-10-06

| # | Who | What | Files |
|---|---|---|---|
| 6 | User | Shared an external review of plan v1 | - |
| 7 | Claude | Assessed the review: ~90% right; nuances on §10 wording, isotonic ties, label-free leak evidence; spring pilot answered from data | - |
| 8 | User + Claude | Applied the review's corrections → plan v2, **locked**. Saved "plan locked" rule to Claude memory | `plan.md` |
| 9 | Claude | **Phase 0:** created folder structure (`notebooks/ src/kestrel/ app/static/ models/ outputs/ evidence/figures/ tests/`) | dirs |
| 10 | Claude | Phase 0: created `.venv` (Python 3.12.3), installed and pinned dependencies | `requirements.txt` |
| 11 | Claude | Phase 0: made `src/kestrel` an installable package (`-e .` in requirements) | `pyproject.toml`, `src/kestrel/__init__.py`, `tests/__init__.py` |
| 12 | Claude | Phase 0: `.gitignore` (data/, all CSVs, venv, caches); `git init` (no commits yet); verified with `git check-ignore` | `.gitignore` |
| 13 | Claude | Phase 0: registered Jupyter kernel "Python (kestrel)" | user kernelspec |
| 14 | Claude | Phase 0: created skeletons for `policy.md`, `key_findings.md` (pre-work + Phase 0 entries), and this log | `policy.md`, `key_findings.md`, `logs.md` |

### AI tools used so far
- Claude Code (Claude Opus 5.5): data reading, exploration, plan writing, setup. Cost: _user to fill in (plan/usage from their account)_.
- No model API inside the product.
