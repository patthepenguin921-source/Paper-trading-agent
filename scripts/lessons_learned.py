"""
Weekly job: reviews one agent's last 7 days of runs/decisions, computes its
actual win rate and avg win/loss % (overall, and broken down by confidence
level, action type, and symbol) PLUS what it missed — universe symbols it
passed on or never even considered that went on to gain anyway — asks
Gemini to draft 1-3 concrete "lessons learned" bullets grounded in that real
performance data (not just a read of its own reasoning text), and appends
them under the "## Lessons learned / standing notes" heading in that
agent's Supabase-stored instructions (agent_instructions.content).
ai_agent.py reads instructions from Supabase first (see _load_instructions),
so this takes effect on the agent's very next scheduled run — no redeploy
needed. This is the weekly half of the learning loop; ai_agent._build_daily_report
(daily, same realized_pnl_pct field) is the daily half, surfaced fresh each
pre-market run instead of being folded into these standing instructions.

Run once per agent via the AGENT_ID env var — see
.github/workflows/agent-review.yml, which matrices over all four agents
(plutus, helios, hermes, eris).

Env vars required: AGENT_ID, GEMINI_API_KEY, SUPABASE_URL, SUPABASE_KEY,
ALPACA_API_KEY, ALPACA_SECRET_KEY (the last two for the missed-opportunity
price check — see _missed_opportunities).
"""
import json
import os
import re
from datetime import datetime, timedelta, timezone

import requests

import alpaca_client as ac
import config

AGENT_ID = os.environ["AGENT_ID"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

LESSONS_HEADING = "## Lessons learned / standing notes"
LOOKBACK_DAYS = 7
MAX_BULLETS_KEPT = 15
# Ignore noise-level moves when flagging something as a "missed winner" —
# a 1% wiggle isn't a real missed opportunity, it's just market noise.
MISSED_MOVE_THRESHOLD_PCT = 3.0
MAX_MISSED_LISTED = 5


def _headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def _fetch_recent_activity():
    since = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).isoformat()
    runs = requests.get(
        f"{SUPABASE_URL}/rest/v1/trading_agent_runs",
        headers=_headers(),
        params={
            "agent_id": f"eq.{AGENT_ID}",
            "run_at": f"gte.{since}",
            "select": "id,run_at,account_equity,num_open_positions,overall_reasoning,error",
            "order": "run_at.asc",
        },
        timeout=30,
    ).json()

    run_ids = [r["id"] for r in runs]
    decisions = []
    if run_ids:
        decisions = requests.get(
            f"{SUPABASE_URL}/rest/v1/trading_agent_decisions",
            headers=_headers(),
            params={
                "run_id": f"in.({','.join(map(str, run_ids))})",
                "select": "symbol,action,order_status,reasoning,realized_pnl_pct,confidence,order_id",
            },
            timeout=30,
        ).json()
    return runs, decisions


def _pnl_breakdown(rows: list, key: str) -> dict:
    """
    Groups closed trades (realized_pnl_pct present) by `key` (e.g.
    "confidence" or "action") and returns win rate / avg win / avg loss per
    group — the actual correlation between what the agent said about a
    trade and what happened to it, rather than just a text sample.
    """
    groups: dict = {}
    for r in rows:
        pnl = r.get("realized_pnl_pct")
        if pnl is None:
            continue
        groups.setdefault(r.get(key) or "unknown", []).append(pnl)

    out = {}
    for group_key, pnls in groups.items():
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        out[group_key] = {
            "closed_trades": len(pnls),
            "win_rate_pct": round(len(wins) / len(pnls) * 100, 1),
            "avg_win_pct": round(sum(wins) / len(wins), 2) if wins else None,
            "avg_loss_pct": round(sum(losses) / len(losses), 2) if losses else None,
        }
    return out


def _max_drawdown_pct(equities: list) -> float | None:
    """
    Largest peak-to-trough decline in the week's equity curve, as a %. A
    return% that ended flat can still have hidden a much rougher week —
    this is the honest "how bad did it get" number a single win-rate/
    expectancy summary can't show.
    """
    if len(equities) < 2:
        return None
    peak = equities[0]
    max_dd = 0.0
    for e in equities:
        peak = max(peak, e)
        if peak > 0:
            max_dd = max(max_dd, (peak - e) / peak * 100)
    return round(max_dd, 2)


