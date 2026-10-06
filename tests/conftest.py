import pytest

from kestrel.config import DATA_DIR

HAS_DATA = (DATA_DIR / "train.csv").exists()
needs_data = pytest.mark.skipif(not HAS_DATA, reason="data pack not present (only needed for retraining)")

# Small catalogue so feature tests run without the data pack
CATALOGUE = {
    "KH-AF-01": {"family": "Air Fryer", "tier": "Lite", "list_price_inr": 5199.0, "launch_date": "2023-11-04"},
    "KH-RV-03": {"family": "Robot Vacuum", "tier": "Max", "list_price_inr": 29698.0, "launch_date": "2023-10-26"},
}


@pytest.fixture(scope="session")
def pack():
    if not HAS_DATA:
        pytest.skip("data pack not present")
    from kestrel.data import load_pack
    return load_pack()


@pytest.fixture
def order():
    """One synthetic dispatch-time order record (no real data)."""
    return {
        "sku": "KH-RV-03", "payment_mode": "cod", "promised_delivery_days": 8, "discount_pct": 22.0,
        "customer_prior_orders": 4, "customer_prior_returns": 2, "sales_channel": "marketplace", "qty": 1,
        "is_gift": "Y", "delivery_pincode": "0", "delivery_note": "Ring twice",
        "order_placed_at": "8/14/2026 18:05", "shield_member": "Y", "city": "Kota", "state": "RJ",
    }
