import random

from trader import monkey


def test_monkey_is_reproducible_and_valid():
    positions = {"AAPL": {"qty": 10, "market_value": 1000}, "TSLA": {"qty": -5, "market_value": -900}}
    a = monkey.throw_darts(positions, random.Random(42))
    b = monkey.throw_darts(positions, random.Random(42))
    assert a == b
    for d in a:
        assert d["action"] in {"buy", "sell", "short", "cover"}
        if d["symbol"] == "AAPL":
            assert d["action"] == "sell"
        if d["symbol"] == "TSLA":
            assert d["action"] == "cover"
        if d["action"] in {"buy", "short"}:
            assert 3 <= d["size_pct"] <= 10 and d["symbol"] not in positions


def test_monkey_respects_target_positions():
    full = {f"S{i}": {"qty": 1, "market_value": 100} for i in range(monkey.TARGET_POSITIONS + 2)}
    for seed in range(50):
        entries = [d for d in monkey.throw_darts(full, random.Random(seed)) if d["action"] in {"buy", "short"}]
        exits = [d for d in monkey.throw_darts(full, random.Random(seed)) if d["action"] in {"sell", "cover"}]
        assert len(full) - len(exits) + len(entries) <= max(len(full), monkey.TARGET_POSITIONS)
