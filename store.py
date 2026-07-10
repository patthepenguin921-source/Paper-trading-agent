"""
Supabase logging/reads and the push-notify helper. Owns the run-cadence
throttle (should_throttle_cadence), the daily report builder, per-run/
per-decision logging, and the agent's own recent-trade track record
(_recent_trade_outcomes) — everything that reads from or writes to
Supabase, in one place.
"""
import os
from datetime import datetime, timedelta, timezone

import requests

import config
import alpaca_client as ac
from backends import _active_model_name

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
NOTIFY_SECRET = os.environ.get("NOTIFY_SECRET", "")

RUN_TRIGGER = os.environ.get("RUN_TRIGGER", "unknown")


_MIN_REAL_RUN_INTERVAL_MINUTES = 13.0

def _minutes_since_last_real_run() -> float | None:
    """
    Minutes since this agent's last *real* run — a decision run (run() or
    run_premarket_review()), not a log_idle() check-in. None if there's no
    prior run or the check fails.
    """
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/trading_agent_runs",
            headers=_supabase_headers(),
            params={
                "agent_id": f"eq.{config.AGENT_ID}",
                "model_used": "not.is.null",
                "select": "run_at",
                "order": "run_at.desc",
                "limit": "1",
            },
            timeout=15,
        )
        resp.raise_for_status()
        rows = resp.json()
        if not rows:
            return None
        last_at = datetime.fromisoformat(rows[0]["run_at"].replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - last_at).total_seconds() / 60
    except Exception as e:
        print(f"Could not check last real-run cadence ({e}); proceeding without throttling.")
        return None


def should_throttle_cadence() -> bool:
    """
    True if this is an automatic (cron-triggered) tick and a real decision
    run for this agent already happened more recently than
    _MIN_REAL_RUN_INTERVAL_MINUTES ago.

    Every agent's instructions and pacing judgment ("X minutes since your
    last buy", "most checks should end in hold") are calibrated around
    being asked to decide roughly every 15 minutes — not every time the
    external Supabase pg_cron trigger happens to fire. main.py's own
    market_phase() gate only restricts *when* runs are allowed (market
    hours, the pre-market window), not *how often* within that window; if
    the external trigger ever fires faster than intended (it has, per
    several since-corrected comments in this repo's own history), nothing
    previously stopped a full AI decision call — with real orders on the
    line — from firing far more often than the "mostly hold" philosophy in
    instructions.md assumes. That's the exact shape of the overtrading
    incidents already recorded in this agent's own lessons-learned notes.
    This makes the intended cadence a real code-level property instead of
    something that only holds if an external scheduler is configured
    exactly right. Manual/forced runs (RUN_TRIGGER != 'schedule') always
    bypass this — a human or a manual_agent_run.py test asked for a run
    right now on purpose.
    """
    if RUN_TRIGGER != "schedule":
        return False
    minutes = _minutes_since_last_real_run()
    return minutes is not None and minutes < _MIN_REAL_RUN_INTERVAL_MINUTES


_DAILY_MISSED_MOVE_THRESHOLD_PCT = 3.0
_MAX_DAILY_MISSED_LISTED = 3

def _daily_missed_opportunities() -> list:
    """
    Informational-only daily check: universe symbols this agent wasn't
    holding and took no action on in the prior trading day, that still
    moved _DAILY_MISSED_MOVE_THRESHOLD_PCT%+ anyway. Unlike the weekly
    version (scripts/lessons_learned.py._missed_opportunities), nothing
    here gets written into permanent instructions — a single day's move is
    too noisy to trust as a standing lesson. It's surfaced fresh each
    morning as quick heads-up context, and persisted to agent_daily_reports
    (see _build_daily_report) so the dashboard can show a history of it.

    Best-effort: any failure here reduces this to an empty list rather than
    block the actual trading run.
    """
    try:
        universe = config.AGENT["universe"]
        held_symbols = set(ac.get_open_positions().keys())

        since = (datetime.now(timezone.utc) - timedelta(hours=20)).isoformat()
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/trading_agent_decisions",
            headers=_supabase_headers(),
            params={
                "agent_id": f"eq.{config.AGENT_ID}",
                "created_at": f"gte.{since}",
                "select": "symbol",
            },
            timeout=15,
        )
        resp.raise_for_status()
        symbols_seen = {r["symbol"] for r in resp.json() if r.get("symbol")}

        candidates = [s for s in universe if s not in held_symbols and s not in symbols_seen]
        if not candidates:
            return []

        bars_by_symbol = ac.get_recent_bars(candidates, lookback_days=4)
        movers = []
        for symbol in candidates:
            bars = bars_by_symbol.get(symbol)
            if not bars or len(bars) < 2:
                continue
            prior, last = bars[-2].close, bars[-1].close
            if not prior:
                continue
            pct = round((last - prior) / prior * 100, 2)
            if pct >= _DAILY_MISSED_MOVE_THRESHOLD_PCT:
                movers.append({"symbol": symbol, "pct_change": pct})

        movers.sort(key=lambda m: m["pct_change"], reverse=True)
        return movers[:_MAX_DAILY_MISSED_LISTED]
    except Exception as e:
        print(f"Could not compute daily missed-opportunity check ({e}); skipping it.")
        return []


