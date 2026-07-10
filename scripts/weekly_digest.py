"""
Weekly digest: compares all four agents' all-time returns and this week's
trade counts since each agent's first run, and pushes one push notification
via the same /api/notify endpoint the trading agents already use for
trade/failure alerts.

Run via .github/workflows/agent-review.yml.

Env vars required: SUPABASE_URL, SUPABASE_KEY, NOTIFY_SECRET
"""
import os
from datetime import datetime, timedelta, timezone

import requests

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
NOTIFY_SECRET = os.environ["NOTIFY_SECRET"]
NOTIFY_URL = "https://trading-agent-dashboard-mu.vercel.app/api/notify"

AGENTS = ["plutus", "helios", "hermes", "eris"]
LOOKBACK_DAYS = 7


def _headers():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}


def _benchmark_return_pct(symbol: str, since_iso: str) -> float | None:
    """Same idea as lessons_learned._benchmark_return_pct: % change in
    `symbol` from the first available benchmark_prices row at/after
    since_iso to the most recent one. Best-effort."""
    try:
        start_row = requests.get(
            f"{SUPABASE_URL}/rest/v1/benchmark_prices",
            headers=_headers(),
            params={"symbol": f"eq.{symbol}", "price_time": f"gte.{since_iso}",
                     "select": "close", "order": "price_time.asc", "limit": "1"},
            timeout=15,
        ).json()
        end_row = requests.get(
            f"{SUPABASE_URL}/rest/v1/benchmark_prices",
            headers=_headers(),
            params={"symbol": f"eq.{symbol}", "select": "close", "order": "price_time.desc", "limit": "1"},
            timeout=15,
        ).json()
        if not start_row or not end_row:
            return None
        start_price, end_price = float(start_row[0]["close"]), float(end_row[0]["close"])
        return round((end_price - start_price) / start_price * 100, 2) if start_price else None
    except Exception:
        return None


def _agent_summary(agent_id: str) -> dict:
    since = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).isoformat()
    runs = requests.get(
        f"{SUPABASE_URL}/rest/v1/trading_agent_runs",
        headers=_headers(),
        params={
            "agent_id": f"eq.{agent_id}",
            "select": "id,run_at,account_equity",
            "order": "run_at.asc",
        },
        timeout=30,
    ).json()

    equities = [r["account_equity"] for r in runs if r.get("account_equity") is not None]
    start, end = (equities[0], equities[-1]) if equities else (None, None)
    pct = ((end - start) / start * 100) if start and end else None

    # "vs SPY since inception" — the single most honest scoreboard number:
    # is this agent actually beating a passive index, not just up in
    # absolute terms. benchmark_prices is already populated continuously
    # by snapshot.py; this was previously write-only, nothing read it back.
    spy_pct = _benchmark_return_pct("SPY", runs[0]["run_at"]) if runs else None
    vs_spy_pct = round(pct - spy_pct, 2) if pct is not None and spy_pct is not None else None

    recent_ids = [r["id"] for r in runs if r["run_at"] >= since]
    trades = 0
    if recent_ids:
        decisions = requests.get(
            f"{SUPABASE_URL}/rest/v1/trading_agent_decisions",
            headers=_headers(),
            params={
                "run_id": f"in.({','.join(map(str, recent_ids))})",
                "action": "in.(buy,sell,short,cover)",
                "order_id": "not.is.null",
                "select": "id",
            },
            timeout=30,
        ).json()
        trades = len(decisions)

    return {"return_pct": pct, "vs_spy_pct": vs_spy_pct, "trades_this_week": trades}


def _format_line(label: str, s: dict) -> str:
    if s["return_pct"] is None:
        return f"{label}: no data yet"
    sign = "+" if s["return_pct"] >= 0 else ""
    vs_spy = ""
    if s["vs_spy_pct"] is not None:
        vs_spy_sign = "+" if s["vs_spy_pct"] >= 0 else ""
        vs_spy = f", {vs_spy_sign}{s['vs_spy_pct']:.2f}% vs SPY"
    return f"{label} {sign}{s['return_pct']:.2f}% all-time{vs_spy} ({s['trades_this_week']} trades this week)"


def main():
    summaries = {a: _agent_summary(a) for a in AGENTS}
    body = " | ".join(_format_line(a.capitalize(), s) for a, s in summaries.items())

    requests.post(
        NOTIFY_URL,
        headers={"Content-Type": "application/json", "x-notify-key": NOTIFY_SECRET},
        json={"title": "Weekly agent digest", "body": body, "agent_id": "digest"},
        timeout=10,
    ).raise_for_status()
    print(f"Digest sent: {body}")


if __name__ == "__main__":
    main()
