"""Dispatch-time feature builder - the single source of truth for training, batch scoring and the API.

Input is an *order record*: the fields the warehouse system has at dispatch (policy.md §3), with
`shield_member` / `city` passed alongside the order. Product details come from the catalogue
(embedded in model_meta.json at serve time). Nothing here reads files.

Output is a tidy frame: numeric columns (NaN = unknown) and categorical columns ("unknown" = unknown).
Encoding and imputation happen inside the model pipeline (Phase 4), so LR and HGB share these features.
"""
import re

import numpy as np
import pandas as pd

from .config import (
    BANNED_COLUMNS, CITIES, DEFAULT_PINCODE, FAMILY_BY_CODE, METRO_CITIES, NOTE_TEMPLATES,
    ORDER_TS_FORMAT, PAYMENT_MODES, SALES_CHANNELS, TIERS,
)

# Raw inputs the builder may read. Anything else in a record is ignored (allow-list, policy.md §3).
REQUIRED_INPUTS = (
    "sku", "payment_mode", "promised_delivery_days", "discount_pct",
    "customer_prior_orders", "customer_prior_returns",
)
OPTIONAL_INPUTS = (
    "sales_channel", "qty", "is_gift", "delivery_pincode", "delivery_note", "order_placed_at",
    "shield_member", "city", "state",
)
ALLOWED_INPUTS = REQUIRED_INPUTS + OPTIONAL_INPUTS

CORE_NUMERIC = (
    "promised_delivery_days", "customer_prior_returns", "customer_prior_orders",
    "prior_return_rate", "has_prior_return", "discount_pct", "shield",
)
CORE_CATEGORICAL = ("payment_mode", "family")
CANDIDATE_NUMERIC = ("metro", "is_gift", "qty", "address_missing", "product_age_days", "note_present")
CANDIDATE_CATEGORICAL = ("city", "sales_channel", "tier", "note_cat")
NUMERIC_FEATURES = CORE_NUMERIC + CANDIDATE_NUMERIC
CATEGORICAL_FEATURES = CORE_CATEGORICAL + CANDIDATE_CATEGORICAL
FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES

UNKNOWN = "unknown"


def catalogue_from_products(products):
    """sku -> {family, tier, list_price_inr, launch_date (YYYY-MM-DD)}; JSON-serialisable for model_meta.json."""
    return {
        r.sku: {
            "family": r.family,
            "tier": r.model_name.split()[-1],
            "list_price_inr": float(r.list_price_inr),
            "launch_date": pd.Timestamp(r.launch_date).strftime("%Y-%m-%d"),
        }
        for r in products.itertuples()
    }


def _note_category(note):
    if note is None or (isinstance(note, float) and np.isnan(note)) or str(note).strip() == "":
        return "none"
    template = re.sub(r"\d+[A-Z]?", "#", str(note))
    return template if template in NOTE_TEMPLATES else "other"


def _flag(series, yes="Y", no="N"):
    """Y/N (any case, also True/False/1/0) -> 1.0/0.0; anything else -> NaN."""
    s = series.astype("string").str.strip().str.upper()
    out = pd.Series(np.nan, index=series.index, dtype=float)
    out[s.isin([yes, "TRUE", "1", "1.0"])] = 1.0
    out[s.isin([no, "FALSE", "0", "0.0"])] = 0.0
    return out


