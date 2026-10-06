"""Walk-forward evaluation and final training.

    python -m kestrel.train      # retrain from data/ and write models/model.joblib + models/model_meta.json

Only this module (and the notebooks) need data/; the service loads the saved artefacts.
"""
import json
from datetime import date

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from .config import MODELS_DIR
from .data import load_pack
from .features import build_features, catalogue_from_products, training_records
from .model import ReturnRiskModel, SigmoidCalibrator, make_estimator

# Walk-forward folds (policy.md §5.7): validate on each window, train on everything before it.
FOLDS = (("2025-07-01", "2025-10-01"), ("2025-10-01", "2026-01-01"), ("2026-01-01", "2026-04-01"))
FOLD_NAMES = ("Jul-Sep 25", "Oct-Dec 25", "Jan-Mar 26")
SELECTION_END = "2026-04-01"         # Apr-Jun 2026 is the one-time holdout
NOISE = 0.005                        # policy.md §5.7

# Chosen configuration - from notebooks/03_modeling.ipynb §10 (rules in policy.md §5.7; key_findings.md Phase 4)
FINAL_CONFIG = {
    "kind": "lr",
    "features": ["promised_delivery_days", "customer_prior_returns", "customer_prior_orders", "prior_return_rate",
                 "has_prior_return", "discount_pct", "shield", "payment_mode", "family"],
    "params": {},                 # C = 1 (no grid point beat the default by the noise rule)
    "monotonic": False,
    "half_life": None,            # recency weighting gave <= 0.001 AUC
    "calibration_folds": [0, 1, 2],   # fold 1 not clearly less confident (slopes 1.08 / 0.93 / 0.96)
}


def load_training_frame(pack=None):
    """Features + label + order timestamp for all labelled orders, and the product catalogue."""
    pack = pack or load_pack()
    catalogue = catalogue_from_products(pack["products"])
    rec = training_records(pack["train"], pack["customers"])
    X, _ = build_features(rec, catalogue)
    return X, rec["returned"].to_numpy(), rec["order_ts"].reset_index(drop=True), catalogue, pack


def recency_weights(ts, ref, half_life_months):
    if not half_life_months:
        return None
    age_months = (pd.Timestamp(ref) - ts).dt.days / 30.44
    return np.power(0.5, age_months / half_life_months).to_numpy()


def walk_forward(X, y, ts, features, kind, params=None, monotonic=False, half_life=None, extra=None, folds=FOLDS):
    """Fit on each fold's past, score its window. Returns per-fold AUCs and the out-of-fold raw scores."""
    extra = extra or {}
    aucs, oof = [], []
    for start, end in folds:
        tr_m = (ts < start).to_numpy()
        va_m = ((ts >= start) & (ts < end)).to_numpy()
        pipe = make_estimator(kind, features, params, monotonic, **extra)
        w = recency_weights(ts[tr_m], start, half_life)
        pipe.fit(X.loc[tr_m, features], y[tr_m], **({"model__sample_weight": w} if w is not None else {}))
        p = pipe.predict_proba(X.loc[va_m, features])[:, 1]
        aucs.append(roc_auc_score(y[va_m], p))
        oof.append(pd.DataFrame({"fold": len(oof), "y": y[va_m], "raw": p}, index=np.flatnonzero(va_m)))
    return np.array(aucs), pd.concat(oof)


def compare(base_aucs, new_aucs, noise=NOISE):
    """policy.md §5.7: a change counts only if it improves AUC by >= noise on at least 2 of 3 folds."""
    d = np.asarray(new_aucs) - np.asarray(base_aucs)
    return {"delta_per_fold": np.round(d, 4).tolist(), "mean_delta": round(float(d.mean()), 4),
            "folds_improved": int((d >= noise).sum()), "passes": bool((d >= noise).sum() >= 2)}


