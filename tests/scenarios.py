"""Black-box scenario sheet (manual acceptance test, Phase 8): expected vs actual for every case.

    python -m tests.scenarios      # re-runs all cases and rewrites evidence/scenario_tests.md
Used by tests/test_scenarios.py, so the evidence file and the test suite always agree.
"""
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
BASE = {"sku": "KH-AF-02", "payment_mode": "prepaid_card", "promised_delivery_days": 5, "discount_pct": 10,
        "customer_prior_orders": 2, "customer_prior_returns": 0, "shield_member": "N"}


def call(body):
    r = client.post("/score", json=body)
    return r.status_code, r.json()


def b(**changes):
    return {**BASE, **changes}


def p(d):
    return d.get("return_probability")


def has_fallback(d, word):
    return any(word in f for f in d.get("fallbacks_used", []))


def warns(d, field):
    return any(w.startswith(field) for w in d.get("warnings", []))


_, BASE_RESULT = call(BASE)
P0 = BASE_RESULT["return_probability"]


def same_as(body):
    return lambda s, d: s == 200 and p(d) == p(call(body)[1])


def err(field=None):
    return lambda s, d: s == 422 and (field is None or any(x["field"] == field for x in d["problems"]))


CASES = [
    # id, description of the order, expectation (blind, business sense), body, check(status, response)
    ("A1", "Mixer grinder, UPI, 3 days, 5%, 6 orders / 0 returns, not Shield", "Low, SHIP",
     dict(sku="KH-MG-01", payment_mode="prepaid_upi", promised_delivery_days=3, discount_pct=5, customer_prior_orders=6, customer_prior_returns=0, shield_member="N"),
     lambda s, d: d["risk_band"] == "Low" and d["recommended_action"] == "SHIP"),
    ("A2", "Robot vacuum Max, COD, 7 days, 25%, 5 orders / 4 returns, Shield", "Very high, CALL; past returns the top reason",
     dict(sku="KH-RV-03", payment_mode="cod", promised_delivery_days=7, discount_pct=25, customer_prior_orders=5, customer_prior_returns=4, shield_member="Y"),
     lambda s, d: d["recommended_action"] == "CALL" and "returned 4 of 5" in d["reasons_raising"][0]),
    ("A3", "Water purifier, COD, 10 days, 30%, new customer, not Shield", "High, CALL",
     dict(sku="KH-WP-02", payment_mode="cod", promised_delivery_days=10, discount_pct=30, customer_prior_orders=0, customer_prior_returns=0, shield_member="N"),
     lambda s, d: d["recommended_action"] == "CALL"),
    ("A4", "Air fryer Max, card, 4 days, 45%, 1 order / 0 returns", "Medium; discount among the reasons",
     dict(sku="KH-AF-03", payment_mode="prepaid_card", promised_delivery_days=4, discount_pct=45, customer_prior_orders=1, customer_prior_returns=0, shield_member="N"),
     lambda s, d: d["risk_band"] == "Medium" and any("discount" in r for r in d["reasons_raising"])),
    ("A5", "Ceiling fan, EMI, 2 days, 0%, 8 orders / 1 return, Shield", "Low-Medium, SHIP",
     dict(sku="KH-CF-02", payment_mode="emi", promised_delivery_days=2, discount_pct=0, customer_prior_orders=8, customer_prior_returns=1, shield_member="Y"),
     lambda s, d: d["recommended_action"] == "SHIP" and d["risk_band"] in ("Low", "Medium")),
    ("A6", "Room heater, COD, 11 days, 15%, 2 orders / 1 return", "High, CALL",
     dict(sku="KH-RH-01", payment_mode="cod", promised_delivery_days=11, discount_pct=15, customer_prior_orders=2, customer_prior_returns=1, shield_member="N"),
     lambda s, d: d["recommended_action"] == "CALL"),
    ("A7", "Induction cooktop, UPI, 3 days, 8%, new customer, Shield unknown", "Low, with a Shield-unknown notice",
     dict(sku="KH-IC-01", payment_mode="prepaid_upi", promised_delivery_days=3, discount_pct=8, customer_prior_orders=0, customer_prior_returns=0, shield_member="unknown"),
     lambda s, d: d["risk_band"] == "Low" and has_fallback(d, "Shield")),
    ("A8", "Robot vacuum Lite, UPI, 2 days, 5%, 4 orders / 0 returns", "Low-Medium; product the only risk reason",
     dict(sku="KH-RV-01", payment_mode="prepaid_upi", promised_delivery_days=2, discount_pct=5, customer_prior_orders=4, customer_prior_returns=0, shield_member="N"),
     lambda s, d: d["risk_band"] in ("Low", "Medium") and d["reasons_raising"] == ["Robot vacuums are returned more often than most products"]),

    ("B1", "Base: air fryer Pro, card, 5 days, 10%, 2 orders / 0 returns, not Shield", "Reference", BASE,
     lambda s, d: s == 200),
    ("B2", "Base, payment = COD", "Higher than base", b(payment_mode="cod"), lambda s, d: p(d) > P0),
    ("B3", "Base, 1 of 2 orders returned", "Higher than base", b(customer_prior_returns=1), lambda s, d: p(d) > P0),
    ("B4", "Base, 10 days", "Higher than base", b(promised_delivery_days=10), lambda s, d: p(d) > P0),
    ("B5", "Base, Shield = Y", "Higher than base", b(shield_member="Y"), lambda s, d: p(d) > P0),
    ("B6", "Base, discount 35%", "Higher than base", b(discount_pct=35), lambda s, d: p(d) > P0),
    ("B7", "Base, SKU = ceiling fan KH-CF-02", "Lower than base", b(sku="KH-CF-02"), lambda s, d: p(d) < P0),
    ("B8", "Base, SKU = robot vacuum KH-RV-02", "Higher than base", b(sku="KH-RV-02"), lambda s, d: p(d) > P0),
    ("B9", "Base, 10 prior orders (still 0 returns)", "Same or lower, never higher", b(customer_prior_orders=10), lambda s, d: p(d) <= P0),
    ("B10", "Base again", "Exactly the same as B1", BASE, lambda s, d: p(d) == P0),

    ("C1", "Base, discount 0%", "Lower than base", b(discount_pct=0), lambda s, d: p(d) < P0),
    ("C2", "Base, discount 100% (free)", "Accepted, with a warning that it's unusual",
     b(discount_pct=100), lambda s, d: warns(d, "discount_pct") and p(d) == p(call(b(discount_pct=60))[1])),
    ("C3", "Base, 1 day", "Lower than base", b(promised_delivery_days=1), lambda s, d: p(d) < P0),
    ("C4", "Base, 60 days", "Higher, with a warning, not blind certainty",
     b(promised_delivery_days=60), lambda s, d: warns(d, "promised_delivery_days") and p(d) > P0 and p(d) == p(call(b(promised_delivery_days=12))[1])),
    ("C5", "Base, 0 prior orders / 0 returns", "Accepted (new customer)", b(customer_prior_orders=0), lambda s, d: s == 200),
    ("C6", "Base, 10 of 10 orders returned", "Very high, CALL", b(customer_prior_orders=10, customer_prior_returns=10),
     lambda s, d: d["recommended_action"] == "CALL"),
    ("C7", "Base, 200 prior orders / 0 returns", "Low, SHIP (a warning is fine)", b(customer_prior_orders=200),
     lambda s, d: d["recommended_action"] == "SHIP" and warns(d, "customer_prior_orders")),
    ("C8", "Base, discount 12.5%", "Accepted, close to base", b(discount_pct=12.5), lambda s, d: s == 200 and abs(p(d) - P0) < 0.01),

    ("D1", "SKU 'kh-af-02' (lower case)", "Same as KH-AF-02", b(sku="kh-af-02"), lambda s, d: p(d) == P0 and d["family"] == "Air Fryer" and not d["fallbacks_used"]),
    ("D2", "SKU '  KH-AF-02  ' (spaces)", "Same as base", b(sku="  KH-AF-02  "), lambda s, d: p(d) == P0 and not d["fallbacks_used"]),
    ("D3", "SKU 'KH-XX-01' (made-up family)", "Scored, with an 'SKU not recognised' notice", b(sku="KH-XX-01"), lambda s, d: s == 200 and has_fallback(d, "SKU")),
    ("D4", "SKU 'ABC123'", "Scored, with an 'SKU not recognised' notice", b(sku="ABC123"), lambda s, d: s == 200 and has_fallback(d, "SKU")),
    ("D5", "SKU empty", "Clear error on SKU", b(sku=""), err("sku")),
    ("D6", "Discount 150", "Clear error (max 100)", b(discount_pct=150), err("discount_pct")),
    ("D7", "Discount -5", "Clear error", b(discount_pct=-5), err("discount_pct")),
    ("D8", "Promised days 4.5", "Clear error or rounding", b(promised_delivery_days=4.5), err("promised_delivery_days")),
    ("D9", "1 prior order, 3 returns", "Clear error", b(customer_prior_orders=1, customer_prior_returns=3), err()),
    ("D10", "Payment 'unknown'", "Scored, with a payment-unknown notice", b(payment_mode="unknown"), lambda s, d: s == 200 and has_fallback(d, "Payment")),
    ("D11", "Payment 'upi' (typo)", "Error listing the valid payment modes", b(payment_mode="upi"),
     lambda s, d: s == 422 and "prepaid_upi" in d["problems"][0].get("allowed_values", "")),
    ("D12", "Payment 'COD', Shield 'yes'", "Same as cod + Y", b(payment_mode="COD", shield_member="yes"), same_as(b(payment_mode="cod", shield_member="Y"))),
    ("D13", "Promised days 'five'", "Clear error on promised days", b(promised_delivery_days="five"), err("promised_delivery_days")),
    ("D14", "Base + delivery_note 'Gate code 9911' + pickup date", "Same score; both ignored; '9911' never shown",
     b(delivery_note="Gate code 9911", pickup_scheduled_at="9/2/2026"),
     lambda s, d: p(d) == P0 and set(d["ignored_fields"]) == {"delivery_note", "pickup_scheduled_at"} and "9911" not in json.dumps(d)),

    ("X1", "Negative number: prior orders -1", "Clear error", b(customer_prior_orders=-1), err("customer_prior_orders")),
    ("X2", "Huge number: discount 1e12", "Clear error", b(discount_pct=1e12), err("discount_pct")),
    ("X3", "Empty body {}", "Clear error listing the required fields", {},
     lambda s, d: s == 422 and {"sku", "promised_delivery_days", "discount_pct", "customer_prior_orders", "customer_prior_returns"} <= {x["field"] for x in d["problems"]}),
    ("X4", "Shield true (JSON boolean)", "Same as Y", b(shield_member=True), same_as(b(shield_member="Y"))),
    ("X5", "Payment ' COD ' (spaces + capitals)", "Same as cod", b(payment_mode=" COD "), same_as(b(payment_mode="cod"))),
    ("X7", "Just below the call cutoff: base with 1 of 2 returned (call value >= 0)", "SHIP, and the note says a call would roughly break even",
     b(customer_prior_returns=1),
     lambda s, d: d["recommended_action"] == "SHIP" and d["call_value_inr"] >= 0 and "roughly break even" in d["note"]),
    ("X6", "Huge prior orders: 5,000 orders / 1,000 returns", "Scored with a warning, return rate kept",
     b(customer_prior_orders=5000, customer_prior_returns=1000), lambda s, d: s == 200 and warns(d, "customer_prior_orders")),
]


