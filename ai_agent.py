"""
AI-driven trading agent — orchestrator.

Each run:
  1. Gathers account state, open positions, and recent price stats for the
     universe in config.py (_build_context, _symbol_stats).
  2. Sends that context + instructions to the configured AI backend — Gemini
     is primary for all three agents (Plutus, Helios, Hermes), with
     Groq-hosted Llama-3.3-70b as fallback if Gemini's keys are exhausted —
     and asks for buy/sell/hold decisions with reasoning, as JSON
     (_build_decision_prompt, _call_model -> backends.py).
  3. Validates every decision against the hard risk caps in config.py —
     the AI's judgment never overrides these; they're enforced in code
     (risk.py's _enforce_caps).
  4. Executes approved orders via alpaca_client (_execute).
  5. Logs the full run (reasoning, decisions, outcomes) to Supabase so it
     can be reviewed later (store.py).

This module deliberately keeps risk enforcement and logging independent of
whether the AI call succeeds — a bad/failed AI response should never leave
silent gaps in the log, and should never bypass the risk caps.

Split from a single ~2800-line file into backends.py (raw Gemini/Groq
calls), news.py (Reddit/ApeWisdom/StockTwits + news research), risk.py
(caps/sizing/anomaly guards), and store.py (Supabase logging/reads) — this
module keeps the orchestration: context building, prompt assembly, and the
run()/run_premarket_review()/run_weekend_crypto_backstop() entry points.
Everything the split modules define is re-imported here too, so existing
callers/tests using ai_agent.<name> (e.g. ai_agent._enforce_caps) keep
working unchanged.
"""
import json
import re
from datetime import datetime, timezone

import requests
from alpaca.trading.enums import OrderSide

import config
import alpaca_client as ac
from schedule import market_phase

from util import _safe_str, _KEY_PARAM_RE  # noqa: F401 (re-exported)
from backends import (  # noqa: F401
    GEMINI_API_KEY, GEMINI_API_KEY_2, GEMINI_KEYS, GEMINI_KEY_NAMES,
    GROQ_API_KEY, GROQ_API_KEY_2, GROQ_KEYS, GROQ_KEY_NAMES,
    _groq_generate, _gemini_generate, _active_model_name,
)
from news import (  # noqa: F401
    REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, _reddit_oauth_token, _fetch_reddit_posts,
    _fetch_apewisdom, _fetch_stocktwits_trending, _fetch_crypto_trending,
    _fetch_retail_sentiment, _trim_to_last_sentence, _fetch_headline_block,
    _research_news_gemini, _research_news_groq, _research_news, _alert_stale_news,
    _get_news_context,
)
from risk import (  # noqa: F401
    _position_entry_dates, _max_favorable_excursion_pct, _canonical_symbol,
    _FILL_PRICE_BUFFER, _enforce_caps, _cancel_stale_orders, _account_state_anomaly,
    _check_daily_loss_breaker, _apply_stop_loss_backstop,
)
from store import (  # noqa: F401
    SUPABASE_URL, SUPABASE_KEY, NOTIFY_SECRET, RUN_TRIGGER,
    _minutes_since_last_real_run, should_throttle_cadence,
    _daily_missed_opportunities, _build_daily_report, _log_daily_report,
    _supabase_headers, _notify, _log_run, _log_decisions, _refresh_account_state,
    log_idle, _log_positions, _log_open_orders, _recent_trade_outcomes, _confidence_calibration,
    _minutes_since_last_buy,
)

def _symbol_stats(symbol: str, bars) -> dict | None:
    if not bars:
        return None
    closes = [b.close for b in bars]
    highs  = [b.high  for b in bars]
    lows   = [b.low   for b in bars]
    volumes = [b.volume for b in bars]
    if len(closes) < 2:
        return None

    last = closes[-1]
    price_precision = 6 if ac.is_crypto(symbol) else 2  # sub-cent memecoins round to $0.00 at 2dp

    def pct_change(n):
        if len(closes) <= n:
            return None
        prior = closes[-1 - n]
        return round((last - prior) / prior * 100, 2)

    def sma(n):
        if len(closes) < n:
            return None
        return round(sum(closes[-n:]) / n, price_precision)

    def rsi(period=14):
        """Wilder RSI over `period` days. Returns None if not enough data."""
        if len(closes) < period + 1:
            return None
        deltas = [closes[i] - closes[i - 1] for i in range(len(closes) - period, len(closes))]
        gains  = [d if d > 0 else 0.0 for d in deltas]
        losses = [-d if d < 0 else 0.0 for d in deltas]
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return round(100 - (100 / (1 + rs)), 1)

    def atr_pct(period=14):
        """ATR as % of last close — symbol's typical daily swing range."""
        if len(closes) < period + 1:
            return None
        trs = []
        for i in range(len(closes) - period, len(closes)):
            tr = max(
                highs[i]  - lows[i],
                abs(highs[i]  - closes[i - 1]),
                abs(lows[i]   - closes[i - 1]),
            )
            trs.append(tr)
        return round((sum(trs) / period) / last * 100, 2)

    def range_position(n=30):
        """Where last close sits in the n-day high-low range (0 = low, 100 = high)."""
        n = min(n, len(closes))
        hi = max(highs[-n:])
        lo = min(lows[-n:])
        if hi == lo:
            return 50.0
        return round((last - lo) / (hi - lo) * 100, 1)

    def vol_ratio():
        """5-day avg volume vs 20-day avg volume. >1 = elevated recent activity."""
        if len(volumes) < 20:
            return None
        avg5  = sum(volumes[-5:])  / 5
        avg20 = sum(volumes[-20:]) / 20
        if avg20 == 0:
            return None
        return round(avg5 / avg20, 2)

    sma20 = sma(20)
    sma50 = sma(50)

    crossover = None
    if sma20 is not None and sma50 is not None:
        if sma20 > sma50:
            crossover = "bullish"
        elif sma20 < sma50:
            crossover = "bearish"
        else:
            crossover = "neutral"

    return {
        # ---- price momentum ----
        "last_close":      round(last, price_precision),
        "pct_change_1d":   pct_change(1),
        "pct_change_5d":   pct_change(5),
        "pct_change_10d":  pct_change(10),
        "pct_change_30d":  pct_change(min(30, len(closes) - 1)),
        # ---- trend / moving averages ----
        "sma_20":          sma20,
        "sma_50":          sma50,
        "pct_vs_sma20":    round((last - sma20) / sma20 * 100, 2) if sma20 else None,
        "pct_vs_sma50":    round((last - sma50) / sma50 * 100, 2) if sma50 else None,
        "sma_crossover":   crossover,   # "bullish" | "bearish" | "neutral" | None
        # ---- momentum / mean-reversion ----
        "rsi_14":          rsi(),
        "range_pos_30d":   range_position(),  # 0 = 30d low, 100 = 30d high
        # ---- volume & volatility ----
        "vol_ratio_5d_20d": vol_ratio(),      # >1.2 = elevated volume
        "atr_pct_14d":      atr_pct(),        # typical daily swing % of price
    }


