"""
_confidence_calibration breaks out win rate/expectancy by the confidence
stated at exit — added because the 2026-07-09 profitability review found
"high" confidence trades underperforming "medium" ones. See ai_agent.py.
"""
import ai_agent


def _trade(pnl, confidence):
    return {"realized_pnl_pct": pnl, "confidence_at_exit": confidence}


def test_groups_by_confidence_level():
    trades = [
        _trade(2.0, "high"),
        _trade(-1.0, "high"),
        _trade(3.0, "medium"),
        _trade(1.0, "medium"),
    ]
    result = ai_agent._confidence_calibration(trades)
    assert result["high"]["trades"] == 2
    assert result["high"]["win_rate_pct"] == 50.0
    assert result["medium"]["trades"] == 2
    assert result["medium"]["win_rate_pct"] == 100.0


def test_missing_confidence_grouped_as_unstated():
    trades = [_trade(1.0, None)]
    result = ai_agent._confidence_calibration(trades)
    assert result["unstated"]["trades"] == 1


def test_expectancy_computed_per_level():
    trades = [_trade(4.0, "high"), _trade(-2.0, "high")]
    result = ai_agent._confidence_calibration(trades)
    assert result["high"]["expectancy_pct_per_trade"] == 1.0
