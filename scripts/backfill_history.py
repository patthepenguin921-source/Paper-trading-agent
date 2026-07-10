"""
One-off backfill: reconstruct an agent's missing intraday equity history from
Alpaca's own portfolio-history endpoint, inserting it into trading_agent_runs
as trigger="backfill" rows.

Needed because log_idle()'s "update the existing idle row in place" logic
silently no-op'd on every 15-minute check-in after the first one (the
Supabase UPDATE policy on trading_agent_runs was missing — fixed separately
via migration), so the compare-tab graph was missing every point after that
first frozen row. This reconstructs those points from Alpaca's real recorded
equity rather than guessing, and skips any timestamp within a minute of a
row that's already logged so it doesn't create duplicates alongside real
decision runs or idle check-ins.
"""
import os
from datetime import datetime, timezone

import requests
from alpaca.trading.requests import GetPortfolioHistoryRequest

import alpaca_client as ac
import config

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]


def _headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _existing_run_minutes(agent_id: str) -> set[str]:
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/trading_agent_runs",
        headers=_headers(),
        params={"agent_id": f"eq.{agent_id}", "select": "run_at"},
        timeout=15,
    )
    resp.raise_for_status()
    return {row["run_at"][:16] for row in resp.json()}


def main():
    agent_id = config.AGENT_ID
    # Explicit start/end (midnight UTC today through now) rather than
    # period="1D" — Alpaca's period param resolves to the last session with
    # activity, which on a day the market never opens (e.g. a holiday) is
    # yesterday, not "since this morning" as intended.
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    end = datetime.now(timezone.utc)
    history = ac.trading_client.get_portfolio_history(
        GetPortfolioHistoryRequest(start=start, end=end, timeframe="5Min", extended_hours=True)
    )

    existing_minutes = _existing_run_minutes(agent_id)
    inserted = 0
    for ts, equity in zip(history.timestamp, history.equity):
        if equity is None:
            continue
        run_at = datetime.fromtimestamp(ts, tz=timezone.utc)
        if run_at.strftime("%Y-%m-%dT%H:%M") in existing_minutes:
            continue
        payload = {
            "agent_id": agent_id,
            "run_at": run_at.isoformat(),
            "trigger": "backfill",
            "account_equity": round(float(equity), 2),
            "overall_reasoning": "Backfilled from Alpaca portfolio history (idle-update bug had frozen this agent's log).",
            "model_used": None,
            "error": None,
        }
        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/trading_agent_runs",
            headers=_headers(),
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
        inserted += 1

    print(f"Backfilled {inserted} row(s) for {agent_id}.")


if __name__ == "__main__":
    main()