def paired_bootstrap(oof_a, oof_b, n=300, seed=0):
    """95% interval of the mean (over folds) paired AUC difference b - a. Transparency only - never decides."""
    rng = np.random.default_rng(seed)
    diffs = []
    folds = [(g.y.to_numpy(), g.raw.to_numpy(), oof_b.loc[g.index, "raw"].to_numpy()) for _, g in oof_a.groupby("fold")]
    for _ in range(n):
        ds = []
        for yy, pa, pb in folds:
            k = rng.integers(0, len(yy), len(yy))
            if yy[k].min() == yy[k].max():
                continue
            ds.append(roc_auc_score(yy[k], pb[k]) - roc_auc_score(yy[k], pa[k]))
        diffs.append(np.mean(ds))
    return [round(float(np.percentile(diffs, 2.5)), 4), round(float(np.percentile(diffs, 97.5)), 4)]


def ranking_metrics(y, p, tops=(0.05, 0.10, 0.20)):
    y, p = np.asarray(y), np.asarray(p)
    out = {"roc_auc": roc_auc_score(y, p), "pr_auc": average_precision_score(y, p), "brier": brier_score_loss(y, p),
           "base_rate": y.mean(), "orders": len(y)}
    order = np.argsort(-p, kind="stable")
    for t in tops:
        k = int(round(t * len(y)))
        hit = y[order[:k]].sum()
        out[f"precision_top{int(t*100)}"] = hit / k
        out[f"recall_top{int(t*100)}"] = hit / y.sum()
    return {k: round(float(v), 4) for k, v in out.items()}


def fit_calibrator(oof, folds_used):
    sel = oof[oof.fold.isin(folds_used)]
    return SigmoidCalibrator().fit(sel.raw, sel.y)


def train_final(config, X, y, ts, catalogue, end=None):
    """Fit the chosen configuration on all orders before `end` (None = all) with the OOF calibrator."""
    _, oof = walk_forward(X, y, ts, config["features"], config["kind"], config.get("params"),
                          config.get("monotonic", False), config.get("half_life"))
    cal = fit_calibrator(oof, config["calibration_folds"])
    m = (ts < end).to_numpy() if end else np.ones(len(y), bool)
    w = recency_weights(ts[m], ts[m].max(), config.get("half_life"))
    model = ReturnRiskModel.fit(X[m], y[m], config["features"], config["kind"], config.get("params"),
                                config.get("monotonic", False), cal, w)
    return model, oof


RANGE_FIELDS = ("promised_delivery_days", "discount_pct", "customer_prior_orders", "customer_prior_returns")


def input_ranges(X):
    """Training min/max of the numeric inputs; the service caps out-of-range values to these (policy.md §3)."""
    return {f: [float(X[f].min()), float(X[f].max())] for f in RANGE_FIELDS}


def save(model, catalogue, config, metrics, path=MODELS_DIR, ranges=None, keep=None):
    """Write model.joblib + model_meta.json. `keep`: extra blocks to carry over (e.g. the Phase 5 decision)."""
    path.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path / "model.joblib")
    meta = {
        "model_version": date.today().isoformat(),
        "kind": config["kind"], "params": config.get("params", {}), "features": config["features"],
        "monotonic": config.get("monotonic", False), "half_life_months": config.get("half_life"),
        "calibrator": {"a": model.calibrator.a, "b": model.calibrator.b,
                       "fitted_on_folds": [FOLD_NAMES[i] for i in config["calibration_folds"]]},
        "unknown_value_weights": model.marginals, "numeric_fill": model.numeric_fill,
        "training_window": config.get("training_window"), "metrics": metrics,
        "input_ranges": ranges or {},
        "catalogue": catalogue,
    }
    meta.update(keep or {})
    (path / "model_meta.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    return meta


def main():
    if FINAL_CONFIG is None:
        raise SystemExit("FINAL_CONFIG not set - run notebooks/03_modeling.ipynb first")
    X, y, ts, catalogue, _ = load_training_frame()
    model, _ = train_final(FINAL_CONFIG, X, y, ts, catalogue)
    meta_path = MODELS_DIR / "model_meta.json"
    old = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    keep = {k: old[k] for k in ("decision",) if k in old}          # Phase 5 decision lives in the meta too
    save(model, catalogue, dict(FINAL_CONFIG, training_window="2025-04-01 to 2026-06-30"), old.get("metrics", {}),
         ranges=input_ranges(X), keep=keep)
    print("saved", MODELS_DIR / "model.joblib")


if __name__ == "__main__":
    main()
