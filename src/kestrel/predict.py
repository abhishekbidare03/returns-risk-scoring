"""Score test_unlabelled.csv with the saved model.

    python -m kestrel.predict

Writes
  outputs/predictions.csv          order_id, score  (submission; same IDs and order as sample_submission.csv)
  outputs/test_scored_detail.csv   + recommended action and fallbacks per order (git-ignored; avoids re-runs)
  evidence/predictions_check.md    checks and score-distribution comparison (aggregates only)
"""
import hashlib
import json

import joblib
import numpy as np
import pandas as pd
from scipy.stats import ks_2samp

from .config import DATA_DIR, MODELS_DIR, OUTPUTS_DIR, ROOT
from .data import load_pack, read_raw
from .features import build_features, training_records
from .train import FINAL_CONFIG, SELECTION_END, load_training_frame, train_final


def sha256(path):
    """Fingerprint of the exact bytes of a file (to verify the submitted predictions are the checked ones)."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def md_table(df):
    """Minimal markdown table (avoids the optional `tabulate` dependency)."""
    cols = [df.index.name or ""] + [str(c) for c in df.columns]
    rows = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for idx, r in df.iterrows():
        rows.append("| " + " | ".join([str(idx)] + [f"{v:.4g}" if isinstance(v, float) else str(v) for v in r]) + " |")
    return "\n".join(rows)


def load_model():
    meta = json.loads((MODELS_DIR / "model_meta.json").read_text(encoding="utf-8"))
    return joblib.load(MODELS_DIR / "model.joblib"), meta


def score_test(model, meta, pack):
    rec = training_records(pack["test"], pack["customers"])      # shield_member as the warehouse would pass it
    X, fallbacks = build_features(rec, meta["catalogue"])
    p = model.predict_proba(X)
    cut = meta["decision"]["score_cutoff_for_call"]
    detail = pd.DataFrame({
        "order_id": rec["order_id"].to_numpy(),
        "score": p,
        "recommended_action": np.where(p >= cut, "CALL", "SHIP"),
        "fallbacks": fallbacks.map(lambda f: ";".join(f)).to_numpy(),
        "order_ts": rec["order_ts"].to_numpy(),
    })
    return detail


def main():
    model, meta = load_model()
    pack = load_pack()
    detail = score_test(model, meta, pack)
    sample = read_raw(DATA_DIR / "sample_submission.csv")
    sub = sample[["order_id"]].merge(detail[["order_id", "score"]], on="order_id", how="left", validate="one_to_one")

    # ---- checks
    checks = {
        "rows == 2,096": len(sub) == 2096,
        "one row per order_id": sub.order_id.is_unique,
        "same IDs and order as sample_submission": sub.order_id.tolist() == sample.order_id.tolist(),
        "no NaN": bool(sub.score.notna().all()),
        "scores in [0, 1]": bool(sub.score.between(0, 1).all()),
        "no fallbacks needed": bool((detail.fallbacks == "").all()),
    }
    assert all(checks.values()), checks

    OUTPUTS_DIR.mkdir(exist_ok=True)
    # LF line endings on every OS, so the fingerprint is the same on Windows, macOS and Linux
    sub.to_csv(OUTPUTS_DIR / "predictions.csv", index=False, lineterminator="\n")
    detail.drop(columns="order_ts").to_csv(OUTPUTS_DIR / "test_scored_detail.csv", index=False, lineterminator="\n")
    digest = sha256(OUTPUTS_DIR / "predictions.csv")

    # ---- distribution vs walk-forward out-of-fold scores (never the holdout)
    X, y, ts, catalogue, _ = load_training_frame(pack)
    sel_model, oof = train_final(FINAL_CONFIG, X, y, ts, catalogue, end=SELECTION_END)
    oof_p = sel_model.calibrator.transform(oof.raw)
    q = [0.05, 0.25, 0.5, 0.75, 0.9, 0.95]
    dist = pd.DataFrame({"test (Jul-Sep 2026)": np.quantile(sub.score, q), "walk-forward OOF": np.quantile(oof_p, q)}, index=[f"p{int(x*100)}" for x in q])
    dist.loc["mean"] = [sub.score.mean(), oof_p.mean()]
    ks = ks_2samp(sub.score, oof_p)

    cut = meta["decision"]["score_cutoff_for_call"]
    days = (detail.order_ts.max().normalize() - detail.order_ts.min().normalize()).days + 1
    share = float((sub.score >= cut).mean())
    calls_day = (sub.score >= cut).sum() / days
    monthly = detail.assign(month=detail.order_ts.dt.to_period("M")).groupby("month").apply(
        lambda g: pd.Series({"orders": len(g), "share_called": (g.score >= cut).mean(), "calls_per_day": (g.score >= cut).sum() / g.order_ts.dt.days_in_month.iloc[0], "mean_score": g.score.mean()}),
        include_groups=False)

    lines = ["# Predictions check (Phase 7)", "",
             f"Model: `models/model.joblib` (version {meta['model_version']}), trained Apr 2025 – Jun 2026. File: `outputs/predictions.csv` (order_id, score).", "",
             "| Check | Result |", "|---|---|"]
    lines += [f"| {k} | {'PASS' if v else 'FAIL'} |" for k, v in checks.items()]
    lines += ["", "## File fingerprint", "",
              f"SHA-256 of `outputs/predictions.csv`: `{digest}`", "",
              "If the submitted file gives the same SHA-256, it is byte-for-byte the file these checks were run on. "
              "Any change, including opening and re-saving it in Excel, gives a different value. Verify with:", "",
              "- Windows (PowerShell): `Get-FileHash outputs\\predictions.csv -Algorithm SHA256`",
              "- macOS: `shasum -a 256 outputs/predictions.csv`",
              "- Linux: `sha256sum outputs/predictions.csv`"]
    lines += ["", "## Score distribution: test vs walk-forward out-of-fold", "", md_table(dist.round(4)), "",
              f"Kolmogorov–Smirnov distance {ks.statistic:.3f} (p = {ks.pvalue:.2f}). Mean predicted return rate on test: **{sub.score.mean():.1%}** (training return rate 11.4%).", "",
              "## Share at or above the 13.7% call cutoff", "",
              f"- **{share:.1%}** of test orders (vs the **25%** assumed in Phase 5): {int((sub.score >= cut).sum())} orders over {days} days = **{calls_day:.1f} calls/day**.", "",
              md_table(monthly.round(3)), ""]
    (ROOT / "evidence" / "predictions_check.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