def _effective_universe(held_symbols: set) -> list[str]:
    """
    The static core universe (config.py's *_UNIVERSE lists) plus today's
    market-wide most-active/biggest-mover sample (see
    alpaca_client.get_market_screen) — so the watchlist isn't limited to
    the hand-picked core list. `held_symbols` is always included too, even
    if a position has since fallen out of both, so a symbol bought on a
    past dynamic slice never loses its price history/exit-management stats
    just because today's screen looks different.
    """
    dynamic_top_n = config.AGENT.get("dynamic_universe_top_n", 0)
    dynamic_symbols = ac.get_market_screen(dynamic_top_n) if dynamic_top_n else []
    return sorted(set(config.AGENT["universe"]) | set(dynamic_symbols) | set(held_symbols))


def _build_context():
    account = ac.get_account()
    positions = ac.get_open_positions()
    effective_universe = _effective_universe(set(positions.keys()))

    bars_by_symbol = ac.get_recent_bars(effective_universe, lookback_days=config.LOOKBACK_DAYS + 5)
    live_prices = ac.get_latest_prices(effective_universe) if config.AGENT.get("use_live_quotes") else {}

    entry_dates = _position_entry_dates(set(positions.keys()))
    now = datetime.now(timezone.utc)

    held = {}
    for symbol, pos in positions.items():
        qty = float(pos.qty)
        side = "short" if qty < 0 else "long"
        avg_entry_price = float(pos.avg_entry_price)
        price_precision = 6 if ac.is_crypto(symbol) else 2  # sub-cent memecoins round to $0.00 at 2dp
        entry_at = entry_dates.get(symbol)
        days_held = None
        if entry_at:
            try:
                entered = datetime.fromisoformat(entry_at.replace("Z", "+00:00"))
                days_held = round((now - entered).total_seconds() / 86400, 1)
            except ValueError:
                pass
        held[symbol] = {
            "side": side,
            "qty": qty,
            "avg_entry_price": round(avg_entry_price, price_precision),
            "current_price": round(float(pos.current_price), price_precision),
            "unrealized_pl_pct": round(float(pos.unrealized_plpc) * 100, 2),
            "market_value": round(float(pos.market_value), 2),
            "days_held": days_held,
            "max_favorable_excursion_pct": _max_favorable_excursion_pct(
                symbol, side, avg_entry_price, entry_at, bars_by_symbol.get(symbol)
            ),
        }

    watchlist = {}
    for symbol in effective_universe:
        if symbol in held:
            continue
        stats = _symbol_stats(symbol, bars_by_symbol.get(symbol))
        if stats:
            live = live_prices.get(symbol)
            if live:
                stats.update(live)
                last_price = stats.get("last_price")
                last_close = stats.get("last_close")
                if last_price and last_close:
                    stats["pct_change_intraday"] = round((last_price - last_close) / last_close * 100, 2)
            watchlist[symbol] = stats

    cash = round(float(account.cash), 2)
    equity = round(float(account.equity), 2)
    minutes_since_buy = _minutes_since_last_buy()
    starting_equity = config.AGENT.get("starting_equity", config.STARTING_EQUITY)

    try:
        open_orders = ac.get_open_orders_summary()
    except Exception as e:
        print(f"Could not fetch open orders for context ({e}); showing none this run.")
        open_orders = []

    return {
        "account": {
            "equity": equity,
            "cash": cash,
            "buying_power": round(float(account.buying_power), 2),
            "cash_pct_of_equity": round(cash / equity * 100, 1) if equity else None,
            "equity_vs_starting_balance": round(equity - starting_equity, 2),
            "shorting_enabled": bool(getattr(account, "shorting_enabled", False)),
            "pattern_day_trader": bool(getattr(account, "pattern_day_trader", False)),
            "daytrade_count": getattr(account, "daytrade_count", None),
        },
        "held_positions": held,
        "watchlist": watchlist,
        "open_orders": open_orders,
        "recent_closed_trades": _recent_trade_outcomes(),
        "open_positions_count": len(held),
        "max_open_positions": config.AGENT["max_open_positions"],
        "minutes_since_last_buy": round(minutes_since_buy, 1) if minutes_since_buy is not None else None,
    }


