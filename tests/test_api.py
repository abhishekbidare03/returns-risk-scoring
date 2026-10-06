"""Service contract: validation vs fallbacks, ignored fields, privacy, health, page, and score parity."""
import json

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import SAMPLES, app, service
from kestrel.features import build_features

from .conftest import needs_data

client = TestClient(app)
VALID = {"order_id": "T-1", "sku": "KH-RV-02", "payment_mode": "cod", "promised_delivery_days": 8, "discount_pct": 18,
         "customer_prior_orders": 3, "customer_prior_returns": 1, "shield_member": "Y"}


def post(**changes):
    body = {k: v for k, v in {**VALID, **changes}.items() if v is not ...}
    return client.post("/score", json=body)


def test_valid_order():
    r = post()
    assert r.status_code == 200
    d = r.json()
    assert d["order_id"] == "T-1" and 0 < d["return_probability"] < 1
    assert d["recommended_action"] in ("CALL", "SHIP")
    assert d["risk_band"] in ("Low", "Medium", "High")
    assert (d["risk_band"] == "High") == (d["recommended_action"] == "CALL")      # bands aligned with the action
    assert 2 <= len(d["reasons_raising"]) <= 3 and len(d["reasons_lowering"]) <= 1
    assert d["fallbacks_used"] == [] and d["ignored_fields"] == []
    assert "HOLD" not in json.dumps(d)
    assert "×" in d["vs_typical"]


@pytest.mark.parametrize("field", ["sku", "promised_delivery_days", "discount_pct", "customer_prior_orders", "customer_prior_returns"])
def test_missing_required_field_is_422(field):
    r = post(**{field: ...})
    assert r.status_code == 422
    assert any(p["field"] == field for p in r.json()["problems"])


@pytest.mark.parametrize("changes", [
    {"promised_delivery_days": -3}, {"discount_pct": 140}, {"customer_prior_orders": "many"},
    {"promised_delivery_days": 4.5}, {"customer_prior_returns": 5, "customer_prior_orders": 2},
])
def test_invalid_value_is_422(changes):
    assert post(**changes).status_code == 422


def test_category_typo_lists_allowed_values():
    r = post(payment_mode="upi")
    assert r.status_code == 422
    p = r.json()["problems"][0]
    assert p["field"] == "payment_mode" and "prepaid_upi" in p["allowed_values"]
    r = post(shield_member="maybe")
    assert r.status_code == 422 and "unknown" in r.json()["problems"][0]["allowed_values"]


@pytest.mark.parametrize("value", [..., "unknown"])
def test_unknown_or_missing_shield_falls_back(value):
    d = post(shield_member=value).json()
    y, n = post(shield_member="Y").json(), post(shield_member="N").json()
    assert n["return_probability"] < d["return_probability"] < y["return_probability"]
    assert any("Shield status unknown" in f for f in d["fallbacks_used"])
    assert not any("Shield" in r for r in d["reasons_raising"] + d["reasons_lowering"])   # no reason from a guess


@pytest.mark.parametrize("value", [..., "unknown"])
def test_unknown_or_missing_payment_falls_back(value):
    d = post(payment_mode=value).json()
    assert any("Payment mode unknown" in f for f in d["fallbacks_used"])


@pytest.mark.parametrize("sku, family", [("KH-AF-09", "Air Fryer"), ("NEW-THING", "unknown")])
def test_unknown_sku_falls_back(sku, family):
    d = post(sku=sku).json()
    assert d["family"] == family and any("SKU not in the catalogue" in f for f in d["fallbacks_used"])


def test_case_and_bool_normalisation():
    a = post(payment_mode="COD", shield_member=True).json()
    b = post(payment_mode="cod", shield_member="Y").json()
    assert a["return_probability"] == b["return_probability"]