def _build_daily_report() -> dict:
    """
    Builds this agent's daily learning report: yesterday's closed-trade
    win/loss record, the raw list of buy/sell/short/cover decisions, and a
    missed-opportunity heads-up — everything the pre-market review prompt
    needs (report["recap_text"]), plus a structured form that gets
    persisted to agent_daily_reports for the dashboard. This is the daily
    half of the learning loop; scripts/lessons_learned.py (same
    realized_pnl_pct field, run weekly) is the half that turns a real
    pattern into a permanent standing note instead of a fresh daily replay.
    """
    report = {
        "closed_trades": 0, "wins": 0, "losses": 0,
        "win_rate_pct": None, "avg_win_pct": None, "avg_loss_pct": None,
        "missed_opportunities": [], "recap_text": "",
    }
    try:
        since = (datetime.now(timezone.utc) - timedelta(hours=20)).isoformat()
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/trading_agent_decisions",
            headers=_supabase_headers(),
            params={
                "agent_id": f"eq.{config.AGENT_ID}",
                "action": "in.(buy,sell,short,cover)",
                "created_at": f"gte.{since}",
                "select": "symbol,action,qty,order_status,reasoning,realized_pnl_pct,confidence,created_at",
                "order": "created_at.asc",
            },
            timeout=15,
        )
        resp.raise_for_status()
        rows = resp.json()

        report["missed_opportunities"] = _daily_missed_opportunities()
        missed_line = ""
        if report["missed_opportunities"]:
            missed_str = ", ".join(
                f"{m['symbol']} {m['pct_change']:+.1f}%" for m in report["missed_opportunities"]
            )
            missed_line = (
                "\nHeads-up (informational only, not a standing lesson): these "
                "universe symbols weren't held or acted on yesterday and moved "
                f"{_DAILY_MISSED_MOVE_THRESHOLD_PCT:.0f}%+ anyway: {missed_str}\n"
            )

        if not rows:
            report["recap_text"] = (
                "No buy/sell/short/cover decisions were made in the prior trading day — it was a full hold."
                + missed_line
            )
            return report

        closed = [r for r in rows if r.get("realized_pnl_pct") is not None]
        stats_line = ""
        if closed:
            wins = [r for r in closed if r["realized_pnl_pct"] > 0]
            losses = [r for r in closed if r["realized_pnl_pct"] <= 0]
            report["closed_trades"] = len(closed)
            report["wins"] = len(wins)
            report["losses"] = len(losses)
            report["win_rate_pct"] = round(len(wins) / len(closed) * 100, 1)
            report["avg_win_pct"] = round(sum(r["realized_pnl_pct"] for r in wins) / len(wins), 2) if wins else None
            report["avg_loss_pct"] = round(sum(r["realized_pnl_pct"] for r in losses) / len(losses), 2) if losses else None
            stats_line = (
                f"Yesterday's closed-trade record: {report['closed_trades']} closed "
                f"({report['wins']} win{'s' if report['wins'] != 1 else ''}, {report['losses']} loss"
                f"{'es' if report['losses'] != 1 else ''}), win rate {report['win_rate_pct']:.0f}%, "
                f"avg win {report['avg_win_pct'] or 0:+.1f}%, avg loss {report['avg_loss_pct'] or 0:+.1f}%. "
                "Actually weigh this, not just the reasoning text below — a good-sounding "
                "thesis that keeps losing is still a losing pattern.\n\n"
            )

        lines = [
            f"- {r['action'].upper()} {r.get('qty') or ''} {r['symbol']} "
            f"({r.get('order_status', 'unknown')}"
            + (f", confidence={r['confidence']}" if r.get("confidence") else "")
            + (f", closed at {r['realized_pnl_pct']:+.1f}%" if r.get("realized_pnl_pct") is not None else "")
            + f"): {r.get('reasoning', '')}"
            for r in rows
        ]
        report["recap_text"] = (
            stats_line + "Buy/sell/short/cover decisions from the prior trading day:\n"
            + "\n".join(lines) + missed_line
        )
        return report
    except Exception as e:
        print(f"Could not build yesterday's recap ({e}); proceeding without it.")
        report["recap_text"] = "(Could not load yesterday's activity — proceed using current portfolio state only.)"
        return report