def _load_instructions() -> str:
    """
    Instructions live in Supabase (agent_instructions table, keyed by
    agent_id) so they can be edited from the dashboard per-agent. Falls
    back to the active agent's local instructions file if the Supabase read
    fails for any reason, so a bad network blip never takes the run down —
    except for dynamically-added agents (instructions_file is None for
    those), which have no local file to fall back to and so require the
    Supabase read to succeed.
    """
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/agent_instructions",
            headers=_supabase_headers(),
            params={"agent_id": f"eq.{config.AGENT_ID}", "select": "content"},
            timeout=15,
        )
        resp.raise_for_status()
        rows = resp.json()
        if rows and rows[0].get("content"):
            return rows[0]["content"]
    except Exception as e:
        print(f"Could not load instructions from Supabase ({e}), falling back to local file.")

    instructions_file = config.AGENT.get("instructions_file")
    if not instructions_file:
        raise RuntimeError(
            f"No instructions available for agent '{config.AGENT_ID}': the Supabase "
            "agent_instructions read failed or returned nothing, and this agent has "
            "no local instructions file to fall back to (dynamically-added agents "
            "depend on the Supabase row existing)."
        )
    with open(instructions_file, "r") as f:
        return f.read()


def _build_decision_prompt(context: dict, news_context: str | None,
                            extra_framing: str = "",
                            news_age_minutes: float | None = None) -> tuple[str, str]:
    """Builds (system_prompt, user_message) for the decision call."""
    starting_equity = config.AGENT.get("starting_equity", config.STARTING_EQUITY)
    minutes_since_buy = context.get("minutes_since_last_buy")
    if minutes_since_buy is None:
        pacing_line = "No prior buy on record — this would be the first."
    elif minutes_since_buy < 60:
        pacing_line = f"{minutes_since_buy:.0f} minutes since your last buy."
    else:
        pacing_line = f"{minutes_since_buy / 60:.1f} hours since your last buy."

    equity_delta = context["account"]["equity_vs_starting_balance"]
    if equity_delta >= 0:
        equity_line = f"${equity_delta:,.2f} ABOVE the ${starting_equity:,.0f} starting balance."
    else:
        equity_line = f"${abs(equity_delta):,.2f} BELOW the ${starting_equity:,.0f} starting balance."

    allow_short = bool(config.AGENT.get("allow_short"))
    max_new = config.AGENT.get("max_new_buys_per_run")

    # Precomputed (rather than inline in the f-string below) because a couple
    # of these need literal double quotes, and an f-string expression can't
    # contain a backslash escape.
    short_selling_note = (
        "- Short selling is allowed. Shorts and covers are always whole-share (no fractional/notional shorting)."
        if allow_short else
        '- Short selling is NOT available to you — long only, regardless of what you conclude. A "short" decision will simply be rejected by the code.'
    )
    action_field_note = (
        ' "short" opens a new short position (you profit if the price drops). "cover" closes an existing '
        'short position in full (buying back the shares) — use this, not "buy", to exit a short.'
        if allow_short else ""
    )
    limit_price_short_note = (
        " For a limit short, set this above the current price (sell into a bounce). For a limit cover, set "
        "this below the current price (buy back the drop as your profit target)."
        if allow_short else ""
    )
    daily_cap = config.AGENT.get("max_daily_loss_pct")
    daily_breaker_note = (
        f"\n- Daily loss circuit breaker: if equity falls more than {daily_cap * 100:.0f}% below "
        "the day's first reading, new buys and shorts are rejected in code for the rest of the "
        "trading day. Sells, covers, and cancels always still work — a locked-out day is for "
        "managing what you hold, not adding to it."
        if daily_cap else ""
    )
    has_crypto = any(ac.is_crypto(s) for s in config.AGENT["universe"])
    crypto_note = (
        '\n- Crypto pairs in your universe (formatted like "BTC/USD") are spot-only on '
        'Alpaca — no margin, no shorting, ever. A "short"/"cover" decision on one of '
        "those is simply rejected regardless of your shorting setting; only "
        '"buy"/"sell" apply to them, and both can be fractional/notional. Crypto '
        "trades 24/7: this market-hours run covers it alongside your meme stocks, "
        "and a separate off-hours/weekend decision cycle (crypto-only — see "
        "run_crypto_afterhours) covers the nights, weekends, and holidays this run "
        "doesn't. You do get real, ongoing eyes on it outside market hours now — "
        "just from a different run than this one, so don't assume a position sat "
        "unwatched just because it moved while the equity market was closed."
        if has_crypto else ""
    )

    track_record = context.get("recent_closed_trades")
    if track_record:
        s = track_record["stats"]
        avg_win = f"{s['avg_win_pct']:+.2f}%" if s["avg_win_pct"] is not None else "n/a"
        avg_loss = f"{s['avg_loss_pct']:+.2f}%" if s["avg_loss_pct"] is not None else "n/a"
        track_record_line = (
            f"\n- Your recent track record (last {s['closed_trades']} closed trades, "
            f"{s['lookback_days']}-day window, computed from your own logs): "
            f"{s['win_rate_pct']:.0f}% win rate, avg win {avg_win}, avg loss {avg_loss}, "
            f"expectancy {s['expectancy_pct_per_trade']:+.2f}% per trade. The per-trade "
            "list is in recent_closed_trades in the account state. Weigh this honestly: "
            "if expectancy is negative, more trades of the same kind make it worse, not "
            "better. If avg loss outweighs avg win, you're cutting winners early and "
            "riding losers. And before re-entering a symbol you recently exited at a "
            "loss, check the list — the same thesis retried minutes later is how "
            "churn happens; a re-entry needs something genuinely new."
        )
        by_confidence = s.get("by_confidence") or {}
        if len(by_confidence) > 1:
            parts = [
                f"{level} ({c['trades']} trades): {c['win_rate_pct']:.0f}% win rate, "
                f"expectancy {c['expectancy_pct_per_trade']:+.2f}%"
                for level, c in by_confidence.items()
            ]
            track_record_line += (
                "\n- Your own confidence calibration (win rate by the confidence you stated "
                f"at exit): {'; '.join(parts)}. If \"high\" isn't outperforming \"medium\"/\"low\" "
                "here, the field isn't tracking real conviction — recalibrate what makes you say "
                "\"high,\" or stop leaning on it to size positions."
            )
    else:
        track_record_line = ""

    short_status_line = ""
    if allow_short:
        short_status_line = (
            f"\n- Shorting: {'enabled' if context['account']['shorting_enabled'] else 'DISABLED on this account right now — short/cover orders will be rejected'} "
            f"on this account. Buying power (includes margin): ${context['account']['buying_power']:,.2f}.\n"
            f"- Pattern day trading: {context['account']['daytrade_count']} day trades in the trailing "
            f"5 trading days{' — flagged as a pattern day trader' if context['account']['pattern_day_trader'] else ''}. "
            "With under $25k equity, a margin account gets restricted once it's flagged as a pattern day "
            "trader (4+ round trips — same-day open+close of a position — in 5 trading days). Watch this "
            "number; it's a real broker-enforced limit, not a code cap, and Alpaca will start rejecting "
            "orders if it's tripped."
        )

    system_prompt = _load_instructions() + extra_framing + f"""

## Your current portfolio status (weigh this yourself — nothing here is a rule, it's information)
- Equity is currently {equity_line} Try to stay above the starting balance
  as much as possible — that's a real goal to weigh in your own risk-taking
  and sizing decisions, not a hard rule the code enforces.
- Cash: {context['account']['cash_pct_of_equity']}% of equity. There is no
  hard cash-floor cap — you can deploy all of it if you have a real reason
  to, but spending it down to (or near) zero is itself a risk to the equity
  goal above, not a neutral act.
- Open positions: {context['open_positions_count']}{f" of {context['max_open_positions']} max" if context['max_open_positions'] is not None else " (no hard cap on count)"}.
  Each entry in held_positions includes days_held and max_favorable_excursion_pct
  (the best price seen since entry, in your favorable direction, as a % move —
  best-effort, not always available). Compare that to unrealized_pl_pct: if MFE
  was well above where you're sitting now, the position already ran and you're
  giving it back, which is a different decision than one that never moved.
- Open (unfilled) orders: {len(context.get('open_orders', []))} — full detail in open_orders in
  the account state (symbol, side, type, limit price, age in minutes). These
  are yours to manage, and unfilled orders silently reserve shares and cash:
  reconsider anything price action has moved past, and cancel/replace rather
  than leaving a stale order working a thesis you no longer hold. New orders
  on a symbol with a pending order are rejected as duplicates — cancel first.
- {pacing_line}{track_record_line}{short_status_line}
None of the above blocks you — the code will stop you from exceeding the
hard limits below, but everything in this section is judgment, not
enforcement.

## Hard limits enforced in code (for your awareness — you don't need to do this math)
- {f"Max open positions at once: {config.AGENT['max_open_positions']}" if config.AGENT['max_open_positions'] is not None else "No cap on number of open positions — sizing and pacing are the controls"}
- {f"Max new positions opened per run: {max_new}" if max_new is not None else "No cap on new positions (buys or shorts) opened per run — act on every genuine setup you find, not just the first couple"}
- Position sizing: {config.AGENT['position_size_pct_min'] * 100:.0f}%–{config.AGENT['position_size_pct_max'] * 100:.0f}%
  of equity per buy or short. This is a range, not a fixed amount — size each
  position yourself within it based on how strongly you believe in it. A
  high-conviction idea can sit near the top of the range; something you're
  taking a smaller swing on can sit near the bottom. The code only clamps
  you to the range if you go outside it — it does not pick the number for
  you, and there's no requirement that positions end up similar sizes.
{short_selling_note}{daily_breaker_note}{crypto_note}

## Output format
Respond with ONLY valid JSON, no markdown fences, no other text, matching
exactly this shape:

{{
  "overall_reasoning": "1-3 sentences on your overall read of the portfolio/market this run",
  "decisions": [
    {{"symbol": "AAPL", "action": "buy|sell{"|short|cover" if allow_short else ""}|hold|cancel", "order_type": "market|limit", "limit_price": 0.00, "size_pct": 0.10, "confidence": "low|medium|high", "reasoning": "why"}}
  ]
}}

Only include symbols you want to take action on. Omitting a symbol means
hold/no action. Field notes:

- **action**: "buy" opens/adds a long position. "sell" closes an existing
  long position in full — it only works on symbols listed in your
  held_positions; it is NOT a way to express a bearish view on something
  you don't hold.{action_field_note} "cancel" cancels ALL of your open
  (unfilled) orders on that symbol — see open_orders in the account state
  for what's currently pending; use cancel when an order you placed earlier
  no longer matches your thesis, or before re-placing it at a better price.
  (A sell/cover automatically cancels that symbol's open orders first, so
  you don't need a separate cancel to exit.)
- **order_type**: "market" (default, fills immediately) or "limit" (GTC order,
  fills when price reaches limit_price). Omit to default to "market". Prefer
  limit orders whenever you have a specific price in mind rather than "now at
  whatever it's trading at" — they're your main tool for precise entries and
  exits, not a rarely-used option.
- **limit_price**: Required when order_type is "limit". For a limit buy, set
  this below the current price (buy the dip). For a limit sell, set this above
  the current price (take-profit target).{limit_price_short_note}
  Use the bid/ask/spread_pct in the watchlist data (when present) to set a
  realistic price — a limit price on the wrong side of the spread just won't
  fill. The order stays live (GTC) until it fills or is cancelled by a future
  run — you're expected to track your own open limit orders and reconsider
  them (not just set-and-forget) as price action develops.
- **size_pct**: Fraction of equity per buy{"/short" if allow_short else ""} (see range above). Ignored for
  sell/cover.
- Sells and covers always close the full position. A limit sell/cover closes
  the full position at the target price instead of immediately at market.
"""

    # Honest description of where the briefing actually comes from and how
    # old it is. The old label claimed "live web search" unconditionally —
    # no agent has that (Search grounding isn't on the free tier), and a
    # model told its briefing is fresh treats 9-day-old content as current
    # fact (this happened: Plutus/Helios traded on a June-30 briefing until
    # July 9). Say what it is, say how old it is, and flag it when stale.
    grounded = config.AGENT.get("news_search_grounded", True)
    source_desc = (
        "researched via live web search" if grounded
        else "SYNTHESIZED BY A MODEL from real Alpaca News API headlines"
        + (" and live retail-sentiment data (aggregated Reddit ticker mentions, "
           "StockTwits trending)" if config.AGENT.get("reddit_subreddits") else "")
    )
    if news_age_minutes is None:
        age_line = ""
    elif news_age_minutes > 3 * config.AGENT["news_refresh_minutes"]:
        age_line = (
            f"\nWARNING: this briefing is {news_age_minutes / 60:.1f} HOURS OLD (refresh has been "
            "failing). Treat anything time-sensitive in it as unreliable and lean on price "
            "action and the raw headlines below instead.\n"
        )
    else:
        age_line = f"\n(Briefing last refreshed {news_age_minutes:.0f} minutes ago.)\n"

    news_block = (
        f"\n\n## Current news / market catalyst context ({source_desc})\n"
        "This is a paraphrased briefing, not a primary source — trust specific numbers, "
        "dates, and figures ONLY if they also appear in the raw headlines below; a "
        "synthesized briefing can inflate or misstate specifics.\n"
        + age_line + "\n" + news_context
        if news_context else
        "\n\n## Current news / market catalyst context\n"
        "(unavailable this run — reason about price action alone)\n"
    )

    # Raw, dated headlines go straight to the decision model too — until
    # now it only ever saw the paraphrase, so it had no way to sanity-check
    # a specific claim (Hermes once shorted META over a "$1.4 trillion
    # penalty" no headline supports). Best-effort, like everything news.
    headlines_block = ""
    try:
        raw_headlines = _fetch_headline_block()
        if raw_headlines:
            headlines_block = (
                "\n\n## Raw recent headlines (Alpaca News API — dated, unedited; "
                "your primary source for specific facts)\n" + raw_headlines
            )
    except Exception as e:
        print(f"Could not fetch raw headlines for the decision prompt ({e}); continuing without.")

    user_message = (
        "Here is the current account state and market context for this run:\n\n"
        + json.dumps(context, indent=2)
        + news_block
        + headlines_block
    )
    return system_prompt, user_message