def test_extra_and_banned_fields_ignored_and_not_echoed():
    secret = "Gate code 4725, call before delivery"
    d = post(delivery_note=secret, delivery_pincode="440365", pickup_scheduled_at="8/20/2026 10:00",
             last_service_event_type="REVERSE_PICKUP", city="Kota").json()
    base = post().json()
    assert d["return_probability"] == base["return_probability"]          # leaky fields change nothing
    assert set(d["ignored_fields"]) == {"delivery_note", "delivery_pincode", "pickup_scheduled_at", "last_service_event_type", "city"}
    assert any("after dispatch" in w for w in d["warnings"])
    assert secret not in json.dumps(d) and "440365" not in json.dumps(d)


def test_health():
    h = client.get("/health").json()
    assert h["status"] == "ok" and h["llm"] == "none" and h["external_api"] == "none"
    assert len(h["inputs"]) == 7 and 0.1 < h["call_cutoff"] < 0.2


def test_page_and_samples():
    r = client.get("/")
    assert r.status_code == 200 and "Kestrel return risk" in r.text and "/score" in r.text
    samples = client.get("/samples").json()
    assert len(samples) >= 5
    text = json.dumps(samples)
    for banned in ("delivery_note", "pincode", "KC1", "Gate code"):          # synthetic only, no PII fields
        assert banned not in text


def test_samples_api_equals_batch_scoring():
    samples = json.loads(SAMPLES.read_text(encoding="utf-8"))
    api = [client.post("/score", json=s["order"]).json()["return_probability"] for s in samples]
    rec = pd.DataFrame([s["order"] for s in samples])
    X, _ = build_features(rec, service.meta["catalogue"])
    batch = service.model.predict_proba(X)
    np.testing.assert_allclose(api, np.round(batch, 4), atol=1e-9)


@needs_data
def test_api_equals_predict_py(pack):
    """API score = predict.py score for the same test orders (7 fields sent as JSON)."""
    from kestrel.predict import load_model, score_test
    model, meta = load_model()
    detail = score_test(model, meta, pack).set_index("order_id")
    rec = pack["test"].merge(pack["customers"][["customer_id", "shield_member"]], on="customer_id").sample(60, random_state=1)
    for r in rec.itertuples():
        body = {"sku": r.sku, "payment_mode": r.payment_mode, "promised_delivery_days": int(r.promised_delivery_days),
                "discount_pct": float(r.discount_pct), "customer_prior_orders": int(r.customer_prior_orders),
                "customer_prior_returns": int(r.customer_prior_returns), "shield_member": r.shield_member}
        api = client.post("/score", json=body).json()["return_probability"]
        assert api == pytest.approx(round(detail.loc[r.order_id, "score"], 4), abs=1e-9)


def test_service_never_reads_data_dir():
    import inspect
    import app.main as m
    from kestrel import service as s
    for mod in (m, s):
        src = inspect.getsource(mod)
        assert "DATA_DIR" not in src and "read_csv" not in src and "load_pack" not in src


def test_sku_is_case_insensitive():
    lower, upper = post(sku="kh-rv-02").json(), post(sku="KH-RV-02").json()
    assert lower["return_probability"] == upper["return_probability"] and lower["family"] == "Robot Vacuum"
    assert lower["fallbacks_used"] == []


@pytest.mark.parametrize("field, value, edge", [("promised_delivery_days", 60, 12), ("discount_pct", 100, 60)])
def test_out_of_range_is_capped_with_warning(field, value, edge):
    d, at_edge = post(**{field: value}).json(), post(**{field: edge}).json()
    assert d["return_probability"] == at_edge["return_probability"]          # scored at the training edge
    w = [x for x in d["warnings"] if x.startswith(field)]
    assert len(w) == 1 and str(value) in w[0] and f"-{edge}" in w[0]          # names field, value given, range
    assert at_edge["warnings"] == []


def test_prior_orders_capped_keeping_return_rate():
    d = post(customer_prior_orders=200, customer_prior_returns=50).json()
    assert any("scored as 10 orders with 2 returns" in w for w in d["warnings"])
    assert any("50 of 200" in r for r in d["reasons_raising"])               # reasons quote what was entered