def _log_daily_report(report: dict):
    """
    Persists today's daily learning report (see _build_daily_report) to
    agent_daily_reports so the dashboard can show a history of it. Upserts
    on (agent_id, report_date) so a re-run the same day (e.g. a forced
    manual pre-market review) replaces rather than duplicates. Best-effort
    — a logging failure here must never block the actual trading run.
    """
    try:
        requests.post(
            f"{SUPABASE_URL}/rest/v1/agent_daily_reports",
            headers={**_supabase_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
            params={"on_conflict": "agent_id,report_date"},
            json={
                "agent_id": config.AGENT_ID,
                "report_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "closed_trades": report["closed_trades"],
                "wins": report["wins"],
                "losses": report["losses"],
                "win_rate_pct": report["win_rate_pct"],
                "avg_win_pct": report["avg_win_pct"],
                "avg_loss_pct": report["avg_loss_pct"],
                "missed_opportunities": report["missed_opportunities"],
                "recap_text": report["recap_text"],
            },
            timeout=15,
        ).raise_for_status()
    except Exception as e:
        print(f"Could not log daily report ({e}) — non-fatal.")


def _supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _notify(title: str, body: str):
    """Pushes a notification to the dashboard's subscribed devices.
    Best-effort only — a notify failure (no NOTIFY_SECRET, dashboard down,
    no subscribers yet, etc.) must never break or delay a trading run."""
    if not NOTIFY_SECRET:
        return
    try:
        requests.post(
            config.NOTIFY_URL,
            headers={"Content-Type": "application/json", "x-notify-key": NOTIFY_SECRET},
            json={"title": f"{config.AGENT['label']}: {title}", "body": body, "agent_id": config.AGENT_ID},
            timeout=10,
        )
    except Exception as e:
        print(f"Notify failed (non-fatal): {e}")


def _log_run(market_open: bool, context: dict | None, overall_reasoning: str,
             error: str | None, news_context: str | None = None) -> int | None:
    payload = {
        "agent_id": config.AGENT_ID,
        "trigger": RUN_TRIGGER,
        "market_open": market_open,
        "account_equity": context["account"]["equity"] if context else None,
        "account_cash": context["account"]["cash"] if context else None,
        "num_open_positions": len(context["held_positions"]) if context else None,
        "overall_reasoning": overall_reasoning,
        "model_used": _active_model_name(),
        "error": error,
        "news_context": news_context,
    }
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/trading_agent_runs",
        headers=_supabase_headers(),
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    rows = resp.json()
    return rows[0]["id"] if rows else None


def _log_decisions(run_id: int, decisions: list):
    if not decisions:
        return
    rows = [
        {
            "run_id": run_id,
            "agent_id": config.AGENT_ID,
            "symbol": d.get("symbol"),
            "action": d.get("action"),
            "qty": d.get("qty"),
            "entry_price": d.get("entry_price"),
            "exit_price": d.get("exit_price"),
            "realized_pnl_pct": d.get("realized_pnl_pct"),
            "confidence": d.get("confidence"),
            "reasoning": d.get("reasoning"),
            "order_id": d.get("order_id"),
            "order_status": d.get("order_status") or d.get("cap_note"),
        }
        for d in decisions
    ]
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/trading_agent_decisions",
        headers=_supabase_headers(),
        json=rows,
        timeout=30,
    )
    resp.raise_for_status()


