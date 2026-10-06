"""Paths, formats and business constants. Every value cites its source (policy.md)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"            # needed for (re)training only - never read by the service
MODELS_DIR = ROOT / "models"
OUTPUTS_DIR = ROOT / "outputs"
FIGURES_DIR = ROOT / "evidence" / "figures"

# policy.md §2 - C2: explicit formats (files were saved by Excel, US order)
ORDER_TS_FORMAT = "%m/%d/%Y %H:%M"
DATE_FORMAT = "%m/%d/%Y"

# policy.md §2 - C4: Oct-2025 order values were stored in paise by the new gateway
PAISE_MONTH = "2025-10"

# policy.md §2 - C5: Excel turned the default pincode 000000 into 0
DEFAULT_PINCODE = "0"

# policy.md §4 - recorded after dispatch, identifiers, bookkeeping, PII, label
BANNED_COLUMNS = (
    "last_service_event_type",
    "pickup_scheduled_at",
    "source",
    "order_id",
    "customer_id",
    "delivery_note",   # only note_present / note_cat may be derived
    "returned",
)

# policy.md §6 - costs (ops-policy §4, §7)
RETURN_COST_INR = 1150          # Finance figure; sensitivity case below
RETURN_COST_SENSITIVITY_INR = 600
CALL_COST_INR = 45
CALL_PREVENTION_RATE = 0.35
HOLD_CANCEL_RATE = 0.12