def _benchmark_return_pct(symbol: str, since_iso: str) -> float | None:
    """
    % change in `symbol` (from benchmark_prices, populated by snapshot.py)
    between the first available price at/after `since_iso` and the most
    recent price. Best-effort: missing data returns None rather than
    failing the weekly review.
    """
    try:
        start_row = requests.get(
            f"{SUPABASE_URL}/rest/v1/benchmark_prices",
            headers=_headers(),
            params={
                "symbol": f"eq.{symbol}",
                "price_time": f"gte.{since_iso}",
                "select": "close",
                "order": "price_time.asc",
                "limit": "1",
            },
            timeout=15,
        ).json()
        end_row = requests.get(
            f"{SUPABASE_URL}/rest/v1/benchmark_prices",
            headers=_headers(),
            params={
                "symbol": f"eq.{symbol}",
                "select": "close",
                "order": "price_time.desc",
                "limit": "1",
            },
            timeout=15,
        ).json()
        if not start_row or not end_row:
            return None
        start_price, end_price = float(start_row[0]["close"]), float(end_row[0]["close"])
        if not start_price:
            return None
        return round((end_price - start_price) / start_price * 100, 2)
    except Exception as e:
        print(f"[{AGENT_ID}] Could not fetch benchmark return for {symbol} ({e}), skipping.")
        return None


def _summarize(runs: list, decisions: list) -> dict:
    equities = [r["account_equity"] for r in runs if r.get("account_equity") is not None]
    errors = [r["error"] for r in runs if r.get("error")]
    acted_on = [d for d in decisions if d.get("action") in ("buy", "sell", "short", "cover")]
    executed = [d for d in acted_on if d.get("order_id")]
    closed = [d for d in decisions if d.get("realized_pnl_pct") is not None]
    wins = [d for d in closed if d["realized_pnl_pct"] > 0]
    losses = [d for d in closed if d["realized_pnl_pct"] <= 0]

    # Per-symbol pnl, sorted so the drafting prompt can call out the actual
    # best/worst performers by name instead of speaking in generalities.
    by_symbol: dict = {}
    for d in closed:
        by_symbol.setdefault(d["symbol"], []).append(d["realized_pnl_pct"])
    symbol_totals = {sym: round(sum(pnls), 2) for sym, pnls in by_symbol.items()}
    ranked_symbols = sorted(symbol_totals.items(), key=lambda kv: kv[1])

    equity_return_pct = (
        round((equities[-1] - equities[0]) / equities[0] * 100, 2)
        if len(equities) >= 2 and equities[0] else None
    )
    spy_return_pct = _benchmark_return_pct("SPY", runs[0]["run_at"]) if runs else None
    relative_return_pct = (
        round(equity_return_pct - spy_return_pct, 2)
        if equity_return_pct is not None and spy_return_pct is not None else None
    )

    return {
        "runs": len(runs),
        "errors": len(errors),
        "equity_start": equities[0] if equities else None,
        "equity_end": equities[-1] if equities else None,
        "equity_return_pct": equity_return_pct,
        "max_drawdown_pct": _max_drawdown_pct(equities),
        "spy_return_pct": spy_return_pct,
        "relative_return_vs_spy_pct": relative_return_pct,
        "trade_attempts": len(acted_on),
        "executed_trades": len(executed),
        "closed_trades": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(len(wins) / len(closed) * 100, 1) if closed else None,
        "avg_win_pct": round(sum(d["realized_pnl_pct"] for d in wins) / len(wins), 2) if wins else None,
        "avg_loss_pct": round(sum(d["realized_pnl_pct"] for d in losses) / len(losses), 2) if losses else None,
        "by_confidence": _pnl_breakdown(decisions, "confidence"),
        "by_action": _pnl_breakdown(decisions, "action"),
        "worst_symbols": ranked_symbols[:3],
        "best_symbols": ranked_symbols[-3:],
    }


def _week_pct_change(bars) -> float | None:
    """
    Rough week-over-week % change from a bars list — first vs last close in
    the returned window. This is a coarse "did this move" signal for
    flagging missed opportunities, not a precise backtest of what a trade
    entered mid-week would have actually returned.
    """
    if not bars or len(bars) < 2:
        return None
    first, last = bars[0].close, bars[-1].close
    if not first:
        return None
    return round((last - first) / first * 100, 2)


