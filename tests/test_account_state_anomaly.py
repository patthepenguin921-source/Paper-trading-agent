"""
_account_state_anomaly guards against the 2026-07-07 Alpaca outage pattern:
equity collapsing AND all positions vanishing simultaneously, which a real
market move can't produce in 15 minutes (closing positions converts to
cash, it doesn't destroy equity). See ai_agent.py:2239.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import ai_agent
import risk


def _mock_response(rows):
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = rows
    return resp


def _last_run_row(hours_ago, equity, num_positions):
    run_at = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat().replace("+00:00", "Z")
    return {"run_at": run_at, "account_equity": equity, "num_open_positions": num_positions}


def _context(equity, held_positions):
    return {"account": {"equity": equity}, "held_positions": held_positions}


def test_no_anomaly_on_stable_account(monkeypatch):
    monkeypatch.setattr(
        risk.requests, "get",
        lambda *a, **k: _mock_response([_last_run_row(0.25, 100_000, 3)]),
    )
    context = _context(99_500, {"AAPL": {}, "MSFT": {}, "TSLA": {}})
    assert ai_agent._account_state_anomaly(context) is None


def test_anomaly_when_equity_collapses_and_positions_vanish(monkeypatch):
    monkeypatch.setattr(
        risk.requests, "get",
        lambda *a, **k: _mock_response([_last_run_row(0.25, 100_000, 3)]),
    )
    context = _context(10_000, {})  # down 90%, zero positions
    result = ai_agent._account_state_anomaly(context)
    assert result is not None
    assert "anomaly" in result


def test_no_anomaly_if_equity_drops_but_positions_still_held(monkeypatch):
    monkeypatch.setattr(
        risk.requests, "get",
        lambda *a, **k: _mock_response([_last_run_row(0.25, 100_000, 3)]),
    )
    context = _context(10_000, {"AAPL": {}})  # big drop, but still holding
    assert ai_agent._account_state_anomaly(context) is None


def test_no_anomaly_if_positions_vanish_without_equity_collapse(monkeypatch):
    monkeypatch.setattr(
        risk.requests, "get",
        lambda *a, **k: _mock_response([_last_run_row(0.25, 100_000, 3)]),
    )
    context = _context(99_000, {})  # sold everything, equity ~unchanged
    assert ai_agent._account_state_anomaly(context) is None


def test_no_anomaly_when_last_run_too_old(monkeypatch):
    monkeypatch.setattr(
        risk.requests, "get",
        lambda *a, **k: _mock_response([_last_run_row(48, 100_000, 3)]),
    )
    context = _context(10_000, {})
    assert ai_agent._account_state_anomaly(context) is None


def test_no_anomaly_when_no_prior_runs(monkeypatch):
    monkeypatch.setattr(risk.requests, "get", lambda *a, **k: _mock_response([]))
    context = _context(10_000, {})
    assert ai_agent._account_state_anomaly(context) is None


def test_best_effort_on_request_failure(monkeypatch):
    def _raise(*a, **k):
        raise ConnectionError("supabase unreachable")

    monkeypatch.setattr(risk.requests, "get", _raise)
    context = _context(10_000, {})
    assert ai_agent._account_state_anomaly(context) is None
