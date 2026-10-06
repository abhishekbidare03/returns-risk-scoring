# Kestrel Returns Risk - Policy (the rules we commit to)

> Status: **SKELETON (Phase 0).** Filled in Phase 1 from `notebooks/01_data_audit.ipynb`; decision rules finalised in Phase 5.
> Each rule states **what**, **why** (evidence or source) and **where it is enforced** (code / test).
> Any change to a rule after it is written gets logged in `key_findings.md`.

---

## 1. Data handling (ops-policy §10)
_To be completed in Phase 1._
- No public repo; nothing shared beyond the engagement team. Returning the submission to the client is fine.
- `data/` is never committed (enforced: `.gitignore`).
- The service never reads `data/` at runtime.
- Delivery notes / gate codes never shown raw; sample orders are synthetic.

## 2. Cleaning rules
_To be completed in Phase 1._

## 3. Allowed features at dispatch (allow-list)
_To be completed in Phase 1 and 3._

## 4. Banned columns and why
_To be completed in Phase 1._

## 5. Banned practices
_To be completed in Phase 1._

## 6. Cost assumptions
_To be completed in Phase 1 (pack figures) and Phase 5 (margin)._

## 7. Decision rules
_To be completed in Phase 5._

## 8. Shield rule
_To be completed in Phase 5._

## 9. Model governance
_To be completed in Phase 6/7._
