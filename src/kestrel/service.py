"""Scoring service used by the API: loads only models/model.joblib + models/model_meta.json.

Never reads data/, never calls an external API, never logs or stores request contents.
"""
import json

import joblib
import pandas as pd

from .config import MODELS_DIR
from .economics import Costs, expected_values
from .features import build_features
from .reasons import explain

MODEL_FIELDS = ("sku", "payment_mode", "promised_delivery_days", "discount_pct",
                "customer_prior_orders", "customer_prior_returns", "shield_member")
# fallback name in features.py -> reason group it neutralises
FALLBACK_GROUPS = {"shield_member": "shield", "payment_mode": "payment_mode", "sku": "family"}
FALLBACK_TEXT = {
    "shield_member": "Shield status unknown - scored as the average customer (22% Shield)",
    "payment_mode": "Payment mode unknown - scored as the average payment mix",
    "sku": "SKU not in the catalogue - product family taken from the SKU code, or the average family if unreadable",
}


class ScoringService:
    def __init__(self, models_dir=MODELS_DIR):
        self.model = joblib.load(models_dir / "model.joblib")
        self.meta = json.loads((models_dir / "model_meta.json").read_text(encoding="utf-8"))
        d = self.meta["decision"]
        self.cutoff = d["score_cutoff_for_call"]
        self.low_below = d["risk_bands"]["low_below"]
        self.typical = d["typical_return_rate"]
        self.costs = Costs(**d["costs"])

    def band(self, p):
        return "High" if p >= self.cutoff else ("Medium" if p >= self.low_below else "Low")

    def score(self, order):
        """`order`: validated dict with the 7 model fields (shield_member / payment_mode may be None or 'unknown')."""
        rec = pd.DataFrame([{k: order.get(k) for k in MODEL_FIELDS}])
        X, fb = build_features(rec, self.meta["catalogue"])
        fallbacks = [f for f in fb.iloc[0] if f in FALLBACK_GROUPS]
        p = float(self.model.predict_proba(X)[0])
        raising, lowering, _ = explain(self.model, X, unknown_groups={FALLBACK_GROUPS[f] for f in fallbacks})
        action = "CALL" if p >= self.cutoff else "SHIP"
        ratio = p / self.typical
        return {
            "order_id": order.get("order_id"),
            "return_probability": round(p, 4),
            "risk_band": self.band(p),
            "vs_typical": f"{ratio:.1f}× a typical order ({self.typical:.1%})",
            "recommended_action": action,
            "note": "Don't hold: call to confirm before dispatch." if action == "CALL" else "Ship as normal.",
            "call_value_inr": round(float(expected_values([p], [0.0], self.costs)["call"][0]), 0),
            "reasons_raising": raising,
            "reasons_lowering": lowering,
            "fallbacks_used": [FALLBACK_TEXT[f] for f in fallbacks],
            "family": X.family.iloc[0],
            "model_version": self.meta["model_version"],
        }

    def health(self):
        m = self.meta["metrics"]
        return {
            "status": "ok", "model_version": self.meta["model_version"], "model": "logistic regression",
            "inputs": list(MODEL_FIELDS), "call_cutoff": round(self.cutoff, 4),
            "risk_bands": {"Low": f"< {self.low_below:.0%}", "Medium": f"{self.low_below:.0%} - {self.cutoff:.1%}",
                           "High (CALL)": f">= {self.cutoff:.1%}"},
            "walk_forward_roc_auc": {k: v["roc_auc"] for k, v in m["walk_forward"].items()},
            "holdout_roc_auc": m["holdout_apr_jun_2026"]["roc_auc"],
            "skus": sorted(self.meta["catalogue"]),
            "external_api": "none", "llm": "none",
        }
