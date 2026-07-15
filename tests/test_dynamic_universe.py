"""
_effective_universe (ai_agent.py) and get_market_screen (alpaca_client.py):
each agent's watchlist should cover its hand-picked core list *plus* a
market-wide most-active/mover sample, not just the ~20-70 hardcoded symbols
in config.py's *_UNIVERSE lists — see config.py's dynamic_universe_top_n.
"""
from types import SimpleNamespace

import ai_agent
import alpaca_client as ac
import config


def test_effective_universe_merges_core_dynamic_and_held(monkeypatch):
    monkeypatch.setitem(config.AGENT, "universe", ["AAPL", "MSFT"])
    monkeypatch.setitem(config.AGENT, "dynamic_universe_top_n", 40)
    monkeypatch.setattr(ac, "get_market_screen", lambda top_n: ["GME", "MSFT"])  # MSFT overlaps on purpose

    result = ai_agent._effective_universe(held_symbols={"TSLA"})

    assert result == ["AAPL", "GME", "MSFT", "TSLA"]


def test_effective_universe_skips_screener_call_when_top_n_is_zero(monkeypatch):
    monkeypatch.setitem(config.AGENT, "universe", ["AAPL"])
    monkeypatch.setitem(config.AGENT, "dynamic_universe_top_n", 0)
    monkeypatch.setattr(ac, "get_market_screen", lambda top_n: (_ for _ in ()).throw(
        AssertionError("should not be called when dynamic_universe_top_n is 0")
    ))

    assert ai_agent._effective_universe(held_symbols=set()) == ["AAPL"]


def test_effective_universe_falls_back_to_core_and_held_if_screener_fails(monkeypatch):
    monkeypatch.setitem(config.AGENT, "universe", ["AAPL"])
    monkeypatch.setitem(config.AGENT, "dynamic_universe_top_n", 40)
    monkeypatch.setattr(ac, "get_market_screen", lambda top_n: [])  # get_market_screen's own best-effort fallback

    assert ai_agent._effective_universe(held_symbols={"TSLA"}) == ["AAPL", "TSLA"]


def _active(symbol):
    return SimpleNamespace(symbol=symbol, volume=1.0, trade_count=1.0)


def _mover(symbol):
    return SimpleNamespace(symbol=symbol, percent_change=5.0, change=1.0, price=100.0)


def test_get_market_screen_merges_actives_and_movers(monkeypatch):
    monkeypatch.setattr(
        ac.screener_client, "get_most_actives",
        lambda req: SimpleNamespace(most_actives=[_active("AAPL"), _active("MSFT")]),
    )
    monkeypatch.setattr(
        ac.screener_client, "get_market_movers",
        lambda req: SimpleNamespace(gainers=[_mover("GME")], losers=[_mover("MSFT")]),  # MSFT overlaps on purpose
    )

    assert ac.get_market_screen(top_n=40) == ["AAPL", "GME", "MSFT"]


def test_get_market_screen_best_effort_returns_empty_on_failure(monkeypatch):
    def _raise(req):
        raise RuntimeError("rate limited")

    monkeypatch.setattr(ac.screener_client, "get_most_actives", _raise)

    assert ac.get_market_screen(top_n=40) == []
