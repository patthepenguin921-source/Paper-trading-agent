"""Runs brief.build and execute.run_cycle against a fake Alpaca client."""
import json

from trader import brief, execute, store

BARS = [{"t": f"2026-01-{(i % 28) + 1:02d}T05:00:00Z", "o": 100, "h": 101 + i * 0.1, "l": 99,
         "c": 100 + i * 0.1, "v": 1_000_000} for i in range(300)]


class FakeAlpaca:
    orders: list = []

    def __init__(self, agent_id):
        self.agent_id = agent_id

    def clock(self): return {"is_open": True, "next_open": "x", "next_close": "y"}
    def account(self): return {"equity": "100000", "cash": "90000", "last_equity": "99000",
                               "long_market_value": "10000", "short_market_value": "0"}
    def positions(self): return [{"symbol": "AAPL", "qty": "100", "market_value": "10000",
                                  "unrealized_plpc": "-0.2", "avg_entry_price": "125", "current_price": "100"}]
    def cancel_all_orders(self): pass
    def asset(self, s): return {"tradable": True, "shortable": True, "easy_to_borrow": True, "class": "us_equity"}
    def snapshots(self, syms): return {s: {"latestTrade": {"p": 100.0}, "prevDailyBar": {"c": 99.0}} for s in syms}
    def daily_bars(self, syms, days=400): return {s: BARS for s in syms}
    def movers(self, top=15): return {"gainers": [{"symbol": "ZZZ"}], "losers": []}
    def most_actives(self, top=20): return [{"symbol": "SPY"}]
    def fills(self, days=30): return [{"transaction_time": "2026-11-05T15:00:00Z", "side": "buy", "qty": "100", "symbol": "AAPL", "price": "125"}]
    def portfolio_history(self, period="3M"): return {"equity": [100000, 99000, 100000]}
    def news(self, symbols=None, limit=50): return [{"created_at": "2026-11-06T12:00:00Z", "symbols": ["AAPL"], "headline": "h", "source": "s"}]

    def market_order(self, symbol, qty, side, client_order_id=None):
        FakeAlpaca.orders.append(("open", symbol, qty, side)); return {"id": "o1", "qty": str(qty)}

    def close_position(self, symbol, fraction=1.0):
        FakeAlpaca.orders.append(("close", symbol, fraction)); return {"id": "o2"}


def test_brief_and_execute(tmp_path, monkeypatch):
    monkeypatch.setattr(brief, "Alpaca", FakeAlpaca)
    monkeypatch.setattr(execute, "Alpaca", FakeAlpaca)
    logged = []
    monkeypatch.setattr(store, "insert", lambda table, rows: logged.append((table, rows)) or [{"id": 7}])

    assert brief.build("analyst", str(tmp_path), allow_closed=False)
    md = (tmp_path / "brief.md").read_text()
    assert "## Open positions" in md and "AAPL" in md and (tmp_path / "history" / "AAPL.csv").exists()
    json.loads((tmp_path / "brief.json").read_text())

    FakeAlpaca.orders = []
    out = execute.run_cycle("analyst", [
        {"symbol": "AAPL", "action": "buy", "size_pct": 5},   # overridden by stop-loss (-20%)
        {"symbol": "MSFT", "action": "buy", "size_pct": 5, "confidence": 0.8},
        {"symbol": "TSLA", "action": "short", "size_pct": 3},
    ])
    assert ("close", "AAPL", 1.0) in FakeAlpaca.orders
    assert ("open", "MSFT", 50, "buy") in FakeAlpaca.orders
    assert ("open", "TSLA", 30, "sell") in FakeAlpaca.orders
    assert [t for t, _ in logged] == ["pt_runs", "pt_decisions"]
    assert all(r["status"] == "submitted" for r in out["results"])
