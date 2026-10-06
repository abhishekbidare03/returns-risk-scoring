"""Chosen model: explicit unknown-value handling (an unknown scores between its known versions) and basic sanity."""
import numpy as np
import pandas as pd
import pytest

from kestrel.config import MODELS_DIR
from kestrel.features import build_features

from .conftest import CATALOGUE, HAS_DATA

HAS_MODEL = (MODELS_DIR / "model.joblib").exists()


@pytest.fixture(scope="module")
def model_and_catalogue():
    if HAS_MODEL:
        import json
        import joblib
        meta = json.loads((MODELS_DIR / "model_meta.json").read_text(encoding="utf-8"))
        return joblib.load(MODELS_DIR / "model.joblib"), meta["catalogue"]
    if not HAS_DATA:
        pytest.skip("neither a saved model nor the data pack is present")
    from kestrel.train import FINAL_CONFIG, SELECTION_END, load_training_frame, train_final
    X, y, ts, catalogue, _ = load_training_frame()
    model, _ = train_final(FINAL_CONFIG, X, y, ts, catalogue, end=SELECTION_END)
    return model, catalogue


def score(model_and_catalogue, order):
    model, catalogue = model_and_catalogue
    X, fb = build_features(pd.DataFrame([order]), catalogue)
    return float(model.predict_proba(X)[0]), fb.iloc[0]


def test_probability_in_range_and_no_fallbacks(model_and_catalogue, order):
    p, fb = score(model_and_catalogue, order)
    assert 0 < p < 1
    assert "shield_member" not in fb


def test_unknown_shield_between_known(model_and_catalogue, order):
    p_y, _ = score(model_and_catalogue, dict(order, shield_member="Y"))
    p_n, _ = score(model_and_catalogue, dict(order, shield_member="N"))
    p_u, fb = score(model_and_catalogue, {k: v for k, v in order.items() if k != "shield_member"})
    assert p_n < p_u < p_y
    assert "shield_member" in fb
    w_y = model_and_catalogue[0].marginals["shield"][1.0]
    assert p_u == pytest.approx(w_y * p_y + (1 - w_y) * p_n)   # training-share-weighted average (~22/78)


def test_unknown_payment_between_known(model_and_catalogue, order):
    known = [score(model_and_catalogue, dict(order, payment_mode=m))[0] for m in ("cod", "emi", "prepaid_card", "prepaid_upi")]
    p_u, fb = score(model_and_catalogue, dict(order, payment_mode="voucher"))
    assert min(known) < p_u < max(known)
    assert "payment_mode" in fb


def test_unknown_family_between_known(model_and_catalogue, order):
    skus = ["KH-AF-01", "KH-CF-01", "KH-IC-01", "KH-MG-01", "KH-RH-01", "KH-RV-01", "KH-WP-01"]
    known = [score(model_and_catalogue, dict(order, sku=s))[0] for s in skus]
    p_u, fb = score(model_and_catalogue, dict(order, sku="UNREADABLE"))
    assert min(known) < p_u < max(known)
    assert "sku" in fb


def test_several_unknowns_at_once(model_and_catalogue, order):
    o = {k: v for k, v in order.items() if k != "shield_member"}
    p, fb = score(model_and_catalogue, dict(o, payment_mode="voucher", sku="UNREADABLE"))
    assert 0 < p < 1 and {"shield_member", "payment_mode", "sku"} <= set(fb)


def test_risk_moves_in_the_expected_direction(model_and_catalogue, order):
    base = dict(order, customer_prior_returns=0, customer_prior_orders=2, payment_mode="prepaid_upi", promised_delivery_days=3)
    p0, _ = score(model_and_catalogue, base)
    assert score(model_and_catalogue, dict(base, customer_prior_returns=2))[0] > p0
    assert score(model_and_catalogue, dict(base, payment_mode="cod"))[0] > p0
    assert score(model_and_catalogue, dict(base, promised_delivery_days=10))[0] > p0


def test_missing_required_number_is_rejected(model_and_catalogue, order):
    model, catalogue = model_and_catalogue
    X, _ = build_features(pd.DataFrame([dict(order, discount_pct=None)]), catalogue)
    with pytest.raises(ValueError, match="discount_pct"):
        model.predict_proba(X)


def test_batch_matches_single(model_and_catalogue, order):
    model, catalogue = model_and_catalogue
    orders = [dict(order, customer_prior_returns=k, payment_mode=m) for k in (0, 1, 3) for m in ("cod", "prepaid_upi")]
    orders.append({k: v for k, v in order.items() if k != "shield_member"})
    X, _ = build_features(pd.DataFrame(orders), catalogue)
    batch = model.predict_proba(X)
    single = [score(model_and_catalogue, o)[0] for o in orders]
    np.testing.assert_allclose(batch, single, rtol=1e-12)
