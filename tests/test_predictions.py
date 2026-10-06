"""Submission file format (skipped until `python -m kestrel.predict` has run)."""
import pandas as pd
import pytest

from kestrel.config import DATA_DIR, OUTPUTS_DIR
from kestrel.data import read_raw

PRED = OUTPUTS_DIR / "predictions.csv"


@pytest.mark.skipif(not PRED.exists() or not (DATA_DIR / "sample_submission.csv").exists(),
                    reason="predictions or sample submission not present")
def test_predictions_match_sample_submission():
    sub = pd.read_csv(PRED, dtype={"order_id": str})
    sample = read_raw(DATA_DIR / "sample_submission.csv")
    assert list(sub.columns) == ["order_id", "score"]
    assert len(sub) == 2096 and sub.order_id.is_unique
    assert sub.order_id.tolist() == sample.order_id.tolist()
    assert sub.score.notna().all() and sub.score.between(0, 1).all()


@pytest.mark.skipif(not PRED.exists(), reason="predictions not present")
def test_predictions_match_recorded_sha256():
    """The file must be byte-for-byte the one checked in evidence/predictions_check.md (catches e.g. an Excel re-save)."""
    import re
    from kestrel.config import ROOT
    from kestrel.predict import sha256
    check = (ROOT / "evidence" / "predictions_check.md").read_text(encoding="utf-8")
    recorded = re.search(r"SHA-256 of `outputs/predictions.csv`: `([0-9a-f]{64})`", check).group(1)
    assert sha256(PRED) == recorded, "outputs/predictions.csv changed since `python -m kestrel.predict` - regenerate it"
