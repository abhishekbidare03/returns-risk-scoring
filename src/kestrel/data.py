"""Load and clean the Kestrel data pack - cleaning rules C1-C4 of policy.md §2.

Only training / analysis code calls this module. The service never reads data/.
"""
from pathlib import Path

import pandas as pd

from .config import DATA_DIR, DATE_FORMAT, ORDER_TS_FORMAT, PAISE_MONTH


def read_raw(path):
    """C1: read as text (no dtype guessing), drop Excel artefact columns and blank rows."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])
    df = df.loc[:, ~df.columns.str.startswith("Unnamed")]
    return df[~df.isna().all(axis=1)].reset_index(drop=True)


def clean_orders(df):
    """C2 parse dates, C3 dedupe (keep the crm copy), C4 paise fix. Returns a new frame."""
    df = df.copy()
    df["order_ts"] = pd.to_datetime(df["order_placed_at"], format=ORDER_TS_FORMAT)
    df["pickup_ts"] = pd.to_datetime(df["pickup_scheduled_at"], format=ORDER_TS_FORMAT)

    # C3 - partner_feed copies are identical to their crm row; "crm" sorts first
    df = (df.sort_values(["order_id", "source"])
            .drop_duplicates("order_id", keep="first")
            .sort_values("order_ts")
            .reset_index(drop=True))

    for col in ["discount_pct", "order_value_inr"]:
        df[col] = df[col].astype(float)
    for col in ["qty", "promised_delivery_days", "customer_prior_orders", "customer_prior_returns"]:
        df[col] = df[col].astype(int)

    # C4 - Oct-2025 values are 100x (paise)
    paise = df["order_ts"].dt.to_period("M") == pd.Period(PAISE_MONTH)
    df["order_value_inr"] = df["order_value_inr"].where(~paise, df["order_value_inr"] / 100)

    if "returned" in df:
        df["returned"] = df["returned"].astype(int)
    return df


def clean_customers(df):
    df = df.copy()
    df["signup_date"] = pd.to_datetime(df["signup_date"], format=DATE_FORMAT)
    return df


def clean_products(df):
    df = df.copy()
    df["launch_date"] = pd.to_datetime(df["launch_date"], format=DATE_FORMAT)
    df["list_price_inr"] = df["list_price_inr"].astype(float)
    df["warranty_months"] = df["warranty_months"].astype(int)
    return df


def load_pack(data_dir=DATA_DIR):
    """Return cleaned train, test, customers, products."""
    data_dir = Path(data_dir)
    return {
        "train": clean_orders(read_raw(data_dir / "train.csv")),
        "test": clean_orders(read_raw(data_dir / "test_unlabelled.csv")),
        "customers": clean_customers(read_raw(data_dir / "customers.csv")),
        "products": clean_products(read_raw(data_dir / "products.csv")),
    }


def attach_reference(orders, customers, products):
    """Training-time join. At serve time shield_member/city/state come with the order
    and product fields from the catalogue in model_meta.json (policy.md §3)."""
    out = orders.merge(customers, on="customer_id", how="left", validate="many_to_one")
    return out.merge(products, on="sku", how="left", validate="many_to_one")