def _call_model(context: dict, news_context: str | None, extra_framing: str = "",
                news_age_minutes: float | None = None) -> dict:
    """
    Routes the decision call to either Groq (llama-3.3-70b, if
    ai_backend == "groq") or Gemini based on the active agent's ai_backend
    config key. All three agents (Plutus, Helios, Hermes) currently run on
    Gemini as primary. Both paths build the same prompt and return the same
    dict shape so the rest of run() doesn't need to know which backend was
    used.
    """
    system_prompt, user_message = _build_decision_prompt(
        context, news_context, extra_framing, news_age_minutes=news_age_minutes)
    backend = config.AGENT.get("ai_backend", "gemini")

    last_exc = None
    for attempt in range(2):
        prompt = user_message
        if attempt > 0:
            prompt += (
                "\n\n## Your previous response was invalid JSON\n"
                f"Parse error: {last_exc}\n"
                "Keep every string value on a single line with no literal line "
                "breaks, make sure any quotes inside text are properly escaped, "
                "and keep 'reasoning' to one short sentence per symbol."
            )
        if backend == "groq":
            text = _groq_generate(system_prompt, prompt, json_mode=True, max_output_tokens=3500)
        else:
            text = _gemini_generate(system_prompt, prompt, json_mode=True, max_output_tokens=3500)

        cleaned = re.sub(r"^```json|```$", "", text.strip(), flags=re.MULTILINE).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            last_exc = e
            print(f"AI JSON parse failed on attempt {attempt + 1}/2 ({e}).")
    raise last_exc


