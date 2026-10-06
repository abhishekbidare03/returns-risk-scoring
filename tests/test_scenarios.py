"""Every case on the black-box scenario sheet (tests/scenarios.py) must pass."""
import pytest

from .scenarios import CASES, call


@pytest.mark.parametrize("cid, desc, expect, body, check", CASES, ids=[c[0] for c in CASES])
def test_scenario(cid, desc, expect, body, check):
    status, d = call(body)
    assert check(status, d), f"{cid}: expected {expect}; got {status} {d}"
