"""
Risk enforcement and position-context helpers: caps/sizing validation
(_enforce_caps), symbol normalization, the account-data-anomaly guard, the
daily loss breaker, and the per-position stop-loss backstop. This is the
code the model's judgment never overrides — see _enforce_caps' docstring.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

import config
import alpaca_client as ac
from util import _safe_str
from store import SUPABASE_URL, _supabase_headers, _notify
from sectors import sector_of

def _position_entry_dates(symbols) -> dict:
    """
    Best-effort entry timestamp per currently-held symbol: the most recent
    filled buy/short decision logged for that symbol. A later sell/cover
    would have closed the position, so "most recent buy/short" is the add
    that opened (or most recently topped up) what's still held — approximate
    for positions built from multiple buys, but good enough to show the
    model how long it's actually been sitting on something.

    Best-effort: any failure returns {} and callers should treat missing
    entries as "unknown," not zero.
    """
    if not symbols:
        return {}
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/trading_agent_decisions",
            headers=_supabase_headers(),
            params={
                "agent_id": f"eq.{config.AGENT_ID}",
                "symbol": f"in.({','.join(symbols)})",
                "action": "in.(buy,short)",
                "order_id": "not.is.null",
                "select": "symbol,created_at",
                "order": "created_at.desc",
                "limit": "500",
            },
            timeout=15,
        )
        resp.raise_for_status()
        entry_dates = {}
        for r in resp.json():
            entry_dates.setdefault(r["symbol"], r["created_at"])  # first (most recent) row wins
        return entry_dates
    except Exception as e:
        print(f"Could not fetch position entry dates ({e}); omitting days_held/MFE this run.")
        return {}


def _max_favorable_excursion_pct(symbol: str, side: str, avg_entry_price: float,
                                  entry_at: str | None, bars) -> float | None:
    """
    Best price seen since entry, expressed as the % move in the position's
    favorable direction (up for long, down for short) — how much of the move
    was actually available to take vs. what got realized. Approximate: only
    looks at the daily bars already fetched for the universe this run
    (config.LOOKBACK_DAYS + 5), so a position held longer than that window
    only reflects the visible tail of its life, not the true peak.

    Surfaced because the 2026-07-09 profitability review found winners being
    cut at ~+0.5% while gains mostly came from positions the model happened
    to still be holding — i.e. exits, not entries, are the leak. Seeing "this
    traded up 6% at one point" next to "you're up 0.5% now" makes that
    legible without a code-level rule forcing a minimum hold.
    """
    if not bars or not entry_at:
        return None
    try:
        entry_date = datetime.fromisoformat(entry_at.replace("Z", "+00:00")).date()
    except (ValueError, TypeError):
        return None
    since_entry = [b for b in bars if b.timestamp.date() >= entry_date]
    if not since_entry:
        return None
    if side == "long":
        best = max(b.high for b in since_entry)
        return round((best - avg_entry_price) / avg_entry_price * 100, 2)
    else:
        best = min(b.low for b in since_entry)
        return round((avg_entry_price - best) / avg_entry_price * 100, 2)


def _canonical_symbol(symbol: str) -> str:
    """
    Maps a model-returned symbol to its canonical universe form. The model
    routinely echoes crypto symbols without the slash ("YFIUSD", or a
    "BONK-USD" variant) — before positions were normalized (see
    alpaca_client._normalize_crypto_symbol) that's literally what it saw in
    held_positions, and it still shows up in its output from headlines and
    habit. _enforce_caps used to exact-match against the universe, so every
    one of those decisions was rejected as "symbol not in approved
    universe" — 90 rejected Eris decisions in three days, several of them
    repeated attempts to take a +19.7% profit. Matching with the separators
    stripped makes the decision mean what the model meant.
    """
    s = symbol.strip().upper()
    universe = config.AGENT["universe"]
    if s in universe:
        return s
    stripped = s.replace("/", "").replace("-", "")
    for u in universe:
        if u.replace("/", "") == stripped:
            return u
    return s


_FILL_PRICE_BUFFER = 1.02  # budget 2% above last_close for actual market fill price

def _enforce_caps(decisions: list, context: dict, pending_buy_info: dict,
                   pending_short_info: dict | None = None,
                   block_new_reason: str | None = None,
                   restrict_to_crypto: bool = False) -> list:
    """Returns the list of decisions actually allowed to execute, each
    annotated with an 'allowed' bool and a 'cap_note' if rejected/clipped.

    block_new_reason, when set (the daily loss circuit breaker — see
    _check_daily_loss_breaker), rejects every buy/short with that reason
    while leaving sells/covers/cancels untouched.

    restrict_to_crypto, when set (the off-hours/weekend run — see
    ai_agent.run_crypto_afterhours), rejects every action on a non-crypto
    symbol regardless of type (buy/sell/short/cover/cancel) since equity
    markets are actually closed at that point and any equity order would be
    premature. "hold" is exempt since it's not really an order."""
    held = context["held_positions"]
    held_symbols = set(held.keys())
    watchlist = context["watchlist"]
    equity = context["account"]["equity"]
    cash = context["account"]["cash"]
    allow_short = bool(config.AGENT.get("allow_short"))
    max_new = config.AGENT.get("max_new_buys_per_run")
    pending_short_info = pending_short_info or {}
    pending_buy_symbols = set(pending_buy_info.keys())
    pending_short_symbols = set(pending_short_info.keys())

    def reference_price(symbol):
        # Prefer the real-time last trade (Hermes' use_live_quotes path) over
        # yesterday's daily-bar close — closer to what an order will actually
        # fill at, which matters a lot more at a day-trading holding period.
        w = watchlist.get(symbol, {})
        return w.get("last_price") or w.get("last_close")

    pending_committed = 0.0
    for sym, qty in {**pending_buy_info, **pending_short_info}.items():
        p = held[sym]["current_price"] if sym in held else (reference_price(sym) or 0.0)
        pending_committed += qty * p

    # Hard cash/buying-power floor: running available capital after pending
    # orders. This is the strict ceiling we never let buys or shorts push
    # through. Shorts are approximated as consuming their full notional from
    # this same pool rather than modeling Alpaca's real Reg-T short margin
    # requirement (~150% of proceeds) — simpler, and more conservative than
    # not reserving anything; Alpaca itself still rejects anything that
    # actually exceeds real buying power.
    available_cash = max(0.0, cash - pending_committed)

    # Sector concentration cap: without this, min_cash_buffer_pct=0 and
    # max_open_positions=None everywhere means nothing stops an agent from
    # legally ending up fully concentrated in one correlated cluster (the
    # 2026-07-09 review's example: Hermes at 25% max sizing landing 100% in
    # four semiconductor stocks that all move together). Running total in
    # dollars per sector — held positions plus dollars already committed to
    # pending orders — checked against max_sector_concentration_pct * equity
    # before each new buy/short, then updated as decisions this run get
    # approved so a run can't blow past the cap by stacking several buys in
    # the same sector back to back. None/"Unclassified"-sector symbols and
    # agents with no max_sector_concentration_pct set are exempt.
    sector_cap_pct = config.AGENT.get("max_sector_concentration_pct")
    sector_exposure: dict[str, float] = {}
    if sector_cap_pct:
        for sym, pos in held.items():
            sec = sector_of(sym)
            if sec is not None:
                sector_exposure[sec] = sector_exposure.get(sec, 0.0) + abs(pos["market_value"])
        for sym, qty in {**pending_buy_info, **pending_short_info}.items():
            sec = sector_of(sym)
            if sec is None:
                continue
            p = held[sym]["current_price"] if sym in held else (reference_price(sym) or 0.0)
            sector_exposure[sec] = sector_exposure.get(sec, 0.0) + qty * p

    open_count = len(held_symbols)
    new_positions = 0
    new_position_symbols_this_run = set()
    approved = []

    open_orders_by_symbol = {}
    for o in context.get("open_orders", []):
        open_orders_by_symbol.setdefault(o["symbol"], []).append(o)

    for d in decisions:
        symbol = _canonical_symbol(d.get("symbol", ""))
        action = d.get("action", "").lower()
        order_type = d.get("order_type", "market").lower()
        limit_price = d.get("limit_price")
        d["symbol"] = symbol
        d["action"] = action
        d["order_type"] = order_type

        if symbol not in config.AGENT["universe"]:
            d["allowed"] = False
            d["cap_note"] = "symbol not in approved universe"

        elif restrict_to_crypto and action != "hold" and not ac.is_crypto(symbol):
            d["allowed"] = False
            d["cap_note"] = "off-hours run — only crypto symbols execute here (equity markets are closed)"

        elif action == "sell":
            if symbol not in held_symbols or held[symbol]["side"] != "long":
                d["allowed"] = False
                d["cap_note"] = "no long position held to sell"
            else:
                pos = held[symbol]
                held_qty = pos["qty"]
                # Alpaca equity limit orders require whole-share qty (crypto
                # limit orders don't have this restriction — fractional qty
                # is normal there). Positions bought notional (Hermes/Eris'
                # use_notional path) can hold fractional shares — truncating
                # that to int() for an equity limit sell would silently leave
                # a fractional "dust" remainder open forever, breaking the
                # output-format promise that "a limit sell closes the full
                # position." Reject instead so the position stays intact and
                # a market sell (which does close it in full, fractional or
                # not) is the only way to exit it.
                if order_type == "limit" and not ac.is_crypto(symbol) and held_qty != int(held_qty):
                    d["allowed"] = False
                    d["cap_note"] = (
                        f"limit sell not allowed on a fractional position ({held_qty} shares) — "
                        "Alpaca limit orders require whole shares; use a market sell to close it"
                    )
                else:
                    d["allowed"] = True
                    d["qty"] = held_qty if ac.is_crypto(symbol) else int(held_qty)  # needed for limit sell execution
                    d["exit_price"] = pos["current_price"]
                    d["realized_pnl_pct"] = pos["unrealized_pl_pct"]
                    if order_type == "limit":
                        if not isinstance(limit_price, (int, float)) or limit_price <= 0:
                            d["allowed"] = False
                            d["cap_note"] = "limit sell requires a valid limit_price"
                        elif limit_price <= pos["current_price"]:
                            # Warn but still allow — agent might intend a stop-loss
                            print(
                                f"Note: limit sell for {symbol} at {limit_price} is at or "
                                f"below current price {pos['current_price']} — will fill immediately or act as a floor."
                            )

        elif action == "cover":
            if not allow_short:
                d["allowed"] = False
                d["cap_note"] = "short selling not enabled for this agent"
            elif symbol not in held_symbols or held[symbol]["side"] != "short":
                d["allowed"] = False
                d["cap_note"] = "no short position held to cover"
            else:
                pos = held[symbol]
                held_qty = abs(pos["qty"])
                if order_type == "limit" and held_qty != int(held_qty):
                    d["allowed"] = False
                    d["cap_note"] = "limit cover not allowed on a fractional short qty — use a market cover"
                else:
                    d["allowed"] = True
                    d["qty"] = int(held_qty)
                    d["exit_price"] = pos["current_price"]
                    d["realized_pnl_pct"] = pos["unrealized_pl_pct"]
                    if order_type == "limit":
                        if not isinstance(limit_price, (int, float)) or limit_price <= 0:
                            d["allowed"] = False
                            d["cap_note"] = "limit cover requires a valid limit_price"
                        elif limit_price >= pos["current_price"]:
                            # Warn but still allow — agent might intend a stop-loss
                            print(
                                f"Note: limit cover for {symbol} at {limit_price} is at or "
                                f"above current price {pos['current_price']} — will fill immediately or act as a ceiling."
                            )

        elif action in ("buy", "short"):
            is_short = action == "short"
            is_crypto_symbol = ac.is_crypto(symbol)
            if block_new_reason:
                d["allowed"] = False
                d["cap_note"] = block_new_reason
            elif is_short and not allow_short:
                d["allowed"] = False
                d["cap_note"] = "short selling not enabled for this agent"
            elif is_short and is_crypto_symbol:
                d["allowed"] = False
                d["cap_note"] = "crypto is spot-only on Alpaca — shorting not supported for this symbol"
            elif available_cash <= 0:
                d["allowed"] = False
                d["cap_note"] = "no available cash/buying power remaining after pending orders"
            elif symbol in held_symbols:
                existing_side = held[symbol]["side"]
                d["allowed"] = False
                if not is_short and existing_side == "short":
                    d["cap_note"] = "already holding a short position in this symbol — use 'cover' to close it, not 'buy'"
                elif is_short and existing_side == "long":
                    d["cap_note"] = "already holding a long position in this symbol — use 'sell' to close it, not 'short'"
                else:
                    d["cap_note"] = f"already holding a {existing_side} position, ignoring duplicate {action}"
            elif symbol in pending_buy_symbols or symbol in pending_short_symbols:
                d["allowed"] = False
                d["cap_note"] = "an order for this symbol is already pending/unfilled, ignoring duplicate"
            elif symbol in new_position_symbols_this_run:
                d["allowed"] = False
                d["cap_note"] = "duplicate order for this symbol already approved this run, ignoring"
            elif config.AGENT["max_open_positions"] is not None and open_count >= config.AGENT["max_open_positions"]:
                d["allowed"] = False
                d["cap_note"] = "max open positions reached"
            elif max_new is not None and new_positions >= max_new:
                d["allowed"] = False
                d["cap_note"] = "max new positions per run reached"
            else:
                price = (limit_price if order_type == "limit" and isinstance(limit_price, (int, float)) and limit_price > 0
                         else reference_price(symbol))
                if not price:
                    d["allowed"] = False
                    d["cap_note"] = "no price data available for this symbol this run"
                elif order_type == "limit" and (not isinstance(limit_price, (int, float)) or limit_price <= 0):
                    d["allowed"] = False
                    d["cap_note"] = f"limit {action} requires a valid limit_price"
                else:
                    min_pct = config.AGENT["position_size_pct_min"]
                    max_pct = config.AGENT["position_size_pct_max"]
                    requested_pct = d.get("size_pct")
                    if isinstance(requested_pct, (int, float)) and requested_pct > 0:
                        size_pct = max(min_pct, min(max_pct, requested_pct))
                    else:
                        size_pct = (min_pct + max_pct) / 2
                    d["size_pct_used"] = round(size_pct, 4)
                    target_notional = equity * size_pct

                    sector = sector_of(symbol)
                    sector_room_exceeded = (
                        sector_cap_pct and sector is not None
                        and sector_exposure.get(sector, 0.0) + target_notional > sector_cap_pct * equity
                    )
                    if sector_room_exceeded:
                        room = max(0.0, sector_cap_pct * equity - sector_exposure.get(sector, 0.0))
                        d["allowed"] = False
                        d["cap_note"] = (
                            f"sector concentration cap reached for {sector} "
                            f"(cap {sector_cap_pct * 100:.0f}% of equity, ~${room:,.0f} of room left there)"
                        )
                    else:
                        # Notional/fractional orders only exist for market buys —
                        # Alpaca has no fractional/notional short selling at all.
                        use_notional = (not is_short) and config.AGENT.get("use_notional", False) and order_type == "market"

                        if use_notional:
                            # Notional (fractional) buy: send Alpaca a dollar amount
                            # and let it fill the exact fractional qty. No integer
                            # rounding or fill-price buffer — Alpaca handles it.
                            notional_to_spend = round(min(target_notional, available_cash), 2)
                            if notional_to_spend < 1.0:
                                d["allowed"] = False
                                d["cap_note"] = "insufficient cash for $1 minimum notional order"
                            else:
                                d["notional_order"] = notional_to_spend
                                # Estimated, for logging only — 6dp for crypto so a
                                # sub-cent memecoin price (e.g. SHIB ~$0.00002)
                                # doesn't round to a meaningless $0.00.
                                d["entry_price"] = round(price, 6 if is_crypto_symbol else 2)
                                d["allowed"] = True
                                open_count += 1
                                new_positions += 1
                                new_position_symbols_this_run.add(symbol)
                                available_cash -= notional_to_spend
                                if sector is not None:
                                    sector_exposure[sector] = sector_exposure.get(sector, 0.0) + notional_to_spend
                        else:
                            # Qty-based buy/short (Plutus, Helios, Hermes limit
                            # buys, and all shorts regardless of order_type).
                            # Equities truncate to whole shares; crypto keeps
                            # fractional precision (Alpaca has no whole-unit
                            # requirement there, and a whole BTC/ETH would be
                            # far beyond any sane position size at this equity).
                            fill_buffer = 1.0 if order_type == "limit" else _FILL_PRICE_BUFFER
                            notional = min(target_notional, available_cash)
                            raw_qty = notional / (price * fill_buffer)
                            qty = round(raw_qty, 6) if is_crypto_symbol else int(raw_qty)
                            unit = "a minimal crypto position" if is_crypto_symbol else "even 1 share"

                            if qty <= 0:
                                d["allowed"] = False
                                d["cap_note"] = f"insufficient cash/buying power for {unit} at the sized notional"
                            else:
                                committed = qty * price * fill_buffer
                                if committed > available_cash:
                                    qty = available_cash / (price * fill_buffer)
                                    qty = round(qty, 6) if is_crypto_symbol else int(qty)
                                if qty <= 0:
                                    d["allowed"] = False
                                    d["cap_note"] = f"insufficient cash/buying power for {unit} (hard floor enforced)"
                                else:
                                    d["qty"] = qty
                                    d["entry_price"] = round(price, 6) if is_crypto_symbol else price
                                    d["allowed"] = True
                                    open_count += 1
                                    new_positions += 1
                                    new_position_symbols_this_run.add(symbol)
                                    committed_final = qty * price * fill_buffer
                                    available_cash -= committed_final
                                    if sector is not None:
                                        sector_exposure[sector] = sector_exposure.get(sector, 0.0) + committed_final

        elif action == "cancel":
            if symbol in open_orders_by_symbol:
                d["allowed"] = True
            else:
                d["allowed"] = False
                d["cap_note"] = "no open order for this symbol to cancel"

        elif action == "hold":
            d["allowed"] = False
            d["cap_note"] = "hold (no action taken)"
        else:
            d["allowed"] = False
            d["cap_note"] = f"unrecognized action '{action}'"

        approved.append(d)

    return approved


