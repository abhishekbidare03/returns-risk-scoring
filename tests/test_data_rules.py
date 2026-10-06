"""policy.md §2 cleaning rules C1-C4, checked against the real pack (skipped without data/)."""
import pandas as pd

from kestrel.config import DATA_DIR
from kestrel.data import read_raw

from .conftest import needs_data


@needs_data
def test_c1_excel_artefacts_removed(pack):
    for name in ("train", "test", "customers", "products"):
        df = pack[name]
        assert not any(c.startswith("Unnamed") for c in df.columns)
    assert len(pack["products"]) == 21
    assert len(pack["customers"]) == 9000


@needs_data
def test_c2_dates_parse_and_ranges(pack):
    tr, te = pack["train"], pack["test"]
    assert tr.order_ts.notna().all() and te.order_ts.notna().all()
    assert tr.order_ts.min() >= pd.Timestamp("2025-04-01") and tr.order_ts.max() < pd.Timestamp("2026-07-01")
    assert te.order_ts.min() >= pd.Timestamp("2026-07-01") and te.order_ts.max() < pd.Timestamp("2026-10-01")
    assert (tr.order_ts.dt.day > 12).any()          # month/day not swapped


@needs_data
def test_c3_dedupe(pack):
    tr = pack["train"]
    assert tr.order_id.is_unique and len(tr) == 10504
    assert set(tr.source) == {"crm"}
    assert round(tr.returned.mean(), 4) == 0.1142


@needs_data
def test_c4_paise_fix(pack):
    tr = pack["train"].merge(pack["products"][["sku", "list_price_inr"]], on="sku")
    expected = tr.list_price_inr * tr.qty * (1 - tr.discount_pct / 100)
    assert ((tr.order_value_inr / expected - 1).abs() < 1e-6).all()


@needs_data
def test_test_file_matches_sample_submission(pack):
    sample = read_raw(DATA_DIR / "sample_submission.csv")
    assert pack["test"].order_id.is_unique
    assert sorted(sample.order_id) == sorted(pack["test"].order_id)
