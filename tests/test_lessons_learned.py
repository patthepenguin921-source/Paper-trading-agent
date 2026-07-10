import os
import sys

os.environ.setdefault("AGENT_ID", "plutus")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import lessons_learned  # noqa: E402


def test_max_drawdown_flat_equity_is_zero():
    assert lessons_learned._max_drawdown_pct([100_000, 100_000, 100_000]) == 0.0


def test_max_drawdown_single_dip():
    # peak 100k, trough 90k -> 10% drawdown, then partial recovery to 95k
    # (recovery doesn't reduce the recorded max drawdown).
    assert lessons_learned._max_drawdown_pct([100_000, 90_000, 95_000]) == 10.0


def test_max_drawdown_uses_running_peak_not_first_value():
    # equity climbs to 110k first, THEN drops to 88k -> 20% off the 110k peak,
    # not 12% off the 100k starting value.
    result = lessons_learned._max_drawdown_pct([100_000, 110_000, 88_000])
    assert result == 20.0


def test_max_drawdown_none_with_fewer_than_two_points():
    assert lessons_learned._max_drawdown_pct([100_000]) is None
    assert lessons_learned._max_drawdown_pct([]) is None
