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

# ---------------------------------------------------------------------------
# Feature contract (policy.md §3). Known levels come from the training pack;
# anything else is mapped to "unknown" and reported as a fallback.
SALES_CHANNELS = ("app", "marketplace", "partner_outlet", "web")
PAYMENT_MODES = ("cod", "emi", "prepaid_card", "prepaid_upi")
FAMILY_BY_CODE = {
    "AF": "Air Fryer", "CF": "Ceiling Fan", "IC": "Induction Cooktop", "MG": "Mixer Grinder",
    "RH": "Room Heater", "RV": "Robot Vacuum", "WP": "Water Purifier",
}
TIERS = ("Lite", "Pro", "Max")
CITIES = (
    "Aurangabad", "Bengaluru", "Bhopal", "Chennai", "Coimbatore", "Delhi", "Hubballi", "Hyderabad",
    "Indore", "Jaipur", "Kota", "Lucknow", "Mumbai", "Mysuru", "Nagpur", "Nashik", "Pune", "Warangal",
)
METRO_CITIES = ("Bengaluru", "Chennai", "Delhi", "Hyderabad", "Mumbai", "Pune")
# Recurring delivery-note templates (digits -> "#"); anything else is "other" (notebook 01 §8)
NOTE_TEMPLATES = (
    "Call before delivery", "Customer requested morning slot", "Deliver after # pm",
    "Deliver to neighbour flat # if not home", "Do not call, WhatsApp only", "Fragile - handle with care",
    "Gate code #, call before delivery", "Landmark: opposite Axis Bank ATM", "Landmark: opposite Big Bazaar",
    "Landmark: opposite HP petrol pump", "Landmark: opposite Metro pillar #", "Landmark: opposite Reliance Fresh",
    "Landmark: opposite St. Mary's school", "Leave with security", "Office address, weekdays only",
    "Ring twice", "Third floor, no lift",
)