def _cancel_stale_orders():
    """Best-effort cleanup of orders that never resolved (see
    alpaca_client.cancel_stale_open_orders) — must never block a run."""
    try:
        cancelled = ac.cancel_stale_open_orders(
            max_age_hours=config.AGENT.get("stale_order_max_age_hours", 20.0)
        )
        if cancelled:
            print(f"Cancelled {len(cancelled)} stale unfilled order(s): {', '.join(cancelled)}")
            _notify(
                "Cleared stale orders",
                f"{len(cancelled)} order(s) never filled and were cancelled so they stop tying up cash: "
                + ", ".join(cancelled),
            )
    except Exception as e:
        print(f"Could not check for stale orders ({e}) — non-fatal.")


def _account_state_anomaly(context: dict) -> str | None:
    """
    Returns a description of the anomaly if the account state Alpaca just
    returned is too inconsistent with this agent's own recent history to
    trade on, else None.

    On 2026-07-07, Alpaca's paper API spent ~5 hours returning equity=cash
    and zero positions for every account (Plutus "lost" 90% of its equity,
    Helios 79%, positions simply gone). The agents were fed that state as
    fact: Hermes opened new shorts into it, Eris issued sells for positions
    the API claimed didn't exist. A decision made on phantom data isn't
    judgment, so: if equity collapsed vs. the last logged run AND all
    positions simultaneously vanished — a combination a real market move
    can't produce in 15 minutes, since closing positions converts them to
    cash rather than destroying equity — skip the decision run and say why.
    Both conditions are required; either alone is legitimate (a real crash,
    or the agent genuinely selling everything).

    Best-effort: if the history lookup fails, trade normally rather than
    letting a Supabase blip halt the agent.
    """
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/trading_agent_runs",
            headers=_supabase_headers(),
            params={
                "agent_id": f"eq.{config.AGENT_ID}",
                "account_equity": "not.is.null",
                "error": "is.null",
                "select": "run_at,account_equity,num_open_positions",
                "order": "run_at.desc",
                "limit": "1",
            },
            timeout=15,
        )
        resp.raise_for_status()
        rows = resp.json()
        if not rows:
            return None
        last = rows[0]
        last_at = datetime.fromisoformat(last["run_at"].replace("Z", "+00:00"))
        if (datetime.now(timezone.utc) - last_at) > timedelta(hours=24):
            return None  # too old to compare against meaningfully
        last_equity = float(last["account_equity"] or 0)
        last_positions = int(last["num_open_positions"] or 0)
        equity = context["account"]["equity"]
        if (
            last_equity > 0
            and last_positions > 0
            and len(context["held_positions"]) == 0
            and equity < last_equity * 0.8
        ):
            return (
                f"account data anomaly: equity ${equity:,.2f} is down "
                f">{(1 - equity / last_equity) * 100:.0f}% from ${last_equity:,.2f} at the last run "
                f"({last_at.isoformat()}) while all {last_positions} open positions "
                "simultaneously vanished — this matches a broker data outage, not a market move. "
                "Skipping the decision run rather than trading on phantom state."
            )
        return None
    except Exception as e:
        print(f"Could not run account-state sanity check ({e}); proceeding.")
        return None


