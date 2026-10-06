# Kestrel Returns Risk - Policy (the rules we commit to)

> Status: **Sections 1–6 written in Phase 1 (2026-10-06)** from `notebooks/01_data_audit.ipynb`. Sections 7–8 are finalised in Phase 5, section 9 in Phase 6/7.
> Each rule states **what**, **why** (evidence or source) and **where it is enforced** (code / test; filled in from Phase 3 onwards).
> Any change to a rule after it is written gets logged in `key_findings.md`.

---

## 1. Data handling (ops-policy §10)

| Rule | Why | Enforced |
|---|---|---|
| No public repo; nothing shared beyond the engagement team. Returning the submission to the client is fine | Ops-policy §10 | Private GitHub repo; **only the user pushes** |
| `data/` and every `*.csv` are never committed | Customer and operational data | `.gitignore` (verified with `git check-ignore`) |
| The service never reads `data/` at runtime | Clean-machine start; §10 | Phase 8 test: service starts with `data/` absent |
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

| Raw input | Allowed derivatives | Status | Source at serve time |
|---|---|---|---|
| `payment_mode`, `promised_delivery_days`, `discount_pct` | as-is / encoded | core | order record |
| `order_value_inr` | cleaned value (C4) | core | order record |
| `customer_prior_orders`, `customer_prior_returns` | as-is, prior return rate, has-prior-return. **Strong but imperfect:** consistent with as-of-order-time (own return excluded, flat by month, never > prior orders, matches test), but a noisy CRM count | core | order record (CRM history as of order time) |
| `sku` | family; SKU tier (Lite/Pro/Max) and product age as candidates | core (family) | product catalogue embedded in `model_meta.json` |
| `shield_member` | as-is, `"unknown"` fallback. Drift checked: 22.2% train vs 22.1% test, flat by month, **no drift risk** | core | **passed with the order**; training joins `customers.csv` |
| `city`, `state` | `city` (18 levels, regularised) **or** `metro` flag; `"unknown"` fallback | core (one of the two) | **passed with the order**; training joins `customers.csv` |
| `sales_channel`, `is_gift`, `qty` | as-is / encoded | candidate | order record |
| `delivery_pincode` | **`address_missing` only** | candidate | order record |
| `delivery_note` | `note_present`, `note_cat` (known template with digits removed, else `other`) | candidate (no signal in EDA) | order record |

**Not used (Phase 2 evidence):**
| Input / derivative | Why |
|---|---|
| Pincode region (first 3 digits) | **Unreliable:** all 12 non-metro cities carry `440xxx`; only 8.4% of `440` orders are from Nagpur customers. City/state replaces it |
| `signup_date` → tenure | No signal (single-field AUC 0.504, flat across bands) **and** shifted (negative-tenure share 19% train vs 0.9% test, PSI 0.60). The service doesn't need `signup_date` |
| `order_placed_at` → hour, weekday, festive window, season | Flat return rates (hour 11.2–11.8%, festive 11.1% vs 11.5%, Jul–Sep 11.1%) |
| `warranty_months` | Exactly determined by family (24 months only for mixer grinders and ceiling fans) |
| value vs list price | Exactly determined by discount and qty (order value = list × qty × (1 − discount)) |

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
3. **Tuning on the final holdout** (Apr–Jun 2026). Tuning uses walk-forward folds only.
4. **Calibrating on in-sample predictions.** The calibrator is fitted on walk-forward out-of-fold predictions only.
5. **Reporting accuracy as the headline metric.** It is shown only to explain why it misleads (base rate 11.4%).

## 6. Cost assumptions

| Item | Value | Source |
|---|---|---|
| Cost of a return | **₹1,150** (reverse pickup, QC, repacking, write-down; on top of the refund) | Ops-policy §4; Finance (Farhan) reports this figure |
| Sensitivity case | ₹600 | Ritu's informal count (email) |
| Pre-dispatch confirmation call | **₹45** per completed call | Ops-policy §4 |
| Call effect | prevents **~35%** of returns on called orders | Ops-policy §7 (spring pilot). No dip is visible in the data (Mar–May 2026: 11.2/12.0/11.2%), so we use the policy figure |
| Hold > 24 h | **~12%** of held orders are cancelled by the customer | Ops-policy §7 |
| Margin lost on a cancelled good order | **open, set in Phase 5** (15 / 25 / 35% of order value, tested against the ₹375 condition) | Not in the pack |
| Model cost per order | **₹0** (local model, local reasons, no API) | Farhan's condition |

## 7. Decision rules
_To be completed in Phase 5._ Planned shape: call the top X% of orders the team can handle; don't hold.

## 8. Shield rule
_To be completed in Phase 5._ Planned shape: "call, don't hold" for everyone; Shield is an extra reason never to hold. Shield = 22% of orders, 36% of returns, return rate 18.6% vs 9.4%.

## 9. Model governance
_To be completed in Phase 6/7._
