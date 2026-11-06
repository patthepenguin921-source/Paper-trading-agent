from datetime import datetime, timezone

from trader import indicators, prompt


def test_indicators_basic():
    closes = [float(i) for i in range(1, 301)]
    bars = [{"c": c, "h": c + 1, "l": c - 1, "v": 1000} for c in closes]
    s = indicators.summarize(bars)
    assert s["close"] == 300 and s["rsi14"] == 100.0 and s["chg_1d"] == round((300 / 299 - 1) * 100, 2)
    assert indicators.rsi([1.0, 2.0]) is None


def test_prompt_renders_all_placeholders():
    for mode in ("trade", "review"):
        text = prompt.render(mode, datetime(2026, 11, 9, 15, 0, tzinfo=timezone.utc))
        assert "{{" not in text and "2026-11-09" in text
