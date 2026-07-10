"""
_canonical_symbol matches config.AGENT["universe"] — see ai_agent.py:1624.
The model routinely echoes crypto symbols without the separator
("BTCUSD" instead of "BTC/USD"); before this normalization existed, every
one of those was rejected in _enforce_caps as "symbol not in approved
universe" (90 rejected Eris decisions in three days per the docstring).
"""
import config
import ai_agent


def test_exact_match_passes_through(monkeypatch):
    monkeypatch.setitem(config.AGENT, "universe", ["AAPL", "BTC/USD"])
    assert ai_agent._canonical_symbol("AAPL") == "AAPL"


def test_lowercase_and_whitespace_normalized(monkeypatch):
    monkeypatch.setitem(config.AGENT, "universe", ["AAPL"])
    assert ai_agent._canonical_symbol(" aapl ") == "AAPL"


def test_crypto_symbol_without_slash_maps_to_universe_form(monkeypatch):
    monkeypatch.setitem(config.AGENT, "universe", ["BTC/USD", "AAPL"])
    assert ai_agent._canonical_symbol("BTCUSD") == "BTC/USD"


def test_crypto_symbol_with_hyphen_maps_to_universe_form(monkeypatch):
    monkeypatch.setitem(config.AGENT, "universe", ["BONK/USD"])
    assert ai_agent._canonical_symbol("BONK-USD") == "BONK/USD"


def test_symbol_not_in_universe_returned_unchanged(monkeypatch):
    monkeypatch.setitem(config.AGENT, "universe", ["AAPL"])
    assert ai_agent._canonical_symbol("TSLA") == "TSLA"


def test_no_false_positive_across_unrelated_symbols(monkeypatch):
    # "ETHUSD" stripped shouldn't accidentally match "ETH/USDT" or similar.
    monkeypatch.setitem(config.AGENT, "universe", ["ETH/USDT"])
    assert ai_agent._canonical_symbol("ETHUSD") == "ETHUSD"
