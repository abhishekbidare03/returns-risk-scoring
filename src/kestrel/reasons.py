"""Plain-language reasons from the logistic-regression model (plan Phase 8).

Each feature's contribution is measured relative to the **average order** on the log-odds scale:
  numeric   : coefficient x standardised value (the scaler is centred on the training mean)
  category  : sum over levels of coefficient x (indicator - training share of that level)
The four customer-history features are correlated (their individual coefficients aren't interpretable), so
they are summed into one "customer history" reason. A field that fell back to an average contributes nothing.
"""
import numpy as np
import pandas as pd

HISTORY = ("customer_prior_returns", "customer_prior_orders", "prior_return_rate", "has_prior_return")
GROUPS = {f: "history" for f in HISTORY} | {
    "shield": "shield", "payment_mode": "payment_mode", "family": "family",
    "promised_delivery_days": "promised_delivery_days", "discount_pct": "discount_pct",
}
MIN_EFFECT = 0.10      # log-odds (~10% relative change in odds); smaller effects are not worth a sentence

FAMILY_PLURAL = {
    "Air Fryer": "Air fryers", "Ceiling Fan": "Ceiling fans", "Induction Cooktop": "Induction cooktops",
    "Mixer Grinder": "Mixer grinders", "Robot Vacuum": "Robot vacuums", "Room Heater": "Room heaters",
    "Water Purifier": "Water purifiers",
}
PAYMENT_WORDS = {"cod": "Cash-on-delivery", "emi": "EMI", "prepaid_card": "Card-prepaid", "prepaid_upi": "UPI-prepaid"}


def contributions(model, X_row):
    """Log-odds contribution of each reason group for one order (relative to the average order)."""
    pre = model.pipeline.named_steps["pre"]
    coef = model.pipeline.named_steps["model"].coef_[0]
    z = pre.transform(X_row[model.features])[0]
    names = pre.get_feature_names_out()
    out = {}
    for name, c, v in zip(names, coef, z):
        kind, rest = name.split("__", 1)
        if kind == "num":
            feat, centred = rest, v                                   # already centred on the training mean
        else:
            feat = next(f for f in ("payment_mode", "family") if rest.startswith(f + "_"))
            level = rest[len(feat) + 1:]
            centred = v - model.marginals[feat].get(level, 0.0)
        g = GROUPS[feat]
        out[g] = out.get(g, 0.0) + float(c * centred)
    return out


def _sentence(group, up, x, typical):
    if group == "history":
        r, o = int(x.customer_prior_returns), int(x.customer_prior_orders)
        if up:
            return f"Customer has returned {r} of {o} previous order{'s' if o != 1 else ''}" if r else "Customer's order history points to higher risk"
        if o == 0:
            return "No previous orders on record, so no returns either"
        return f"No returns in {o} previous order{'s' if o != 1 else ''}" if r == 0 else f"Customer's return history ({r} of {o}) is better than most"
    if group == "shield":
        return ("Shield members return more often; returns are free for them" if up
                else "Not a Shield member; these orders are returned less often")
    if group == "payment_mode":
        word = PAYMENT_WORDS.get(x.payment_mode, "This payment mode's")
        return f"{word} orders are returned {'more' if up else 'less'} often"
    if group == "family":
        fam = FAMILY_PLURAL.get(x.family, x.family)
        return f"{fam} are returned more often than most products" if up else f"{fam} are returned less often than most products"
    if group == "promised_delivery_days":
        d = int(x.promised_delivery_days)
        return f"{'Longer' if up else 'Shorter'} delivery promise than usual ({d} day{'s' if d != 1 else ''}; typical {typical['promised_delivery_days']:.0f})"
    if group == "discount_pct":
        return f"{'Bigger' if up else 'Smaller'} discount than usual ({x.discount_pct:.0f}%; typical {typical['discount_pct']:.0f}%)"
    raise ValueError(group)


def explain(model, X_row, unknown_groups=(), n_up=3, n_down=1):
    """Return (reasons raising risk, reasons lowering risk) for one order (a one-row features frame).
    `unknown_groups` (fallbacks) are scored as average and therefore not given as reasons."""
    row = X_row.copy()
    for f, shares in model.marginals.items():                 # any concrete value works; the group is dropped below
        if f in row and (pd.isna(row[f].iloc[0]) or row[f].iloc[0] == "unknown"):
            row[f] = max(shares, key=shares.get)
    contrib = {g: c for g, c in contributions(model, row).items() if g not in unknown_groups}
    x = row.iloc[0]
    pre = model.pipeline.named_steps["pre"]
    num = pre.named_transformers_["num"]
    typical = dict(zip(pre.transformers_[0][2], num.mean_))
    ups = sorted([(c, g) for g, c in contrib.items() if c > MIN_EFFECT], reverse=True)[:n_up]
    downs = sorted([(c, g) for g, c in contrib.items() if c < -MIN_EFFECT])[:n_down]
    return [_sentence(g, True, x, typical) for _, g in ups], [_sentence(g, False, x, typical) for _, g in downs], contrib