def _refresh_account_state() -> dict:
    """
    Re-fetches account + position state fresh from Alpaca. Called after this
    run's own orders have been submitted, so what gets logged reflects what
    actually happened this run instead of the pre-trade snapshot that was
    only meant to feed the decision prompt above.
    """
    account = ac.get_account()
    positions = ac.get_open_positions()
    held = {}
    for symbol, pos in positions.items():
        qty = float(pos.qty)
        price_precision = 6 if ac.is_crypto(symbol) else 2  # sub-cent memecoins round to $0.00 at 2dp
        held[symbol] = {
            "side": "short" if qty < 0 else "long",
            "qty": qty,
            "avg_entry_price": round(float(pos.avg_entry_price), price_precision),
            "current_price": round(float(pos.current_price), price_precision),
            "unrealized_pl_pct": round(float(pos.unrealized_plpc) * 100, 2),
            "market_value": round(float(pos.market_value), 2),
        }
    return {
        "account": {
            "equity": round(float(account.equity), 2),
            "cash": round(float(account.cash), 2),
        },
        "held_positions": held,
    }


def log_idle(market_open: bool):
    """
    Lightweight check-in for cron ticks that don't run the full agent (market
    closed). Deliberately skips the AI entirely so it doesn't burn API quota
    every minute outside trading hours — just records a current account
    snapshot and a plain "checked in, no action" note.

    Inserts a fresh row every tick rather than updating one row in place.
    A prior version tried to collapse a closed period into a single
    continuously-updated row to keep the run log tidy, but that meant every
    equity/cash chart (compare tab, home page sparkline) could only ever
    plot one point for the whole closed stretch — no shape, no detail, even
    though positions (e.g. Eris' crypto leg) keep moving in the background.
    A distinct row per tick is what those charts need to show that.
    """
    try:
        state = _refresh_account_state()
        equity = state["account"]["equity"]
        cash = state["account"]["cash"]
        num_positions = len(state["held_positions"])
    except Exception as e:
        print(f"Could not fetch account snapshot for idle check-in ({e}).")
        equity = cash = num_positions = None

    payload = {
        "agent_id": config.AGENT_ID,
        "trigger": RUN_TRIGGER,
        "market_open": market_open,
        "account_equity": equity,
        "account_cash": cash,
        "num_open_positions": num_positions,
        "overall_reasoning": "Market is closed — checked in, no action taken.",
        "model_used": None,
        "error": None,
        "news_context": None,
    }
    try:
        requests.post(
            f"{SUPABASE_URL}/rest/v1/trading_agent_runs",
            headers=_supabase_headers(),
            json=payload,
            timeout=15,
        ).raise_for_status()
    except Exception as e:
        print(f"Could not log idle check-in ({e}) — non-fatal.")