def build_features(records, catalogue):
    """Order records (DataFrame) + product catalogue -> (features DataFrame, fallbacks Series of lists).

    Only ALLOWED_INPUTS are read; banned or unknown columns in `records` are ignored.
    """
    missing = [c for c in REQUIRED_INPUTS if c not in records]
    if missing:
        raise ValueError(f"missing required order fields: {missing}")
    r = records.reindex(columns=list(ALLOWED_INPUTS))   # the allow-list is enforced here
    idx = records.index
    fallbacks = pd.Series([[] for _ in range(len(r))], index=idx, dtype=object)

    def note_fallback(mask, label):
        for i in idx[mask.to_numpy()]:
            fallbacks.at[i].append(label)

    f = pd.DataFrame(index=idx)

    # --- numeric order fields
    for col in ("promised_delivery_days", "discount_pct", "customer_prior_orders", "customer_prior_returns"):
        f[col] = pd.to_numeric(r[col], errors="coerce").astype(float)
        note_fallback(f[col].isna(), col)
    f["prior_return_rate"] = f.customer_prior_returns / f.customer_prior_orders.clip(lower=1)
    f["has_prior_return"] = (f.customer_prior_returns > 0).astype(float).where(f.customer_prior_returns.notna())

    qty = pd.to_numeric(r["qty"], errors="coerce")
    f["qty"] = qty.fillna(1).astype(float)          # 94% of orders are single units; reported below
    note_fallback(qty.isna(), "qty")
    f["is_gift"] = _flag(r["is_gift"])              # unknown -> NaN, averaged over Y/N by the model
    note_fallback(f.is_gift.isna(), "is_gift")

    # --- customer fields passed with the order (training joins them from customers.csv)
    f["shield"] = _flag(r["shield_member"])
    note_fallback(f.shield.isna(), "shield_member")
    city = r["city"].astype("string").str.strip()
    known_city = city.isin(CITIES)
    f["city"] = city.where(known_city, UNKNOWN).astype(object)
    f["metro"] = city.isin(METRO_CITIES).astype(float).where(known_city)
    note_fallback(~known_city, "city")

    # --- categoricals with known levels
    for col, levels in (("payment_mode", PAYMENT_MODES), ("sales_channel", SALES_CHANNELS)):
        v = r[col].astype("string").str.strip().str.lower()
        ok = v.isin(levels)
        f[col] = v.where(ok, UNKNOWN).astype(object)
        if col == "payment_mode" or r[col].notna().any():
            note_fallback(~ok, col)

    # --- product fields from the catalogue (unknown SKU -> family from the SKU code)
    sku = r["sku"].astype("string").str.strip()
    known_sku = sku.isin(list(catalogue))
    cat_family = sku.map(lambda s: catalogue.get(s, {}).get("family") if isinstance(s, str) else None)
    code_family = sku.str.extract(r"^KH-([A-Z]{2})-", expand=False).map(FAMILY_BY_CODE)
    f["family"] = cat_family.fillna(code_family).fillna(UNKNOWN).astype(object)
    f["tier"] = sku.map(lambda s: catalogue.get(s, {}).get("tier") if isinstance(s, str) else None).fillna(UNKNOWN).astype(object)
    f.loc[~f.tier.isin(TIERS), "tier"] = UNKNOWN
    note_fallback(~known_sku, "sku")

    launch = pd.to_datetime(sku.map(lambda s: catalogue.get(s, {}).get("launch_date") if isinstance(s, str) else None))
    placed = pd.to_datetime(r["order_placed_at"], format=ORDER_TS_FORMAT, errors="coerce")
    placed = placed.fillna(pd.to_datetime(r["order_placed_at"], errors="coerce"))   # also accept ISO timestamps (API)
    f["product_age_days"] = (placed - launch).dt.days.astype(float)

    # --- address / note: only presence flags and the template bucket, never raw text
    pin = r["delivery_pincode"].astype("string").str.strip()
    f["address_missing"] = (pin.isna() | pin.isin([DEFAULT_PINCODE, "000000", ""])).astype(float)
    f["note_cat"] = r["delivery_note"].map(_note_category).astype(object)
    f["note_present"] = (f.note_cat != "none").astype(float)

    f = f[list(FEATURE_COLUMNS)]
    assert not set(f.columns) & set(BANNED_COLUMNS), "leakage guard: banned column in features"
    return f, fallbacks


def training_records(orders, customers):
    """Training-time order records: orders + the customer fields the warehouse would pass with them."""
    return orders.merge(customers[["customer_id", "shield_member", "city", "state"]],
                        on="customer_id", how="left", validate="many_to_one")
