from trader import risk

RISK = dict(risk.RISK)
OK = {"tradable": True, "shortable": True, "easy_to_borrow": True, "class": "us_equity"}


def pos(qty, mv, pl=0.0):
    return {"qty": qty, "market_value": mv, "unrealized_plpc": pl, "avg_entry_price": 0, "current_price": 0}


def plan(decisions, positions=None, prices=None, assets=None, equity=100_000):
    syms = {d["symbol"].upper() for d in decisions}
    prices = prices or {s: 100.0 for s in syms}
    assets = assets or {s: OK for s in syms}
    return {r["symbol"]: r for r in risk.plan_orders(decisions, equity, positions or {}, prices, assets, RISK)}


def test_buy_sized_to_whole_shares():
    r = plan([{"symbol": "aapl", "action": "buy", "size_pct": 5}])["AAPL"]
    assert r["status"] == "planned" and r["qty"] == 50 and r["side"] == "buy"


def test_size_clamped_to_max_position():
    r = plan([{"symbol": "AAPL", "action": "buy", "size_pct": 50}])["AAPL"]
    assert r["qty"] == 100  # 10% of 100k at $100


def test_add_respects_existing_position():
    r = plan([{"symbol": "AAPL", "action": "buy", "size_pct": 10}], {"AAPL": pos(80, 8000)})["AAPL"]
    assert r["qty"] == 20


def test_short_requires_borrow():
    a = {"AAPL": {**OK, "easy_to_borrow": False}}
    assert plan([{"symbol": "AAPL", "action": "short", "size_pct": 5}], assets=a)["AAPL"]["status"] == "rejected"


def test_short_planned_as_sell_side():
    r = plan([{"symbol": "AAPL", "action": "short", "size_pct": 5}])["AAPL"]
    assert r["status"] == "planned" and r["side"] == "sell" and r["qty"] == 50


def test_cannot_short_while_long():
    assert plan([{"symbol": "AAPL", "action": "short"}], {"AAPL": pos(10, 1000)})["AAPL"]["status"] == "rejected"


def test_sell_requires_long_and_cover_requires_short():
    p = {"AAPL": pos(10, 1000), "TSLA": pos(-10, -1000)}
    out = plan([{"symbol": "AAPL", "action": "cover"}, {"symbol": "TSLA", "action": "sell"}], p)
    assert out["AAPL"]["status"] == "rejected" and out["TSLA"]["status"] == "rejected"
    out = plan([{"symbol": "AAPL", "action": "sell", "fraction": 0.5}, {"symbol": "TSLA", "action": "cover"}], p)
    assert out["AAPL"]["fraction"] == 0.5 and out["TSLA"]["side"] == "buy"


def test_gross_exposure_cap_and_exit_frees_room():
    p = {f"S{i}": pos(95, 9500) for i in range(10)}  # 95% gross
    assert plan([{"symbol": "NEW", "action": "buy", "size_pct": 10}], p)["NEW"]["qty"] == 50
    out = plan([{"symbol": "S0", "action": "sell"}, {"symbol": "NEW", "action": "buy", "size_pct": 10}], p)
    assert out["NEW"]["qty"] == 100


def test_short_exposure_cap():
    p = {f"S{i}": pos(-95, -9500) for i in range(4)}  # 38% short
    assert plan([{"symbol": "NEW", "action": "short", "size_pct": 10}], p)["NEW"]["qty"] == 20


def test_max_positions():
    p = {f"S{i}": pos(10, 1000) for i in range(RISK["max_positions"])}
    assert plan([{"symbol": "NEW", "action": "buy"}], p)["NEW"]["status"] == "rejected"


def test_penny_stock_and_untradable_rejected():
    assert plan([{"symbol": "X", "action": "buy"}], prices={"X": 2.0})["X"]["status"] == "rejected"
    assert plan([{"symbol": "X", "action": "buy"}], assets={"X": {"tradable": False}})["X"]["status"] == "rejected"


def test_bad_action_and_duplicates():
    out = risk.plan_orders([{"symbol": "A", "action": "yolo"}, {"symbol": "B", "action": "buy"},
                            {"symbol": "B", "action": "buy"}], 1e5, {}, {"B": 100}, {"B": OK}, RISK)
    assert [r["status"] for r in out] == ["rejected", "rejected", "planned"]


def test_higher_confidence_entries_get_room_first():
    p = {f"S{i}": pos(92, 9200) for i in range(10)}  # 92% gross, room for 8%
    out = plan([{"symbol": "LOW", "action": "buy", "size_pct": 8, "confidence": 0.3},
                {"symbol": "HIGH", "action": "buy", "size_pct": 8, "confidence": 0.9}], p)
    assert out["HIGH"]["status"] == "planned" and out["LOW"]["status"] == "rejected"


def test_stop_loss_exits():
    exits = risk.stop_loss_exits({"A": pos(10, 800, -20), "B": pos(-10, -1200, -16), "C": pos(10, 950, -5)}, 15)
    assert {(e["symbol"], e["action"]) for e in exits} == {("A", "sell"), ("B", "cover")}


def test_normalize_positions():
    p = risk.normalize_positions([{"symbol": "A", "qty": "-5", "market_value": "-500",
                                   "unrealized_plpc": "-0.031", "avg_entry_price": "97", "current_price": "100"}])
    assert p["A"]["qty"] == -5 and round(p["A"]["unrealized_plpc"], 2) == -3.1


def test_fractional_longs_for_small_accounts():
    frac = {**OK, "fractionable": True}
    # $10k account, 3% = $300, stock at $737: whole shares would be 0
    r = plan([{"symbol": "SPY", "action": "buy", "size_pct": 3}], prices={"SPY": 737.0},
             assets={"SPY": frac}, equity=10_000)["SPY"]
    assert r["status"] == "planned" and 0.40 < r["qty"] < 0.41
    # shorts stay whole shares, so the same trade is rejected
    r = plan([{"symbol": "SPY", "action": "short", "size_pct": 3}], prices={"SPY": 737.0},
             assets={"SPY": frac}, equity=10_000)["SPY"]
    assert r["status"] == "rejected"