def _check_daily_loss_breaker(current_equity: float) -> tuple[str | None, bool]:
    """
    Account-level daily loss circuit breaker (see max_daily_loss_pct in
    config.py). Returns (reason, was_already_tripped): reason is a
    human-readable string when equity has fallen more than the cap below
    today's baseline — the first successfully-logged equity reading of the
    current US/Eastern day — or None when trading can proceed normally.
    was_already_tripped is True if some earlier run today had already
    breached the cap, so the trip notification only fires once per day
    instead of on every 15-minute run for the rest of the session.

    The baseline deliberately excludes errored runs: the July 7 Alpaca
    glitch logged phantom equity=cash readings with the error field set,
    and a phantom baseline would make the breaker fire (or fail to fire)
    on data the anomaly guard already rejected.

    Distinct from _account_state_anomaly above: that guard catches *broken
    data* (equity collapsed AND positions vanished — an API glitch); this
    one catches *real losses* accumulating across a genuinely bad day.

    Best-effort like the other Supabase-backed guards: if the query fails,
    the breaker stays open (no lockout) rather than blocking trading on a
    logging outage.
    """
    cap = config.AGENT.get("max_daily_loss_pct")
    if not cap or not current_equity:
        return None, False
    try:
        day_start_utc = (
            datetime.now(ZoneInfo("America/New_York"))
            .replace(hour=0, minute=0, second=0, microsecond=0)
            .astimezone(timezone.utc)
        )
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/trading_agent_runs",
            headers=_supabase_headers(),
            params={
                "agent_id": f"eq.{config.AGENT_ID}",
                "run_at": f"gte.{day_start_utc.isoformat()}",
                "error": "is.null",
                "account_equity": "not.is.null",
                "select": "account_equity",
                "order": "run_at.asc",
                "limit": "500",
            },
            timeout=15,
        )
        resp.raise_for_status()
        equities = [float(r["account_equity"]) for r in resp.json()]
        if not equities or equities[0] <= 0:
            return None, False  # first run of the day — nothing to measure against yet

        baseline = equities[0]
        drawdown_pct = (current_equity - baseline) / baseline * 100
        if drawdown_pct > -cap * 100:
            return None, False

        already = any((e - baseline) / baseline * 100 <= -cap * 100 for e in equities[1:])
        reason = (
            f"daily loss circuit breaker: equity ${current_equity:,.2f} is "
            f"{abs(drawdown_pct):.1f}% below today's baseline ${baseline:,.2f} "
            f"(cap {cap * 100:.0f}%) — no new buys/shorts for the rest of the day"
        )
        return reason, already
    except Exception as e:
        print(f"Could not check daily loss circuit breaker ({e}); not enforcing it this run.")
        return None, False