def _missed_opportunities(decisions: list) -> dict:
    """
    What the agent passed on this week that would have paid off anyway — the
    blind spot a pure win/loss review of executed trades can't see on its
    own. Two cases, ranked separately since they carry different weight:

    - "passed_on_and_gained": the agent actually reasoned about the symbol
      this week (an explicit hold, or a buy/short a risk cap rejected) and
      it moved up afterward regardless — the highest-value case, since the
      actual reasoning that led to sitting it out is right there to
      critique.
    - "never_considered_and_gained": a universe symbol with zero decision
      rows logged all week and no existing position in it — a fully silent
      miss. No reasoning captured, just the price move.

    Currently-held symbols are excluded from both — a position the agent is
    already in isn't a missed opportunity, and a bare "no new decision row
    this week" for something already held would otherwise look like total
    silence when it's actually just an unchanged position.

    Best-effort: any failure here (Alpaca hiccup, thin data) reduces this to
    an empty dict rather than take down the whole weekly review, same as
    every other best-effort block in this codebase.
    """
    try:
        universe = config.AGENT["universe"]
        bars_by_symbol = ac.get_recent_bars(universe, lookback_days=LOOKBACK_DAYS + 3)
        held_symbols = set(ac.get_open_positions().keys())

        moves = {}
        for symbol in universe:
            pct = _week_pct_change(bars_by_symbol.get(symbol))
            if pct is not None:
                moves[symbol] = pct

        symbols_seen = {d["symbol"] for d in decisions if d.get("symbol")}
        executed_symbols = {d["symbol"] for d in decisions if d.get("order_id")}
        passed_symbols = (symbols_seen - executed_symbols) - held_symbols
        untouched_symbols = set(universe) - symbols_seen - held_symbols

        passed_notes: dict = {}
        for d in decisions:
            sym = d.get("symbol")
            if sym in passed_symbols and d.get("reasoning") and sym not in passed_notes:
                passed_notes[sym] = d["reasoning"]

        passed_ranked = sorted(
            (
                {"symbol": sym, "week_pct_change": moves[sym], "reasoning_given": passed_notes.get(sym, "")}
                for sym in passed_symbols
                if sym in moves and moves[sym] >= MISSED_MOVE_THRESHOLD_PCT
            ),
            key=lambda r: r["week_pct_change"],
            reverse=True,
        )[:MAX_MISSED_LISTED]

        untouched_ranked = sorted(
            (
                {"symbol": sym, "week_pct_change": moves[sym]}
                for sym in untouched_symbols
                if sym in moves and moves[sym] >= MISSED_MOVE_THRESHOLD_PCT
            ),
            key=lambda r: r["week_pct_change"],
            reverse=True,
        )[:MAX_MISSED_LISTED]

        return {"passed_on_and_gained": passed_ranked, "never_considered_and_gained": untouched_ranked}
    except Exception as e:
        print(f"[{AGENT_ID}] Could not compute missed opportunities ({e}), skipping.")
        return {}


def _draft_lessons(summary: dict, decisions: list, missed: dict) -> list:
    # Pair reasoning with its actual outcome (rather than a bare text sample)
    # so the drafting model can see which kinds of reasoning led to wins vs.
    # losses, not just what the agent said in general.
    closed_with_reasoning = [
        {
            "symbol": d["symbol"],
            "action": d.get("action"),
            "confidence": d.get("confidence"),
            "realized_pnl_pct": d.get("realized_pnl_pct"),
            "reasoning": d.get("reasoning"),
        }
        for d in decisions
        if d.get("realized_pnl_pct") is not None and d.get("reasoning")
    ]
    closed_with_reasoning.sort(key=lambda d: d["realized_pnl_pct"])
    # Worst and best few — the informative extremes — rather than a random
    # or chronological slice, which tends to be mostly unremarkable holds.
    sample = closed_with_reasoning[:8] + closed_with_reasoning[-8:]

    has_missed = bool(missed.get("passed_on_and_gained") or missed.get("never_considered_and_gained"))
    missed_block = (
        f"""

This week's missed opportunities — universe symbols the agent either passed
on (with the reasoning given at the time) or never even considered, that
went on to gain {MISSED_MOVE_THRESHOLD_PCT:.0f}%+ anyway:
{json.dumps(missed, indent=2)}

Weigh these carefully, not automatically as mistakes — a filter that skips
some winners while also skipping the losses on similarly-shaped trades can
still be net positive. Only call out a missed opportunity if the reasoning
given for passing looks like a specific, avoidable flaw (a stale rule,
dismissing a real catalyst, a confidence miscalibration) rather than normal,
healthy selectivity."""
        if has_missed else ""
    )

    prompt = f"""You are reviewing one week of an autonomous paper-trading agent's
real gains, losses, and missed opportunities to draft standing notes for its
own future self. The goal is for the agent to actually get better over
time, not just repeat the same reasoning patterns regardless of whether
they've been working.

Weekly performance summary, including win rate and avg win/loss % broken
down by confidence level and by action type, and the best/worst performing
symbols by total realized P&L:
{json.dumps(summary, indent=2)}

This week's closed trades with the worst and best outcomes, paired with the
reasoning given for each at the time (sorted worst to best):
{json.dumps(sample, indent=2)}{missed_block}

Write 1-3 short, concrete bullet points (no more) capturing a real pattern
grounded in the data above — e.g. whether high-confidence trades actually
won more than low-confidence ones, whether a particular action/symbol/sector
is consistently costing money, a recurring flaw in the reasoning behind the
losing trades, or (per the missed-opportunities guidance above) a specific,
avoidable pattern of sitting out real winners. Skip generic advice ("be
careful", "diversify") that isn't backed by this week's actual data. If
nothing notable or statistically meaningful happened this week (e.g. too
few closed trades to draw a real conclusion), return an empty list. Respond
with ONLY a JSON array of strings, e.g. ["...", "..."]."""

    resp = requests.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
        params={"key": GEMINI_API_KEY},
        headers={"content-type": "application/json"},
        json={
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 400},
        },
        timeout=60,
    )
    resp.raise_for_status()
    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    bullets = json.loads(text)
    return [b.strip() for b in bullets if isinstance(b, str) and b.strip()]


