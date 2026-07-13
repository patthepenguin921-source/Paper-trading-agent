"""
_enforce_caps validates/clips every AI-returned decision against the hard
risk caps in config.py — the AI's judgment never overrides these, they're
enforced here in code (see ai_agent.py:1651). This is the single most
load-bearing function in the risk pipeline, so it gets the deepest coverage.
"""
import config
import ai_agent


def _base_agent(**overrides):
    agent = {
        "universe": ["AAPL", "TSLA", "BTC/USD"],
        "allow_short": False,
        "max_new_buys_per_run": None,
        "max_open_positions": None,
        "position_size_pct_min": 0.05,
        "position_size_pct_max": 0.20,
        "use_notional": False,
    }
    agent.update(overrides)
    return agent


def _context(equity=100_000.0, cash=100_000.0, held=None, watchlist=None, open_orders=None):
    return {
        "account": {"equity": equity, "cash": cash},
        "held_positions": held or {},
        "watchlist": watchlist or {},
        "open_orders": open_orders or [],
    }


def _apply_agent(monkeypatch, **overrides):
    monkeypatch.setattr(config, "AGENT", _base_agent(**overrides))


def test_symbol_outside_universe_rejected(monkeypatch):
    _apply_agent(monkeypatch)
    decisions = [{"symbol": "MSFT", "action": "buy"}]
    out = ai_agent._enforce_caps(decisions, _context(), {})
    assert out[0]["allowed"] is False
    assert out[0]["cap_note"] == "symbol not in approved universe"


def test_buy_sized_within_range_and_qty_computed(monkeypatch):
    _apply_agent(monkeypatch)
    context = _context(watchlist={"AAPL": {"last_price": 100.0}})
    decisions = [{"symbol": "AAPL", "action": "buy", "size_pct": 0.10}]
    out = ai_agent._enforce_caps(decisions, context, {})
    d = out[0]
    assert d["allowed"] is True
    assert d["size_pct_used"] == 0.10
    # target notional = 100_000 * 0.10 = 10_000, fill buffer 1.02, price 100
    # raw_qty = 10_000 / 102 = 98.03 -> int() = 98
    assert d["qty"] == 98


def test_requested_size_pct_clipped_to_agent_range(monkeypatch):
    _apply_agent(monkeypatch)
    context = _context(watchlist={"AAPL": {"last_price": 100.0}})
    decisions = [{"symbol": "AAPL", "action": "buy", "size_pct": 0.99}]
    out = ai_agent._enforce_caps(decisions, context, {})
    assert out[0]["size_pct_used"] == 0.20  # clipped to max


def test_missing_size_pct_defaults_to_midpoint(monkeypatch):
    _apply_agent(monkeypatch)
    context = _context(watchlist={"AAPL": {"last_price": 100.0}})
    decisions = [{"symbol": "AAPL", "action": "buy"}]
    out = ai_agent._enforce_caps(decisions, context, {})
    assert out[0]["size_pct_used"] == 0.125  # (0.05 + 0.20) / 2


def test_buy_rejected_with_no_price_data(monkeypatch):
    _apply_agent(monkeypatch)
    context = _context(watchlist={})
    decisions = [{"symbol": "AAPL", "action": "buy"}]
    out = ai_agent._enforce_caps(decisions, context, {})
    assert out[0]["allowed"] is False
    assert out[0]["cap_note"] == "no price data available for this symbol this run"


def test_buy_rejected_when_no_cash_available(monkeypatch):
    _apply_agent(monkeypatch)
    context = _context(cash=0.0, watchlist={"AAPL": {"last_price": 100.0}})
    decisions = [{"symbol": "AAPL", "action": "buy"}]
    out = ai_agent._enforce_caps(decisions, context, {})
    assert out[0]["allowed"] is False
    assert out[0]["cap_note"] == "no available cash/buying power remaining after pending orders"


def test_pending_buys_reduce_available_cash(monkeypatch):
    _apply_agent(monkeypatch)
    # $100k cash, but $95k already committed to a pending TSLA buy at $500/share x 190.
    context = _context(cash=100_000.0, watchlist={"AAPL": {"last_price": 100.0}, "TSLA": {"last_price": 500.0}})
    decisions = [{"symbol": "AAPL", "action": "buy", "size_pct": 0.20}]
    out = ai_agent._enforce_caps(decisions, context, {"TSLA": 190})
    # available_cash = 100_000 - 190*500 = 5_000; target_notional = 20_000 but capped by cash
    assert out[0]["allowed"] is True
    assert out[0]["qty"] * 100.0 * ai_agent._FILL_PRICE_BUFFER <= 5_000 + 1e-6


