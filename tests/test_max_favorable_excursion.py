"""
_max_favorable_excursion_pct: best price seen since entry, as a % move in
the position's favorable direction. See ai_agent.py — surfaced because the
2026-07-09 review found winners cut early while the model's exit judgment,
not entry judgment, was the leak.
"""
from datetime import datetime, timezone
from types import SimpleNamespace

import ai_agent


def _bar(day, high, low):
    return SimpleNamespace(timestamp=datetime(2026, 7, day, tzinfo=timezone.utc), high=high, low=low)


def test_long_position_mfe_uses_highest_high_since_entry():
    bars = [_bar(1, 100, 95), _bar(2, 110, 100), _bar(3, 105, 98)]
    result = ai_agent._max_favorable_excursion_pct(
        "AAPL", "long", avg_entry_price=100.0, entry_at="2026-07-01T00:00:00Z", bars=bars
    )
    assert result == 10.0  # best high 110 vs entry 100


def test_short_position_mfe_uses_lowest_low_since_entry():
    bars = [_bar(1, 100, 95), _bar(2, 105, 90), _bar(3, 102, 98)]
    result = ai_agent._max_favorable_excursion_pct(
        "AAPL", "short", avg_entry_price=100.0, entry_at="2026-07-01T00:00:00Z", bars=bars
    )
    assert result == 10.0  # best low 90 vs entry 100


def test_bars_before_entry_excluded():
    bars = [_bar(1, 200, 195), _bar(2, 105, 100)]  # day-1 spike happened before entry
    result = ai_agent._max_favorable_excursion_pct(
        "AAPL", "long", avg_entry_price=100.0, entry_at="2026-07-02T00:00:00Z", bars=bars
    )
    assert result == 5.0  # day-1's 200 high is excluded


def test_returns_none_without_entry_date():
    bars = [_bar(1, 110, 95)]
    assert ai_agent._max_favorable_excursion_pct("AAPL", "long", 100.0, None, bars) is None


def test_returns_none_without_bars():
    assert ai_agent._max_favorable_excursion_pct("AAPL", "long", 100.0, "2026-07-01T00:00:00Z", None) is None