def _notify_size(d: dict) -> str:
    """Human-readable order size for a notification line. Whole-share buys
    and sells always have qty set, but Hermes's notional/fractional buys
    (use_notional) never get an integer qty -- only a spent dollar amount
    (notional_order) and an estimated per-share entry_price -- so qty was
    printing as the literal string "None". Falls back to the dollar value
    actually spent, then to price, rather than a missing share count."""
    qty = d.get("qty")
    if qty is not None:
        return str(qty)
    notional = d.get("notional_order")
    if notional is not None:
        return f"${notional:,.2f}"
    price = d.get("entry_price")
    if price is not None:
        return f"@ ${price:,.2f}"
    return "?"


def _execute(decisions: list):
    for d in decisions:
        if not d.get("allowed"):
            d["order_id"] = None
            d["order_status"] = f"skipped: {d.get('cap_note', 'not allowed')}"
            continue
        try:
            order_type = d.get("order_type", "market").lower()
            limit_price = d.get("limit_price")
            notional_order = d.get("notional_order")
            if d["action"] in ("sell", "cover", "cancel"):
                # Any open order on this symbol holds its shares hostage:
                # Alpaca rejects a new exit order with 40310000
                # ("held_for_orders") while a pending GTC limit exit exists
                # — the most common execution error in the run log. Clear
                # the symbol's open orders before an exit so the decision
                # actually executes; for "cancel" this IS the action.
                n_cancelled = ac.cancel_open_orders_for_symbol(d["symbol"])
                if n_cancelled:
                    print(f"Cancelled {n_cancelled} open order(s) on {d['symbol']} "
                          + ("(explicit cancel decision)." if d["action"] == "cancel"
                             else "so the exit isn't blocked by held shares."))
            if d["action"] == "cancel":
                d["order_id"] = None
                d["order_status"] = (
                    f"cancelled {n_cancelled} open order(s)" if n_cancelled
                    else "no open orders found to cancel"
                )
                continue
            if d["action"] == "buy":
                qty = d.get("qty", 1)
                if notional_order:
                    # Fractional/notional market buy (Hermes)
                    result = ac.submit_market_order(d["symbol"], notional_order, OrderSide.BUY)
                elif order_type == "limit" and limit_price:
                    result = ac.submit_limit_order(d["symbol"], qty, OrderSide.BUY, limit_price)
                else:
                    result = ac.submit_qty_order(d["symbol"], qty, OrderSide.BUY)
            elif d["action"] == "short":
                # Opening a short: a plain SELL order on a symbol with no
                # existing long position. Alpaca opens the short automatically
                # (margin-enabled paper account) — there's no separate "short"
                # order type. Always whole-share qty, never notional.
                qty = d.get("qty", 1)
                if order_type == "limit" and limit_price:
                    result = ac.submit_limit_order(d["symbol"], qty, OrderSide.SELL, limit_price)
                else:
                    result = ac.submit_qty_order(d["symbol"], qty, OrderSide.SELL)
            elif d["action"] == "cover":
                # Closing a short: a BUY order for the shares. close_position
                # handles market covers (it liquidates whatever position
                # exists, long or short); a limit cover needs an explicit BUY
                # limit order since close_position is always a market order.
                qty = d.get("qty", 0)
                if order_type == "limit" and limit_price and qty:
                    result = ac.submit_limit_order(d["symbol"], qty, OrderSide.BUY, limit_price)
                else:
                    result = ac.close_position(d["symbol"])
            else:  # sell (closing a long)
                qty = d.get("qty", 0)
                if order_type == "limit" and limit_price and qty:
                    result = ac.submit_limit_order(d["symbol"], qty, OrderSide.SELL, limit_price)
                else:
                    result = ac.close_position(d["symbol"])
            d["order_id"] = str(result.id) if hasattr(result, "id") else None
            d["order_status"] = str(getattr(result, "status", "submitted"))
        except Exception as e:
            d["order_id"] = None
            d["order_status"] = f"error: {_safe_str(e)}"