def test_duplicate_buy_for_already_held_symbol_rejected(monkeypatch):
    _apply_agent(monkeypatch)
    context = _context(
        held={"AAPL": {"side": "long", "qty": 10, "current_price": 100.0, "unrealized_pl_pct": 5.0}},
        watchlist={"AAPL": {"last_price": 100.0}},
    )
    decisions = [{"symbol": "AAPL", "action": "buy"}]
    out = ai_agent._enforce_caps(decisions, context, {})
    assert out[0]["allowed"] is False
    assert "already holding" in out[0]["cap_note"]


def test_max_open_positions_enforced(monkeypatch):
    _apply_agent(monkeypatch, max_open_positions=1)
    context = _context(
        held={"TSLA": {"side": "long", "qty": 5, "current_price": 200.0, "unrealized_pl_pct": 1.0}},
        watchlist={"AAPL": {"last_price": 100.0}},
    )
    decisions = [{"symbol": "AAPL", "action": "buy"}]
    out = ai_agent._enforce_caps(decisions, context, {})
    assert out[0]["allowed"] is False
    assert out[0]["cap_note"] == "max open positions reached"


def test_max_new_buys_per_run_enforced(monkeypatch):
    _apply_agent(monkeypatch, max_new_buys_per_run=1)
    context = _context(watchlist={"AAPL": {"last_price": 100.0}, "TSLA": {"last_price": 200.0}})
    decisions = [
        {"symbol": "AAPL", "action": "buy"},
        {"symbol": "TSLA", "action": "buy"},
    ]
    out = ai_agent._enforce_caps(decisions, context, {})
    assert out[0]["allowed"] is True
    assert out[1]["allowed"] is False
    assert out[1]["cap_note"] == "max new positions per run reached"


def test_duplicate_symbol_within_same_run_rejected(monkeypatch):
    _apply_agent(monkeypatch)
    context = _context(watchlist={"AAPL": {"last_price": 100.0}})
    decisions = [
        {"symbol": "AAPL", "action": "buy"},
        {"symbol": "AAPL", "action": "buy"},
    ]
    out = ai_agent._enforce_caps(decisions, context, {})
    assert out[0]["allowed"] is True
    assert out[1]["allowed"] is False
    assert out[1]["cap_note"] == "duplicate order for this symbol already approved this run, ignoring"


def test_sell_without_held_position_rejected(monkeypatch):
    _apply_agent(monkeypatch)
    decisions = [{"symbol": "AAPL", "action": "sell"}]
    out = ai_agent._enforce_caps(decisions, _context(), {})
    assert out[0]["allowed"] is False
    assert out[0]["cap_note"] == "no long position held to sell"


def test_sell_of_held_long_position_allowed(monkeypatch):
    _apply_agent(monkeypatch)
    context = _context(
        held={"AAPL": {"side": "long", "qty": 10, "current_price": 105.0, "unrealized_pl_pct": 5.0}},
    )
    decisions = [{"symbol": "AAPL", "action": "sell"}]
    out = ai_agent._enforce_caps(decisions, context, {})
    assert out[0]["allowed"] is True
    assert out[0]["qty"] == 10
    assert out[0]["exit_price"] == 105.0


def test_cover_rejected_when_shorting_disabled(monkeypatch):
    _apply_agent(monkeypatch, allow_short=False)
    context = _context(
        held={"AAPL": {"side": "short", "qty": -10, "current_price": 95.0, "unrealized_pl_pct": 5.0}},
    )
    decisions = [{"symbol": "AAPL", "action": "cover"}]
    out = ai_agent._enforce_caps(decisions, context, {})
    assert out[0]["allowed"] is False
    assert out[0]["cap_note"] == "short selling not enabled for this agent"


def test_short_on_crypto_rejected_spot_only(monkeypatch):
    _apply_agent(monkeypatch, allow_short=True)
    context = _context(watchlist={"BTC/USD": {"last_price": 50_000.0}})
    decisions = [{"symbol": "BTC/USD", "action": "short"}]
    out = ai_agent._enforce_caps(decisions, context, {})
    assert out[0]["allowed"] is False
    assert "spot-only" in out[0]["cap_note"]


