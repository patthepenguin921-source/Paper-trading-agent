"""
Sector concentration cap (max_sector_concentration_pct, see sectors.py and
_enforce_caps): without this, min_cash_buffer_pct=0 and
max_open_positions=None everywhere meant nothing stopped an agent from
legally ending up fully concentrated in one correlated cluster.
"""
import config
import ai_agent
import sectors


def _base_agent(**overrides):
    agent = {
        "universe": ["AAPL", "NVDA", "AVGO", "AMD", "INTC", "SPY"],
        "allow_short": False,
        "max_new_buys_per_run": None,
        "max_open_positions": None,
        "position_size_pct_min": 0.10,
        "position_size_pct_max": 0.10,
        "use_notional": False,
        "max_sector_concentration_pct": 0.40,
    }
    agent.update(overrides)
    return agent


def _context(equity=100_000.0, cash=100_000.0, held=None, watchlist=None):
    return {
        "account": {"equity": equity, "cash": cash},
        "held_positions": held or {},
        "watchlist": watchlist or {},
        "open_orders": [],
    }


def _apply_agent(monkeypatch, **overrides):
    monkeypatch.setattr(config, "AGENT", _base_agent(**overrides))


def test_sanity_semiconductor_symbols_share_one_sector():
    assert sectors.sector_of("NVDA") == "Semiconductors"
    assert sectors.sector_of("AVGO") == sectors.sector_of("NVDA")


def test_broad_market_etf_is_exempt():
    assert sectors.sector_of("SPY") is None


def test_first_buy_in_a_sector_is_allowed(monkeypatch):
    _apply_agent(monkeypatch)
    context = _context(watchlist={"NVDA": {"last_price": 100.0}})
    out = ai_agent._enforce_caps([{"symbol": "NVDA", "action": "buy"}], context, {})
    assert out[0]["allowed"] is True


def test_new_buy_rejected_once_sector_exposure_at_cap(monkeypatch):
    _apply_agent(monkeypatch)
    # $39k already held in Semiconductors (NVDA) — cap is 40% of $100k = $40k.
    # A new 10%-of-equity ($10k) AVGO buy would push it to $49k, over the cap.
    context = _context(
        held={"NVDA": {"side": "long", "qty": 100, "current_price": 390.0,
                        "unrealized_pl_pct": 0.0, "market_value": 39_000.0}},
        watchlist={"AVGO": {"last_price": 200.0}},
    )
    out = ai_agent._enforce_caps([{"symbol": "AVGO", "action": "buy"}], context, {})
    assert out[0]["allowed"] is False
    assert "sector concentration cap reached for Semiconductors" in out[0]["cap_note"]


def test_buy_allowed_when_under_cap_even_with_existing_sector_exposure(monkeypatch):
    _apply_agent(monkeypatch)
    # $10k held in Semiconductors, cap room is $30k — a $10k new buy fits.
    context = _context(
        held={"NVDA": {"side": "long", "qty": 10, "current_price": 1000.0,
                        "unrealized_pl_pct": 0.0, "market_value": 10_000.0}},
        watchlist={"AVGO": {"last_price": 200.0}},
    )
    out = ai_agent._enforce_caps([{"symbol": "AVGO", "action": "buy"}], context, {})
    assert out[0]["allowed"] is True


def test_exempt_sector_never_blocked_regardless_of_exposure(monkeypatch):
    _apply_agent(monkeypatch, universe=["AAPL", "NVDA", "AVGO", "AMD", "INTC", "SPY", "QQQ"])
    # SPY already 90% of equity — buying QQQ (a different symbol, also an
    # exempt broad-market ETF, so also sector_of() -> None) is still
    # allowed: exempt symbols never accumulate into sector_exposure and
    # never get checked against it either way.
    context = _context(
        held={"SPY": {"side": "long", "qty": 100, "current_price": 900.0,
                       "unrealized_pl_pct": 0.0, "market_value": 90_000.0}},
        watchlist={"QQQ": {"last_price": 400.0}},
    )
    out = ai_agent._enforce_caps([{"symbol": "QQQ", "action": "buy"}], context, {})
    assert out[0]["allowed"] is True


def test_pending_orders_count_toward_sector_exposure(monkeypatch):
    _apply_agent(monkeypatch)
    # No held positions, but a pending AVGO buy already commits $35k to
    # Semiconductors — a new $10k NVDA buy would push it to $45k, over cap.
    context = _context(watchlist={"NVDA": {"last_price": 100.0}, "AVGO": {"last_price": 200.0}})
    out = ai_agent._enforce_caps([{"symbol": "NVDA", "action": "buy"}], context, {"AVGO": 175})
    assert out[0]["allowed"] is False
    assert "sector concentration cap reached" in out[0]["cap_note"]


def test_multiple_same_sector_buys_in_one_run_accumulate_toward_cap(monkeypatch):
    _apply_agent(monkeypatch, position_size_pct_min=0.15, position_size_pct_max=0.15)
    context = _context(watchlist={
        "NVDA": {"last_price": 100.0}, "AVGO": {"last_price": 100.0},
        "AMD": {"last_price": 100.0}, "INTC": {"last_price": 100.0},
    })
    # Four buys at 15% of $100k equity ($15k target notional each) in the
    # same sector: 1st and 2nd fit under the $40k cap (~$15k, ~$30k
    # committed), the 3rd would push past $40k and gets rejected — proving
    # sector_exposure accumulates across decisions within a single run, not
    # just against pre-existing held/pending state.
    decisions = [
        {"symbol": "NVDA", "action": "buy"},
        {"symbol": "AVGO", "action": "buy"},
        {"symbol": "AMD", "action": "buy"},
        {"symbol": "INTC", "action": "buy"},
    ]
    out = ai_agent._enforce_caps(decisions, context, {})
    assert out[0]["allowed"] is True
    assert out[1]["allowed"] is True
    assert out[2]["allowed"] is False
    assert "sector concentration cap reached" in out[2]["cap_note"]
    assert out[3]["allowed"] is False


def test_cap_disabled_when_not_set_on_agent(monkeypatch):
    _apply_agent(monkeypatch, max_sector_concentration_pct=None)
    context = _context(
        held={"NVDA": {"side": "long", "qty": 900, "current_price": 100.0,
                        "unrealized_pl_pct": 0.0, "market_value": 90_000.0}},
        watchlist={"AVGO": {"last_price": 100.0}},
    )
    out = ai_agent._enforce_caps([{"symbol": "AVGO", "action": "buy"}], context, {})
    assert out[0]["allowed"] is True