def run(extra_context: str = ""):
    context = None
    news_context = None
    overall_reasoning = ""
    market_open = True
    try:
        market_open = ac.is_market_open()
        _cancel_stale_orders()
        context = _build_context()
        missing = [
            s for s in config.AGENT["universe"]
            if s not in context["held_positions"] and s not in context["watchlist"]
        ]
        print(
            f"Context built: {len(context['watchlist'])} watchlist symbols, "
            f"{len(context['held_positions'])} held."
            + (f" No price data this run for: {', '.join(missing)}" if missing else "")
        )
        if not market_open:
            print(
                "Note: market is actually closed right now (this is a force-run via "
                "manual_agent_run.py, which intentionally bypasses the market-hours "
                "gate). Any orders submitted will sit unfilled until the next open."
            )

        anomaly = _account_state_anomaly(context)
        if anomaly:
            print(anomaly)
            _log_run(market_open, context, overall_reasoning="", error=anomaly, news_context=None)
            _notify("Skipped run on bad account data", anomaly[:200])
            return

        stop_loss_decisions = _apply_stop_loss_backstop()
        if stop_loss_decisions:
            # Rebuild so the model reasons from the post-close state instead
            # of seeing positions the backstop just liquidated.
            context = _build_context()

        breaker_reason, breaker_already_tripped = _check_daily_loss_breaker(
            context["account"]["equity"]
        )
        breaker_framing = ""
        if breaker_reason:
            print(f"DAILY LOSS BREAKER ACTIVE — {breaker_reason}")
            if not breaker_already_tripped:
                _notify("daily loss breaker tripped", breaker_reason[:200])
            breaker_framing = (
                "\n\n## Daily loss circuit breaker is ACTIVE this run\n"
                f"{breaker_reason}. Any buy/short you output will be rejected in code, "
                "so don't spend decisions on new entries — this run is for managing what "
                "you already hold: exit what's broken (sell/cover), cancel stale orders, "
                "and hold what still deserves it.\n"
            )

        news_context, news_age_minutes = _get_news_context()

        # Extra framing injected when the run was triggered manually with a prompt
        manual_framing = (
            f"\n\n## Manual context from Carter (injected for this run only)\n{extra_context}\n"
            if extra_context else ""
        )

        ai_response = _call_model(context, news_context, extra_framing=breaker_framing + manual_framing,
                                  news_age_minutes=news_age_minutes)
        overall_reasoning = ai_response.get("overall_reasoning", "")
        decisions = ai_response.get("decisions", [])

        held_long_symbols = {s for s, p in context["held_positions"].items() if p["side"] == "long"}
        decisions = _enforce_caps(
            decisions, context, ac.get_pending_buy_info(),
            ac.get_pending_short_info(held_long_symbols),
            block_new_reason=breaker_reason,
        )
        _execute(decisions)
        decisions = stop_loss_decisions + decisions

        try:
            post_context = _refresh_account_state()
        except Exception as e:
            print(f"Could not refresh post-trade account state ({e}); logging pre-trade snapshot instead.")
            post_context = context
        _log_positions(post_context)
        _log_open_orders()

        run_id = _log_run(market_open, post_context, overall_reasoning, error=None, news_context=news_context)
        _log_decisions(run_id, decisions)

        print(f"Run complete. Reasoning: {overall_reasoning}")
        for d in decisions:
            print(f"  {d['symbol']}: {d['action']} -> {d.get('order_status')} | {d.get('reasoning', '')}")

        executed = [d for d in decisions if d.get("order_id")]
        if executed:
            summary = ", ".join(f"{d['action'].upper()} {_notify_size(d)} {d['symbol']}" for d in executed)
            _notify("made a move", summary)

    except Exception as e:
        safe_msg = _safe_str(e)
        print(f"Agent run failed: {safe_msg}")
        _log_run(market_open, context, overall_reasoning=overall_reasoning, error=safe_msg, news_context=news_context)
        _notify("Run failed", safe_msg[:200])
        raise