def _apply_stop_loss_backstop(crypto_only: bool = False) -> list[dict]:
    """
    Closes, at market, any held position whose unrealized loss exceeds this
    agent's max_position_loss_pct, and returns synthetic decision dicts for
    the run log. Runs before the model is called (and before the context is
    built, so the model sees the post-close state).

    This is a disaster brake, not a trading rule — thresholds are set per
    agent (config.py) wide enough that the model's own exit judgment is
    still doing the real work. It exists because the 2026-07-09
    profitability review found the opposite asymmetry of a healthy book:
    winners realized at ~+0.5% while losers were held, and (worse) exit
    decisions failing on execution bugs while positions kept sliding. A
    position this far underwater with no run having closed it means
    judgment already didn't happen — code takes over.

    crypto_only restricts the sweep to crypto positions (see
    run_weekend_crypto_backstop) — equity positions can't move or be closed
    outside market hours anyway, so a weekend sweep only needs to look at
    the crypto leg.
    """
    max_loss_pct = config.AGENT.get("max_position_loss_pct")
    if not max_loss_pct:
        return []
    closed = []
    try:
        positions = ac.get_open_positions()
        for symbol, pos in positions.items():
            if crypto_only and not ac.is_crypto(symbol):
                continue
            pl_pct = float(pos.unrealized_plpc) * 100
            if pl_pct > -max_loss_pct * 100:
                continue
            side = "short" if float(pos.qty) < 0 else "long"
            d = {
                "symbol": symbol,
                "action": "cover" if side == "short" else "sell",
                "order_type": "market",
                "confidence": None,
                "reasoning": (
                    f"Code-enforced stop-loss backstop: position is {pl_pct:.1f}% underwater, "
                    f"past the {max_loss_pct * 100:.0f}% max-loss cap for this agent. "
                    "Closed at market before the decision run."
                ),
                "exit_price": round(float(pos.current_price), 6 if ac.is_crypto(symbol) else 2),
                "realized_pnl_pct": round(pl_pct, 2),
                "qty": abs(float(pos.qty)),
            }
            try:
                ac.cancel_open_orders_for_symbol(symbol)
                result = ac.close_position(symbol)
                d["order_id"] = str(result.id) if hasattr(result, "id") else None
                d["order_status"] = str(getattr(result, "status", "submitted"))
                print(f"Stop-loss backstop closed {symbol} at {pl_pct:.1f}%.")
                _notify(
                    "stop-loss backstop hit",
                    f"{symbol} was {pl_pct:.1f}% underwater (cap {max_loss_pct * 100:.0f}%) — closed at market.",
                )
            except Exception as e:
                d["order_id"] = None
                d["order_status"] = f"error: {_safe_str(e)}"
                print(f"Stop-loss backstop failed to close {symbol}: {_safe_str(e)}")
            closed.append(d)
    except Exception as e:
        print(f"Could not run stop-loss backstop ({e}) — non-fatal.")
    return closed
