"""Feature contract: leakage guard, allow-list, fallbacks, privacy, train/serve parity."""
import inspect

import numpy as np
import pandas as pd
import pytest

from kestrel import features
from kestrel.config import BANNED_COLUMNS
from kestrel.features import (
    ALLOWED_INPUTS, FEATURE_COLUMNS, build_features, catalogue_from_products, training_records,
)

from .conftest import CATALOGUE, needs_data

POST_DISPATCH = {"last_service_event_type", "pickup_scheduled_at", "source", "returned", "order_id", "customer_id"}


def one(order, catalogue=CATALOGUE):
    X, fb = build_features(pd.DataFrame([order]), catalogue)
    return X.iloc[0], fb.iloc[0]


# --- leakage guard -----------------------------------------------------------------------------
def test_no_banned_column_is_a_feature():
    assert not set(FEATURE_COLUMNS) & set(BANNED_COLUMNS)


def test_post_dispatch_columns_are_not_inputs():
    assert not set(ALLOWED_INPUTS) & POST_DISPATCH


def test_leaky_values_do_not_change_features(order):
    clean, _ = one(order)
    leaky = dict(order, last_service_event_type="REVERSE_PICKUP", pickup_scheduled_at="8/20/2026 10:00",
                 returned=1, source="partner_feed", order_id="X", customer_id="Y", anything_else=42)
    dirty, _ = one(leaky)
    pd.testing.assert_series_equal(clean, dirty)


def test_feature_module_reads_no_files():
    src = inspect.getsource(features)
    assert "read_csv" not in src and "DATA_DIR" not in src and "open(" not in src


# --- behaviour on a known order ------------------------------------------------------------------
def test_known_order(order):
    x, fb = one(order)
    assert fb == []
    assert x.family == "Robot Vacuum" and x.tier == "Max" and x.payment_mode == "cod"
    assert x.shield == 1.0 and x.metro == 0.0 and x.city == "Kota"
    assert x.prior_return_rate == 0.5 and x.has_prior_return == 1.0
    assert x.is_gift == 1.0 and x.address_missing == 1.0
    assert x.product_age_days == (pd.Timestamp("2026-08-14") - pd.Timestamp("2023-10-26")).days


def test_iso_timestamp_accepted(order):
    a, _ = one(order)
    b, _ = one(dict(order, order_placed_at="2026-08-14T18:05:00"))
    assert a.product_age_days == b.product_age_days


# --- fallbacks: unknown input -> NaN / "unknown", always reported ------------------------------
def test_missing_shield_and_city_fall_back(order):
    o = {k: v for k, v in order.items() if k not in ("shield_member", "city", "state")}
    x, fb = one(o)
    assert np.isnan(x.shield) and np.isnan(x.metro) and x.city == "unknown"
    assert "shield_member" in fb and "city" in fb


def test_unknown_sku_uses_family_code(order):
    x, fb = one(dict(order, sku="KH-WP-09"))
    assert x.family == "Water Purifier" and x.tier == "unknown" and np.isnan(x.product_age_days)
    assert "sku" in fb


def test_unknown_payment_mode_reported(order):
    x, fb = one(dict(order, payment_mode="crypto"))
    assert x.payment_mode == "unknown" and "payment_mode" in fb


def test_missing_required_field_raises(order):
    o = dict(order); o.pop("customer_prior_returns")
    with pytest.raises(ValueError, match="customer_prior_returns"):
        one(o)


def test_optional_defaults_are_reported(order):
    o = {k: order[k] for k in features.REQUIRED_INPUTS}
    x, fb = one(o)
    assert x.qty == 1.0 and np.isnan(x.is_gift) and x.note_cat == "none" and x.address_missing == 1.0
    assert {"qty", "is_gift", "shield_member", "city"} <= set(fb)


def test_unreadable_sku_gives_unknown_family(order):
    x, fb = one(dict(order, sku="ZZ-123"))
    assert x.family == "unknown" and "sku" in fb


# --- privacy: raw note text never reaches the features --------------------------------------
@pytest.mark.parametrize("note, expected", [
    ("Gate code 0000, call before delivery", "Gate code #, call before delivery"),
    ("Deliver to neighbour flat 11B if not home", "Deliver to neighbour flat # if not home"),
    ("please call my brother on 98xxxxxx", "other"),
    (None, "none"),
])
def test_note_bucketing(order, note, expected):
    x, _ = one(dict(order, delivery_note=note))
    assert x.note_cat == expected
    assert not any(ch.isdigit() for ch in x.note_cat)


@pytest.mark.parametrize("pin, missing", [("0", 1.0), ("000000", 1.0), (None, 1.0), ("999001", 0.0)])
def test_address_missing(order, pin, missing):
    x, _ = one(dict(order, delivery_pincode=pin))
    assert x.address_missing == missing


# --- real pack: no fallbacks, and batch == one-record-at-a-time (train/serve parity) ----------
@needs_data
def test_real_pack_has_no_fallbacks(pack):
    cat = catalogue_from_products(pack["products"])
    for name in ("train", "test"):
        X, fb = build_features(training_records(pack[name], pack["customers"]), cat)
        assert fb.map(len).sum() == 0
        assert X[list(features.NUMERIC_FEATURES)].notna().all().all()


@needs_data
def test_batch_equals_single_record(pack):
    cat = catalogue_from_products(pack["products"])
    rec = training_records(pack["test"], pack["customers"])
    # what the API receives: plain JSON-like values, one order at a time
    sample = rec.sample(150, random_state=0)
    batch, _ = build_features(sample, cat)
    for i, row in sample.iterrows():
        payload = {k: (None if pd.isna(row[k]) else row[k]) for k in ALLOWED_INPUTS if k in row}
        payload["order_placed_at"] = row["order_placed_at"]
        single, _ = build_features(pd.DataFrame([payload]), cat)
        pd.testing.assert_series_equal(single.iloc[0], batch.loc[i], check_names=False, check_dtype=False)
