"""Rupee economics of acting on a return-risk score (policy.md §6-7, plan Phase 5).

Per order, with p = calibrated return probability, C = cost of a return, m = margin on the sale:
    ship  : 0
    call  : prevention * p * (C [+ m]) - call_cost      (a prevented return also keeps the sale's margin)
    hold  : cancel * p * C - cancel * (1 - p) * m       (only cancellations avoid a return; good orders lost)
The headline call value is conservative (margin kept on prevented returns is NOT counted).
"""
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from .config import CALL_COST_INR, CALL_PREVENTION_RATE, HOLD_CANCEL_RATE, RETURN_COST_INR

MARGIN_RATE_ASSUMPTION = 0.25   # not in the pack; stated assumption with 15% / 35% sensitivity (policy.md §6)


@dataclass(frozen=True)
class Costs:
    return_cost: float = RETURN_COST_INR
    call_cost: float = CALL_COST_INR
    prevention: float = CALL_PREVENTION_RATE
    cancel: float = HOLD_CANCEL_RATE
    margin_rate: float = MARGIN_RATE_ASSUMPTION
    count_margin_in_call: bool = False      # conservative headline

    def as_dict(self):
        return asdict(self)


def expected_values(p, order_value, costs=Costs()):
    """Expected ₹ net of each action for each order (vectorised). Used by the API."""
    p, v = np.asarray(p, dtype=float), np.asarray(order_value, dtype=float)
    m = costs.margin_rate * v
    kept = m if costs.count_margin_in_call else 0.0
    call = costs.prevention * p * (costs.return_cost + kept) - costs.call_cost
    hold = costs.cancel * p * costs.return_cost - costs.cancel * (1 - p) * m
    return {"ship": np.zeros_like(p), "call": call, "hold": hold}


def call_break_even(order_value=None, costs=Costs()):
    """Risk above which a call pays for itself."""
    kept = costs.margin_rate * np.asarray(order_value, dtype=float) if (costs.count_margin_in_call and order_value is not None) else 0.0
    return costs.call_cost / (costs.prevention * (costs.return_cost + kept))


def realised_value(y, order_value, selected, action, costs=Costs()):
    """₹ outcome of applying `action` to the selected orders, using what actually happened (y = returned).
    Expected values over the random parts (35% prevention, 12% cancellation)."""
    y, v, s = np.asarray(y), np.asarray(order_value, dtype=float), np.asarray(selected, dtype=bool)
    n, returns = int(s.sum()), int(y[s].sum())
    m = costs.margin_rate * v[s]
    if action == "call":
        kept = (m * y[s]).sum() if costs.count_margin_in_call else 0.0
        saved = costs.prevention * (returns * costs.return_cost + kept)
        cost = n * costs.call_cost
        prevented = costs.prevention * returns
        lost_orders = 0.0
    elif action == "hold":
        saved = costs.cancel * returns * costs.return_cost
        cost = costs.cancel * (m * (1 - y[s])).sum()          # margin lost on good orders that cancel
        prevented = costs.cancel * returns
        lost_orders = costs.cancel * (n - returns)
    else:
        raise ValueError(action)
    return {"orders_actioned": n, "returns_among_them": returns, "precision": returns / n if n else np.nan,
            "returns_avoided": prevented, "good_orders_lost": lost_orders,
            "gross_saving": saved, "cost": cost, "net": saved - cost}


def capacity_table(p, y, order_value, shares=(0.02, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50),
                   action="call", costs=Costs(), orders_per_month=None):
    """Act on the top X% by score. Cumulative and marginal (band between consecutive X) ₹ outcomes."""
    p, y, v = np.asarray(p), np.asarray(y), np.asarray(order_value, dtype=float)
    order = np.argsort(-p, kind="stable")
    rows, prev_k, prev_net = [], 0, 0.0
    total_returns = y.sum()
    for x in shares:
        k = int(round(x * len(p)))
        sel = np.zeros(len(p), bool); sel[order[:k]] = True
        band = np.zeros(len(p), bool); band[order[prev_k:k]] = True
        r = realised_value(y, v, sel, action, costs)
        b = realised_value(y, v, band, action, costs)
        row = {"top_share": x, "score_cutoff": float(p[order[k - 1]]), "orders": k, "precision": r["precision"],
               "recall": r["returns_among_them"] / total_returns, "returns_avoided": r["returns_avoided"],
               "net": r["net"], "band_precision": b["precision"], "band_net": b["net"],
               "band_net_per_order": b["net"] / max(b["orders_actioned"], 1)}
        rows.append(row)
        prev_k = k
    t = pd.DataFrame(rows).set_index("top_share")
    n = len(p)
    t["net_per_1000_orders"] = t.net / n * 1000
    if orders_per_month:
        scale = orders_per_month / n
        t["actions_per_month"] = t.orders * scale
        t["returns_avoided_per_month"] = t.returns_avoided * scale
        t["net_per_month"] = t.net * scale
    return t


def recommended_share(table):
    """Declared rule (policy.md §7): the largest top-X% whose marginal band is still net-positive."""
    ok = table.index[table.band_net > 0]
    contiguous = []
    for x in table.index:
        if x in ok:
            contiguous.append(x)
        else:
            break
    return contiguous[-1] if contiguous else None
