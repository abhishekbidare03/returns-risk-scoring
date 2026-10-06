"""Kestrel returns-risk service.

    uvicorn app.main:app --port 8000      ->  http://localhost:8000

Loads only models/model.joblib + models/model_meta.json (no data/, no API key, no LLM).
Request bodies are never logged or stored.
"""
import json
import sys
from pathlib import Path
from typing import Literal, Optional

ROOT = Path(__file__).resolve().parents[1]
try:
    import kestrel  # noqa: F401  (installed by `pip install -r requirements.txt`, which includes `-e .`)
except ImportError:  # fallback when the package wasn't installed
    sys.path.insert(0, str(ROOT / "src"))

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from kestrel.service import ScoringService

STATIC = Path(__file__).resolve().parent / "static"
SAMPLES = Path(__file__).resolve().parent / "samples.json"
PAYMENT_MODES = ("cod", "emi", "prepaid_card", "prepaid_upi")

# Why a field that isn't one of the 7 inputs is ignored (names only; values are never echoed)
IGNORED_WHY = {
    "last_service_event_type": "recorded after dispatch (would leak the outcome)",
    "pickup_scheduled_at": "recorded after dispatch (would leak the outcome)",
    "returned": "the outcome itself",
    "delivery_note": "personal free text - not needed by the model",
    "delivery_pincode": "address data - not needed by the model",
    "city": "not used by the model", "state": "not used by the model",
    "customer_id": "identifier - not used", "source": "import bookkeeping - not used",
}

service = ScoringService()
app = FastAPI(title="Kestrel returns risk", version=service.meta["model_version"],
              description="Pre-dispatch return-risk score with a call/ship recommendation. No external API, no LLM.")


class Order(BaseModel):
    """One order at dispatch. Seven fields; anything else is ignored and listed in `ignored_fields`."""
    model_config = ConfigDict(extra="allow", json_schema_extra={"example": {
        "order_id": "SAMPLE-001", "sku": "KH-RV-02", "payment_mode": "cod", "promised_delivery_days": 8,
        "discount_pct": 18, "customer_prior_orders": 3, "customer_prior_returns": 1, "shield_member": "Y"}})

    order_id: Optional[str] = Field(None, max_length=64, description="Echoed back; not used for scoring")
    sku: str = Field(..., min_length=1, max_length=40, description="Kestrel SKU, e.g. KH-AF-01")
    payment_mode: Optional[Literal["cod", "emi", "prepaid_card", "prepaid_upi", "unknown"]] = Field(
        None, description="Missing or 'unknown' -> scored as the average payment mix (reported)")
    promised_delivery_days: int = Field(..., ge=1, le=60)
    discount_pct: float = Field(..., ge=0, le=100)
    customer_prior_orders: int = Field(..., ge=0, le=10000)
    customer_prior_returns: int = Field(..., ge=0, le=10000)
    shield_member: Optional[Literal["Y", "N", "unknown"]] = Field(
        None, description="Y / N; missing or 'unknown' -> scored as the average customer (reported)")

    @field_validator("payment_mode", mode="before")
    @classmethod
    def _payment_lower(cls, v):
        return v.strip().lower() if isinstance(v, str) else v

    @field_validator("shield_member", mode="before")
    @classmethod
    def _shield_norm(cls, v):
        if isinstance(v, bool):
            return "Y" if v else "N"
        if isinstance(v, str):
            s = v.strip()
            return {"y": "Y", "yes": "Y", "n": "N", "no": "N", "unknown": "unknown"}.get(s.lower(), s)
        return v

    @model_validator(mode="after")
    def _returns_le_orders(self):
        if self.customer_prior_returns > self.customer_prior_orders:
            raise ValueError("customer_prior_returns cannot exceed customer_prior_orders")
        return self


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    problems = []
    for e in exc.errors():
        field = ".".join(str(p) for p in e["loc"] if p != "body") or "body"
        item = {"field": field, "problem": e["msg"]}
        expected = (e.get("ctx") or {}).get("expected")
        if expected:
            item["allowed_values"] = expected
        problems.append(item)
    return JSONResponse(status_code=422, content={"error": "The order could not be scored", "problems": problems})


@app.post("/score")
def score(order: Order):
    extra = sorted((order.model_extra or {}).keys())
    result = service.score(order.model_dump())
    result["ignored_fields"] = extra
    result["warnings"] = [f"'{k}' ignored: {IGNORED_WHY.get(k, 'not used by the model')}" for k in extra]
    return result


@app.get("/health")
def health():
    return service.health()


@app.get("/samples")
def samples():
    return json.loads(SAMPLES.read_text(encoding="utf-8"))


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")
