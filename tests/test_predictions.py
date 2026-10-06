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