def _log_positions(context: dict):
    """
    Replaces this agent's stored 'current positions' snapshot.
    Upsert-then-prune rather than delete-then-insert to avoid race windows
    with snapshot.py which writes to the same table every minute.
    """
    try:
        held = context["held_positions"] if context else {}
        if held:
            rows = [
                {
                    "agent_id": config.AGENT_ID,
                    "symbol": symbol,
                    "qty": pos["qty"],
                    "avg_entry_price": pos["avg_entry_price"],
                    "current_price": pos["current_price"],
                    "unrealized_pl_pct": pos["unrealized_pl_pct"],
                    "market_value": pos["market_value"],
                }
                for symbol, pos in held.items()
            ]
            requests.post(
                f"{SUPABASE_URL}/rest/v1/trading_agent_positions",
                headers={**_supabase_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
                params={"on_conflict": "agent_id,symbol"},
                json=rows,
                timeout=30,
            ).raise_for_status()

        held_list = ",".join(held.keys()) if held else ""
        symbol_filter = f"not.in.({held_list})" if held_list else "not.is.null"
        requests.delete(
            f"{SUPABASE_URL}/rest/v1/trading_agent_positions",
            headers=_supabase_headers(),
            params={"agent_id": f"eq.{config.AGENT_ID}", "symbol": symbol_filter},
            timeout=15,
        ).raise_for_status()
    except Exception as e:
        print(f"Could not update positions snapshot ({e}) — non-fatal.")


_RECENT_TRADES_LOOKBACK_DAYS = 14
_RECENT_TRADES_LIMIT = 20

def _recent_trade_outcomes() -> dict | None:
    """
    The agent's own recent closed-trade track record: its last
    _RECENT_TRADES_LIMIT executed sells/covers (including stop-loss backstop
    closes — those log as sells/covers too) with their realized P/L, plus
    rolling win-rate/expectancy stats computed from them.

    Surfaced in the decision context because until now the model decided
    every run with zero memory of how its recent trades actually went — the
    2026-07-09 profitability review found it repeatedly re-entering names it
    had just lost on and rating losing trades "high" confidence, and the
    only feedback loop was instructions edited after the fact. Same
    philosophy as minutes_since_last_buy: real numbers for the model to
    weigh, not a code-enforced rule.

    Best-effort: any failure returns None and the run proceeds without it.
    """
    try:
        since = (datetime.now(timezone.utc) - timedelta(days=_RECENT_TRADES_LOOKBACK_DAYS)).isoformat()
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/trading_agent_decisions",
            headers=_supabase_headers(),
            params={
                "agent_id": f"eq.{config.AGENT_ID}",
                "action": "in.(sell,cover)",
                "order_id": "not.is.null",
                "realized_pnl_pct": "not.is.null",
                "created_at": f"gte.{since}",
                "select": "symbol,action,realized_pnl_pct,confidence,created_at",
                "order": "created_at.desc",
                "limit": str(_RECENT_TRADES_LIMIT),
            },
            timeout=15,
        )
        resp.raise_for_status()
        rows = resp.json()
        if not rows:
            return None

        now = datetime.now(timezone.utc)
        trades = []
        for r in rows:
            closed_at = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))
            trades.append({
                "symbol": r["symbol"],
                # what kind of position the close realized, not the order side
                "closed": "short" if r["action"] == "cover" else "long",
                "realized_pnl_pct": round(float(r["realized_pnl_pct"]), 2),
                "confidence_at_exit": r.get("confidence"),
                "hours_ago": round((now - closed_at).total_seconds() / 3600, 1),
            })

        pnls = [t["realized_pnl_pct"] for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        stats = {
            "closed_trades": len(pnls),
            "lookback_days": _RECENT_TRADES_LOOKBACK_DAYS,
            "win_rate_pct": round(len(wins) / len(pnls) * 100, 1),
            "avg_win_pct": round(sum(wins) / len(wins), 2) if wins else None,
            "avg_loss_pct": round(sum(losses) / len(losses), 2) if losses else None,
            "expectancy_pct_per_trade": round(sum(pnls) / len(pnls), 2),
            "by_confidence": _confidence_calibration(trades),
        }
        return {"stats": stats, "trades": trades}
    except Exception as e:
        print(f"Could not build recent-trade track record ({e}); deciding without it this run.")
        return None


def _confidence_calibration(trades: list[dict]) -> dict:
    """
    Win rate/expectancy broken out by the confidence the model stated *at
    exit* (confidence_at_exit, from _recent_trade_outcomes' trades list),
    surfaced back to the model as its own calibration table.

    Added because the 2026-07-09 profitability review found "high"
    confidence trades underperforming "medium" ones — i.e. the stated field
    wasn't tracking actual outcome quality. Rather than silently dropping
    it, feed the agent its own track record the same way expectancy is fed:
    real numbers, model's judgment on what to do with them.
    """
    by_level: dict[str, list[float]] = {}
    for t in trades:
        level = t.get("confidence_at_exit") or "unstated"
        by_level.setdefault(level, []).append(t["realized_pnl_pct"])
    return {
        level: {
            "trades": len(pnls),
            "win_rate_pct": round(sum(1 for p in pnls if p > 0) / len(pnls) * 100, 1),
            "expectancy_pct_per_trade": round(sum(pnls) / len(pnls), 2),
        }
        for level, pnls in by_level.items()
    }


def _minutes_since_last_buy() -> float | None:
    """
    Minutes since this agent's most recent *executed* buy, or None if it has
    never bought anything. Surfaced to the model as information (see
    _build_decision_prompt's "portfolio status" section) so it can weigh its
    own pacing — this used to be a hard code-level cooldown that blocked any
    buy outright regardless of the AI's reasoning, but that meant the model
    couldn't actually reason about it at all (it was never even told the
    cooldown existed). Removed in favor of giving it the real numbers and
    trusting its judgment, same as the rest of the portfolio context.
    """
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/trading_agent_decisions",
            headers=_supabase_headers(),
            params={
                "agent_id": f"eq.{config.AGENT_ID}",
                "action": "eq.buy",
                "order_id": "not.is.null",
                "select": "created_at",
                "order": "created_at.desc",
                "limit": "1",
            },
            timeout=15,
        )
        resp.raise_for_status()
        rows = resp.json()
        if not rows:
            return None
        last_at = datetime.fromisoformat(rows[0]["created_at"].replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - last_at).total_seconds() / 60
    except Exception as e:
        print(f"Could not check last-buy cooldown ({e}); not enforcing it this run.")
        return None