_PREMARKET_FRAMING = """

## This is your once-daily pre-market review
Markets are still closed — they open in about an hour. This is a dedicated
moment to look back at the prior trading day (decisions and outcomes below)
and your current equity/cash/positions, and decide whether there's a
genuine reason to queue a buy ahead of the open. You do not have to buy —
if nothing here changes your thesis on anything, holding is the right
answer, exactly like any other run. A buy placed now queues as a normal
day order and fills at or shortly after the open; it does not fill
immediately.
"""


def run_premarket_review(extra_context: str = ""):
    """
    Once per trading day, ~1 hour before open (see market_phase()): reviews
    the prior trading day's buy/sell activity plus current equity/cash/
    positions, and gets one chance to queue a buy ahead of the open.
    """
    context = None
    news_context = None
    overall_reasoning = ""
    try:
        _cancel_stale_orders()
        context = _build_context()

        anomaly = _account_state_anomaly(context)
        if anomaly:
            print(anomaly)
            _log_run(market_open=False, context=context, overall_reasoning="", error=anomaly, news_context=None)
            _notify("Skipped pre-market review on bad account data", anomaly[:200])
            return

        stop_loss_decisions = _apply_stop_loss_backstop()
        if stop_loss_decisions:
            context = _build_context()

        daily_report = _build_daily_report()
        recap = daily_report["recap_text"]
        print(f"Pre-market review. Yesterday recap: {recap}")
        _log_daily_report(daily_report)

        news_context, news_age_minutes = _get_news_context()

        manual_framing = (
            f"\n\n## Manual context from Carter (injected for this run only)\n{extra_context}\n"
            if extra_context else ""
        )

        ai_response = _call_model(
            context, news_context,
            extra_framing=_PREMARKET_FRAMING + "\n" + recap + manual_framing,
            news_age_minutes=news_age_minutes,
        )
        overall_reasoning = ai_response.get("overall_reasoning", "")
        decisions = ai_response.get("decisions", [])

        held_long_symbols = {s for s, p in context["held_positions"].items() if p["side"] == "long"}
        decisions = _enforce_caps(
            decisions, context, ac.get_pending_buy_info(),
            ac.get_pending_short_info(held_long_symbols),
        )
        _execute(decisions)
        decisions = stop_loss_decisions + decisions

        try:
            post_context = _refresh_account_state()
        except Exception as e:
            print(f"Could not refresh post-trade account state ({e}); logging pre-trade snapshot instead.")
            post_context = context
        _log_positions(post_context)
        _log_open_orders()

        run_id = _log_run(market_open=False, context=post_context, overall_reasoning=overall_reasoning,
                           error=None, news_context=news_context)
        _log_decisions(run_id, decisions)

        print(f"Pre-market review complete. Reasoning: {overall_reasoning}")
        for d in decisions:
            print(f"  {d['symbol']}: {d['action']} -> {d.get('order_status')} | {d.get('reasoning', '')}")

        executed = [d for d in decisions if d.get("order_id")]
        if executed:
            summary = ", ".join(f"{d['action'].upper()} {_notify_size(d)} {d['symbol']}" for d in executed)
            _notify("queued a pre-market move", f"{summary} (will fill at/after the open)")

    except Exception as e:
        safe_msg = _safe_str(e)
        print(f"Pre-market review failed: {safe_msg}")
        _log_run(market_open=False, context=context, overall_reasoning=overall_reasoning,
                 error=safe_msg, news_context=news_context)
        _notify("Pre-market review failed", safe_msg[:200])
        raise


_OFFHOURS_CRYPTO_FRAMING = """

## This is an off-hours/weekend crypto-only decision run
Equity markets are closed right now, so only your crypto pairs (formatted
"BASE/USD") can actually execute this run — any buy/sell decision on a meme
stock is rejected in code, so don't spend a decision on one. Crypto trades
24/7 on Alpaca; this run exists specifically so you get a real, ongoing
decision cycle on it overnight and on weekends instead of only reacting
once your market-hours run picks back up.
"""