def _update_instructions(new_bullets: list):
    if not new_bullets:
        print(f"[{AGENT_ID}] No new lessons this week.")
        return

    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/agent_instructions",
        headers=_headers(),
        params={"agent_id": f"eq.{AGENT_ID}", "select": "content"},
        timeout=15,
    )
    resp.raise_for_status()
    rows = resp.json()
    if not rows:
        print(f"[{AGENT_ID}] No agent_instructions row found, skipping.")
        return
    content = rows[0]["content"]

    if LESSONS_HEADING not in content:
        print(f"[{AGENT_ID}] Heading '{LESSONS_HEADING}' not found in instructions, skipping.")
        return

    before, after = content.split(LESSONS_HEADING, 1)
    existing_bullets = re.findall(r"^- (.+)$", after, flags=re.MULTILINE)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dated_new = [f"({today}) {b}" for b in new_bullets]
    combined = (existing_bullets + dated_new)[-MAX_BULLETS_KEPT:]

    new_section = "\n\n" + "\n".join(f"- {b}" for b in combined) + "\n"
    new_content = before + LESSONS_HEADING + new_section

    requests.patch(
        f"{SUPABASE_URL}/rest/v1/agent_instructions",
        headers=_headers(),
        params={"agent_id": f"eq.{AGENT_ID}"},
        json={"content": new_content, "updated_at": datetime.now(timezone.utc).isoformat()},
        timeout=30,
    ).raise_for_status()
    print(f"[{AGENT_ID}] Added {len(new_bullets)} lesson(s): {new_bullets}")


def _log_weekly_report(summary: dict, missed: dict, lessons_added: list):
    """
    Persists this week's full report — the same performance summary and
    missed-opportunity data fed to the drafting prompt, plus exactly which
    lesson bullets (if any) got appended to agent_instructions — to
    agent_weekly_reports, so the dashboard can show the reasoning behind
    each standing note rather than just the note itself. Upserts on
    (agent_id, week_ending) so a re-run this week (e.g. a manual
    workflow_dispatch) replaces rather than duplicates. Best-effort — a
    logging failure here must never fail the whole weekly review.
    """
    try:
        requests.post(
            f"{SUPABASE_URL}/rest/v1/agent_weekly_reports",
            headers={**_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
            params={"on_conflict": "agent_id,week_ending"},
            json={
                "agent_id": AGENT_ID,
                "week_ending": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "summary": summary,
                "missed_opportunities": missed,
                "lessons_added": lessons_added,
            },
            timeout=30,
        ).raise_for_status()
    except Exception as e:
        print(f"[{AGENT_ID}] Could not log weekly report ({e}) — non-fatal.")


def main():
    runs, decisions = _fetch_recent_activity()
    if not runs:
        print(f"[{AGENT_ID}] No runs in the last {LOOKBACK_DAYS} days, skipping.")
        return
    summary = _summarize(runs, decisions)
    missed = _missed_opportunities(decisions)
    if missed.get("passed_on_and_gained") or missed.get("never_considered_and_gained"):
        print(f"[{AGENT_ID}] Missed opportunities: {json.dumps(missed)}")
    bullets = _draft_lessons(summary, decisions, missed)
    _update_instructions(bullets)
    _log_weekly_report(summary, missed, bullets)


if __name__ == "__main__":
    main()
