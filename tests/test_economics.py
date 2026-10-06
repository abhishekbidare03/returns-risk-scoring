"""Rupee economics: formulas, break-evens and the 'calls beat holds' result (policy.md §6-7)."""
import json

import numpy as np
import pytest

from kestrel.config import MODELS_DIR
from kestrel.economics import Costs, call_break_even, capacity_table, expected_values, realised_value, recommended_share


def test_break_evens_match_policy():
    assert call_break_even() == pytest.approx(45 / (0.35 * 1150))            # 11.2%
    assert call_break_even(costs=Costs(return_cost=600)) == pytest.approx(45 / (0.35 * 600))   # 21.4%
    true = call_break_even(4000, Costs(count_margin_in_call=True))
    assert true < call_break_even()                                           # conservative figure is an upper bound


def test_expected_values_formula():
    ev = expected_values([0.2], [4000], Costs())
    assert ev["ship"][0] == 0
    assert ev["call"][0] == pytest.approx(0.35 * 0.2 * 1150 - 45)
    assert ev["hold"][0] == pytest.approx(0.12 * 0.2 * 1150 - 0.12 * 0.8 * 0.25 * 4000)


@pytest.mark.parametrize("p", [0.06, 0.112, 0.2, 0.4, 0.8])
@pytest.mark.parametrize("value", [880, 2300, 4400, 20000])
def test_calls_beat_holds_wherever_calling_pays_true_accounting(p, value):
    # Counting the margin a prevented return keeps, call > hold wherever a call pays, at margins >= 15%.
    # (At 10% margin, 2 of 10,504 training orders - the cheapest room heaters - have a window up to 12.0% risk
    #  where a hold edges a call; it lies below the 13.7% operating cutoff. See key_findings.md Phase 5.)
    for margin in (0.15, 0.25, 0.35):
        ev = expected_values([p], [value], Costs(margin_rate=margin, count_margin_in_call=True))
        if ev["call"][0] > 0:
            assert ev["call"][0] > ev["hold"][0]


@pytest.mark.parametrize("p", [0.137, 0.2, 0.4, 0.8])
@pytest.mark.parametrize("value", [880, 2300, 4400, 20000])
def test_calls_beat_holds_at_operating_cutoff_conservative(p, value):
    # Conservative accounting has a documented sliver just above 11.2% for the cheapest orders at 10% margin
    # (Phase 2 §10e: 99.8%); at the default operating cutoff (13.7%) calls win for every order and margin >= 10%.
    for margin in (0.10, 0.15, 0.25):
        ev = expected_values([p], [value], Costs(margin_rate=margin))
        assert ev["call"][0] > ev["hold"][0]


def test_realised_value_counts():
    y = np.array([1, 0, 0, 1]); v = np.array([1000, 1000, 1000, 1000]); s = np.array([True, True, False, False])
    call = realised_value(y, v, s, "call")
    assert call["orders_actioned"] == 2 and call["returns_among_them"] == 1
    assert call["net"] == pytest.approx(0.35 * 1150 - 2 * 45)
    hold = realised_value(y, v, s, "hold")
    assert hold["net"] == pytest.approx(0.12 * 1150 - 0.12 * 0.25 * 1000)


def test_capacity_rule_picks_last_positive_band():
    rng = np.random.default_rng(0)
    p = rng.uniform(0, 1, 5000); y = (rng.uniform(0, 1, 5000) < p * 0.4).astype(int); v = np.full(5000, 4000.0)
    t = capacity_table(p, y, v)
    x = recommended_share(t)
    assert t.loc[x, "band_net"] > 0
    later = t.index[t.index > x]
    assert len(later) == 0 or t.loc[later[0], "band_net"] <= 0


def test_saved_decision_is_consistent():
    path = MODELS_DIR / "model_meta.json"
    if not path.exists():
        pytest.skip("no saved model")
    d = json.loads(path.read_text(encoding="utf-8")).get("decision")
    if d is None:
        pytest.skip("decision not saved yet")
    assert d["score_cutoff_for_call"] >= call_break_even() - 1e-9            # never calls below break-even
    assert d["capacity_options"][f"{d['recommended_top_share']:.0%}"] == d["score_cutoff_for_call"]
    assert "never hold" in d["rule"]