def run_crypto_afterhours(extra_context: str = ""):
    """
    Off-hours/weekend counterpart to run(): until now, the equity-market-
    hours run (run(), triggered by trade_eris.yml's Supabase-scheduled
    cron) was the only place any agent's crypto leg ever got a real trading
    decision, even though crypto trades 24/7 on Alpaca — nights, weekends,
    and holidays got nothing but the stop-loss disaster brake (see
    run_weekend_crypto_backstop below). This is the real thing: the full AI
    decision cycle, restricted in code to crypto-only symbols
    (_enforce_caps' restrict_to_crypto=True) since equity markets are
    actually closed and any equity order here would be premature.

    Only meaningful for an agent with at least one crypto symbol in its
    universe (currently only Eris) — a no-op otherwise, so this is safe to
    wire into main.py's dispatch for every agent rather than special-casing
    which ones call it.

    Invoked from main.py's "quiet" phase branch, which is in turn reached
    both by the regular Supabase-triggered dispatch (on the rare tick that
    lands just as the market closes/reopens) and by
    crypto_afterhours_trade.yml's own independent schedule — the latter is
    what actually guarantees this runs on a real cadence overnight and on
    weekends, since the Supabase cron is itself scoped to market hours.
    """
    if not any(ac.is_crypto(s) for s in config.AGENT["universe"]):
        print(f"{config.AGENT['label']} has no crypto in its universe — nothing to do off-hours.")
        return

    context = None
    news_context = None
    overall_reasoning = ""
    try:
        _cancel_stale_orders()
        context = _build_context()
        print(
            f"Off-hours crypto context built: {len(context['watchlist'])} watchlist symbols, "
            f"{len(context['held_positions'])} held."
        )

        anomaly = _account_state_anomaly(context)
        if anomaly:
            print(anomaly)
            _log_run(market_open=False, context=context, overall_reasoning="", error=anomaly, news_context=None)
            _notify("Skipped off-hours crypto run on bad account data", anomaly[:200])
            return

        stop_loss_decisions = _apply_stop_loss_backstop(crypto_only=True)
        if stop_loss_decisions:
            # Rebuild so the model reasons from the post-close state instead
            # of seeing a position the backstop just liquidated.
            context = _build_context()

        news_context, news_age_minutes = _get_news_context()

        manual_framing = (
            f"\n\n## Manual context from Carter (injected for this run only)\n{extra_context}\n"
            if extra_context else ""
        )

        ai_response = _call_model(
            context, news_context,
            extra_framing=_OFFHOURS_CRYPTO_FRAMING + manual_framing,
            news_age_minutes=news_age_minutes,
        )
        overall_reasoning = ai_response.get("overall_reasoning", "")
        decisions = ai_response.get("decisions", [])

        held_long_symbols = {s for s, p in context["held_positions"].items() if p["side"] == "long"}
        decisions = _enforce_caps(
            decisions, context, ac.get_pending_buy_info(),
            ac.get_pending_short_info(held_long_symbols),
            restrict_to_crypto=True,
        )
        _execute(decisions)
        decisions = stop_loss_decisions + decisions

        try:
            post_context = _refresh_account_state()
        except Exception as e:
            print(f"Could not refresh post-trade account state ({e}); logging pre-trade snapshot instead.")
            post_context = context
        _log_positions(post_context)
        _log_open_orders()

        run_id = _log_run(market_open=False, context=post_context, overall_reasoning=overall_reasoning,
                           error=None, news_context=news_context)
        _log_decisions(run_id, decisions)

        print(f"Off-hours crypto run complete. Reasoning: {overall_reasoning}")
        for d in decisions:
            print(f"  {d['symbol']}: {d['action']} -> {d.get('order_status')} | {d.get('reasoning', '')}")

        executed = [d for d in decisions if d.get("order_id")]
        if executed:
            summary = ", ".join(f"{d['action'].upper()} {_notify_size(d)} {d['symbol']}" for d in executed)
            _notify("made an off-hours crypto move", summary)

    except Exception as e:
        safe_msg = _safe_str(e)
        print(f"Off-hours crypto run failed: {safe_msg}")
        _log_run(market_open=False, context=context, overall_reasoning=overall_reasoning,
                 error=safe_msg, news_context=news_context)
        _notify("Off-hours crypto run failed", safe_msg[:200])
        raise


def run_weekend_crypto_backstop():
    """
    No-AI, crypto-only sweep of _apply_stop_loss_backstop(). Independent,
    faster-cadence (every 3h, see weekend_crypto_backstop.yml) safety net
    that sits alongside run_crypto_afterhours() above rather than
    replacing it: if a real off-hours decision cycle is ever delayed or
    fails outright (a bad Gemini/Alpaca API day, a workflow bug like the
    one this repo already hit once — see git history), a position that's
    blown through the loss cap still doesn't have to wait for the next
    successful decision run to get closed.

    Deliberately does not call the model or build the full decision
    context — this is purely the disaster brake, not a trading run.
    """
    closed = _apply_stop_loss_backstop(crypto_only=True)
    if not closed:
        print("Weekend crypto backstop: nothing past the loss cap.")
        return
    print(f"Weekend crypto backstop closed {len(closed)} position(s): "
          f"{', '.join(d['symbol'] for d in closed)}")
    try:
        run_id = _log_run(market_open=True, context=None, overall_reasoning="", error=None,
                           news_context=None)
        _log_decisions(run_id, closed)
    except Exception as e:
        print(f"Weekend crypto backstop: closed positions but failed to log the run ({_safe_str(e)}).")