def run_all():
    rows = []
    for cid, desc, expect, body, check in CASES:
        status, d = call(body)
        ok = bool(check(status, d))
        if status == 200:
            actual = f"{d['return_probability']:.1%} {d['risk_band']}, {d['recommended_action']}"
            extra = d["fallbacks_used"] + d.get("warnings", [])
            if extra:
                actual += " · " + " · ".join(x.split(";")[0].split(" - ")[0][:70] for x in extra)
        else:
            actual = f"HTTP {status}: " + "; ".join(f"{x['field']}: {x['problem'][:60]}" for x in d["problems"])
        rows.append((cid, desc, expect, actual, ok))
    return rows


def write_markdown(path=Path(__file__).resolve().parents[1] / "evidence" / "scenario_tests.md"):
    rows = run_all()
    passed = sum(r[4] for r in rows)
    lines = [
        "# Scenario tests (black-box acceptance sheet)", "",
        "Made-up orders (none from the data pack), tested the way an independent tester would: realistic orders (A), "
        "one change at a time from a base order (B), extreme but valid values (C), messy input (D) and extra edge cases (X). "
        "The expectation column was written from business sense **before** looking at the model's internals.", "",
        f"**Result: {passed} / {len(rows)} pass** (regenerated by `python -m tests.scenarios`; asserted by `tests/test_scenarios.py`).", "",
        "History: the first manual run (2026-10-06) found three issues, now fixed and covered by these cases: "
        "(1) lower-case SKU treated as unknown (D1); (2) out-of-range values extrapolated with no warning: 60 days scored 99.99% CALL, "
        "100% discount 51% CALL (C2, C4, C7, X6); values outside the training range are now scored at the edge of that range, with a warning; "
        "(3) a positive call value next to SHIP had no explanation; the API note (and so the screen) now says \"A call would roughly break even; below the call cutoff, so ship\" (X7).", "",
        f"Base order (B1) = {P0:.1%}.", "",
        "| ID | Order | Expected | Actual | Pass |", "|---|---|---|---|---|",
    ]
    for cid, desc, expect, actual, ok in rows:
        lines.append(f"| {cid} | {desc} | {expect} | {actual.replace('|', '/')} | {'✅' if ok else '❌'} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return passed, len(rows)


if __name__ == "__main__":
    print("%d / %d pass" % write_markdown())