def test_block_new_reason_blocks_buys_but_not_sells(monkeypatch):
    _apply_agent(monkeypatch)
    context = _context(
        held={"AAPL": {"side": "long", "qty": 10, "current_price": 100.0, "unrealized_pl_pct": -2.0}},
        watchlist={"TSLA": {"last_price": 200.0}},
    )
    decisions = [
        {"symbol": "TSLA", "action": "buy"},
        {"symbol": "AAPL", "action": "sell"},
    ]
    out = ai_agent._enforce_caps(decisions, context, {}, block_new_reason="daily loss breaker tripped")
    assert out[0]["allowed"] is False
    assert out[0]["cap_note"] == "daily loss breaker tripped"
    assert out[1]["allowed"] is True


def test_hold_action_never_allowed(monkeypatch):
    _apply_agent(monkeypatch)
    decisions = [{"symbol": "AAPL", "action": "hold"}]
    out = ai_agent._enforce_caps(decisions, _context(), {})
    assert out[0]["allowed"] is False
    assert out[0]["cap_note"] == "hold (no action taken)"


def test_unrecognized_action_rejected(monkeypatch):
    _apply_agent(monkeypatch)
    decisions = [{"symbol": "AAPL", "action": "yolo"}]
    out = ai_agent._enforce_caps(decisions, _context(), {})
    assert out[0]["allowed"] is False
    assert out[0]["cap_note"] == "unrecognized action 'yolo'"


def test_notional_buy_uses_dollar_amount_not_qty(monkeypatch):
    _apply_agent(monkeypatch, use_notional=True)
    context = _context(watchlist={"BTC/USD": {"last_price": 50_000.0}})
    decisions = [{"symbol": "BTC/USD", "action": "buy", "size_pct": 0.10}]
    out = ai_agent._enforce_caps(decisions, context, {})
    d = out[0]
    assert d["allowed"] is True
    assert d["notional_order"] == 10_000.0
    assert "qty" not in d  # notional path doesn't set qty


def test_symbol_gets_canonicalized_before_universe_check(monkeypatch):
    _apply_agent(monkeypatch)
    context = _context(watchlist={"BTC/USD": {"last_price": 50_000.0}})
    decisions = [{"symbol": "BTCUSD", "action": "buy", "size_pct": 0.05}]
    out = ai_agent._enforce_caps(decisions, context, {})
    assert out[0]["symbol"] == "BTC/USD"
    assert out[0]["allowed"] is True


def test_restrict_to_crypto_rejects_equity_buy(monkeypatch):
    _apply_agent(monkeypatch)
    context = _context(watchlist={"AAPL": {"last_price": 100.0}})
    decisions = [{"symbol": "AAPL", "action": "buy"}]
    out = ai_agent._enforce_caps(decisions, context, {}, restrict_to_crypto=True)
    assert out[0]["allowed"] is False
    assert out[0]["cap_note"] == "off-hours run — only crypto symbols execute here (equity markets are closed)"


def test_restrict_to_crypto_rejects_equity_sell_of_held_position(monkeypatch):
    _apply_agent(monkeypatch)
    context = _context(
        held={"AAPL": {"side": "long", "qty": 10, "current_price": 100.0, "unrealized_pl_pct": 5.0}},
    )
    decisions = [{"symbol": "AAPL", "action": "sell"}]
    out = ai_agent._enforce_caps(decisions, context, {}, restrict_to_crypto=True)
    assert out[0]["allowed"] is False
    assert out[0]["cap_note"] == "off-hours run — only crypto symbols execute here (equity markets are closed)"


def test_restrict_to_crypto_allows_crypto_buy(monkeypatch):
    _apply_agent(monkeypatch)
    context = _context(watchlist={"BTC/USD": {"last_price": 50_000.0}})
    decisions = [{"symbol": "BTC/USD", "action": "buy", "size_pct": 0.05}]
    out = ai_agent._enforce_caps(decisions, context, {}, restrict_to_crypto=True)
    assert out[0]["allowed"] is True


def test_restrict_to_crypto_does_not_override_hold(monkeypatch):
    _apply_agent(monkeypatch)
    decisions = [{"symbol": "AAPL", "action": "hold"}]
    out = ai_agent._enforce_caps(decisions, _context(), {}, restrict_to_crypto=True)
    assert out[0]["allowed"] is False
    assert out[0]["cap_note"] == "hold (no action taken)"


def test_restrict_to_crypto_false_by_default_allows_equities(monkeypatch):
    _apply_agent(monkeypatch)
    context = _context(watchlist={"AAPL": {"last_price": 100.0}})
    decisions = [{"symbol": "AAPL", "action": "buy"}]
    out = ai_agent._enforce_caps(decisions, context, {})
    assert out[0]["allowed"] is True
