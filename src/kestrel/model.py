"""Model pipelines, sigmoid calibration and explicit unknown-value handling (policy.md §5.7, plan Phase 4).

No class weighting or resampling anywhere: the model is trained on the true class balance because its
probabilities drive the rupee decisions.
"""
from itertools import product

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler

from .features import CATEGORICAL_FEATURES, NUMERIC_FEATURES, UNKNOWN

# Directions for the optional monotonic HGB (numeric features only; sklearn can't constrain categoricals)
MONOTONIC_INCREASING = ("customer_prior_returns", "prior_return_rate", "promised_delivery_days", "discount_pct")


def split_features(features, extra_numeric=(), extra_categorical=()):
    num = [f for f in features if f in NUMERIC_FEATURES or f in extra_numeric]
    cat = [f for f in features if f in CATEGORICAL_FEATURES or f in extra_categorical]
    return num, cat


def make_estimator(kind, features, params=None, monotonic=False, extra_numeric=(), extra_categorical=()):
    """'lr' = scaled numerics + one-hot categoricals + L2 logistic regression; 'hgb' = gradient boosting
    with native categorical handling. Column order is numerics then categoricals."""
    params = dict(params or {})
    num, cat = split_features(features, extra_numeric, extra_categorical)
    if kind == "lr":
        pre = ColumnTransformer([
            ("num", StandardScaler(), num),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cat),
        ])
        est = LogisticRegression(C=params.get("C", 1.0), max_iter=5000)
    elif kind == "hgb":
        pre = ColumnTransformer([
            ("num", "passthrough", num),
            ("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1), cat),
        ])
        cst = [1 if (monotonic and f in MONOTONIC_INCREASING) else 0 for f in num] + [0] * len(cat)
        est = HistGradientBoostingClassifier(
            learning_rate=params.get("learning_rate", 0.1),
            max_leaf_nodes=params.get("max_leaf_nodes", 31),
            max_iter=params.get("max_iter", 100),
            l2_regularization=params.get("l2_regularization", 0.0),
            min_samples_leaf=params.get("min_samples_leaf", 40),
            categorical_features=[False] * len(num) + [True] * len(cat),
            monotonic_cst=cst if any(cst) else None,
            early_stopping=False,
            random_state=0,
        )
    else:
        raise ValueError(kind)
    return Pipeline([("pre", pre), ("model", est)])


def _logit(p):
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


class SigmoidCalibrator:
    """Platt scaling on the logit of the raw score: p = 1 / (1 + exp(-(a * logit(raw) + b)))."""

    def __init__(self, a=1.0, b=0.0):
        self.a, self.b = float(a), float(b)

    def fit(self, raw, y):
        lr = LogisticRegression(C=1e6, max_iter=1000).fit(_logit(raw).reshape(-1, 1), np.asarray(y))
        self.a, self.b = float(lr.coef_[0, 0]), float(lr.intercept_[0])
        return self

    def transform(self, raw):
        return 1 / (1 + np.exp(-(self.a * _logit(raw) + self.b)))


class ReturnRiskModel:
    """Fitted pipeline + calibrator + explicit handling of unknown inputs.

    An unknown value of a discrete feature (Shield, metro/city, payment mode, gift, family, ...) is scored as the
    training-share-weighted average of the calibrated scores for each known value. Unknown product age (unknown
    SKU) takes the training median. Required numeric fields must be present.
    """

    REQUIRED_NUMERIC = ("promised_delivery_days", "discount_pct", "customer_prior_orders",
                        "customer_prior_returns", "prior_return_rate", "has_prior_return")

    def __init__(self, pipeline, features, calibrator, marginals, numeric_fill, kind, params):
        self.pipeline, self.features, self.calibrator = pipeline, list(features), calibrator
        self.marginals, self.numeric_fill = marginals, numeric_fill
        self.kind, self.params = kind, params

    # -- construction -------------------------------------------------------------------------
    @classmethod
    def fit(cls, X, y, features, kind, params=None, monotonic=False, calibrator=None, sample_weight=None):
        pipe = make_estimator(kind, features, params, monotonic)
        fit_kw = {"model__sample_weight": sample_weight} if sample_weight is not None else {}
        pipe.fit(X[features], y, **fit_kw)
        marginals = {}
        for f in features:
            if f in CATEGORICAL_FEATURES or f in ("shield", "metro", "is_gift"):
                share = X[f].value_counts(normalize=True)
                marginals[f] = {(v.item() if hasattr(v, "item") else v): float(w) for v, w in share.items()}
        numeric_fill = {f: float(X[f].median()) for f in features if f == "product_age_days"}
        return cls(pipe, features, calibrator or SigmoidCalibrator(), marginals, numeric_fill, kind, params or {})

    # -- scoring ------------------------------------------------------------------------------
    def raw_proba(self, X):
        return self.pipeline.predict_proba(X[self.features])[:, 1]

    def _unknown_mask(self, X, f):
        col = X[f]
        if f in CATEGORICAL_FEATURES:
            return (col == UNKNOWN) | col.isna()
        return col.isna()

    def predict_proba(self, X):
        """Calibrated return probability; unknown discrete values are averaged over their known values."""
        X = X[self.features].copy()
        for f, v in self.numeric_fill.items():
            X[f] = X[f].fillna(v)
        bad = [f for f in self.REQUIRED_NUMERIC if f in X and X[f].isna().any()]
        if bad:
            raise ValueError(f"required numeric fields missing: {bad}")

        unknown = pd.DataFrame({f: self._unknown_mask(X, f) for f in self.marginals}, index=X.index)
        has_unknown = unknown.any(axis=1)
        out = pd.Series(np.nan, index=X.index)
        if (~has_unknown).any():
            known = X[~has_unknown]
            out[known.index] = self.calibrator.transform(self.raw_proba(known))
        for i in X.index[has_unknown]:
            cols = [f for f in self.marginals if unknown.at[i, f]]
            combos = list(product(*[list(self.marginals[f].items()) for f in cols]))
            rows = pd.DataFrame([X.loc[i]] * len(combos)).reset_index(drop=True)
            weights = np.ones(len(combos))
            for k, combo in enumerate(combos):
                for f, (value, w) in zip(cols, combo):
                    rows.at[k, f] = value
                    weights[k] *= w
            for f in rows:   # restore dtypes after row-wise assignment
                rows[f] = rows[f].astype(X[f].dtype) if f in NUMERIC_FEATURES else rows[f].astype(object)
            p = self.calibrator.transform(self.raw_proba(rows))
            out[i] = float(np.average(p, weights=weights))
        return out.to_numpy()
