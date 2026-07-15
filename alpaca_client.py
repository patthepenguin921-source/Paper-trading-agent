"""
Thin wrapper around Alpaca's PAPER trading and market-data APIs.

Trades both equities/ETFs and crypto:
- TradingClient is constructed with paper=True, which pins it to Alpaca's
  paper-trading base URL. No code path here can place a live order.
- Crypto symbols use Alpaca's "BASE/QUOTE" pair format (e.g. "BTC/USD") —
  is_crypto() below uses the presence of "/" as the sole marker to route a
  symbol to the crypto data client / order rules instead of the equity
  ones. No agent is required to trade crypto; config.py's universe lists
  simply do or don't contain any "/"-formatted symbols.
- Crypto is spot-only on Alpaca (no margin, no shorting) — callers (see
  ai_agent._enforce_caps) are expected to reject short/cover decisions on
  crypto symbols themselves; this module doesn't second-guess an order it's
  asked to submit.
"""
import os
from datetime import datetime, timedelta, timezone

import config

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus, OrderType
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.historical.crypto import CryptoHistoricalDataClient
from alpaca.data.historical.screener import ScreenerClient
from alpaca.data.requests import (
    StockBarsRequest, StockLatestTradeRequest, StockLatestQuoteRequest,
    CryptoBarsRequest, CryptoLatestTradeRequest, CryptoLatestQuoteRequest,
    MostActivesRequest, MarketMoversRequest,
)
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed, MostActivesBy, MarketType

API_KEY = os.environ["ALPACA_API_KEY"]
SECRET_KEY = os.environ["ALPACA_SECRET_KEY"]

# paper=True forces the paper-trading base URL (paper-api.alpaca.markets).
trading_client = TradingClient(API_KEY, SECRET_KEY, paper=True)
data_client = StockHistoricalDataClient(API_KEY, SECRET_KEY)
# Crypto market data on Alpaca doesn't require auth, but passing the same
# keys costs nothing and keeps request attribution consistent with the
# equity client above.
crypto_data_client = CryptoHistoricalDataClient(API_KEY, SECRET_KEY)
screener_client = ScreenerClient(API_KEY, SECRET_KEY)


def is_crypto(symbol: str) -> bool:
    """Alpaca crypto pairs are always "BASE/QUOTE" (e.g. "BTC/USD", "DOGE/USD");
    no equity/ETF ticker ever contains a "/", so this is a reliable, cheap
    way to route a symbol without needing a separate asset-class field
    threaded through every function that takes a symbol list."""
    return "/" in symbol


def fetch_news_headlines(symbols: list[str], limit: int = 18) -> list[dict]:
    """
    Real headlines from Alpaca's News API (Benzinga-sourced) for the given
    symbols, most recent first. Uses the same API keys as trading. Returns a
    list of {headline, source, symbols, created_at} dicts; empty list on any
    failure — news is a nice-to-have, never a reason to stop a run.
    """
    import requests
    try:
        resp = requests.get(
            "https://data.alpaca.markets/v1beta1/news",
            headers={
                "APCA-API-KEY-ID": API_KEY,
                "APCA-API-SECRET-KEY": SECRET_KEY,
            },
            params={
                "symbols": ",".join(symbols),
                "limit": limit,
                "include_content": "false",
                "exclude_contentless": "true",
            },
            timeout=15,
        )
        resp.raise_for_status()
        items = resp.json().get("news", [])
        return [
            {
                "headline": n.get("headline", ""),
                "source": n.get("source", ""),
                "symbols": n.get("symbols", []),
                "created_at": n.get("created_at", ""),
            }
            for n in items
            if n.get("headline")
        ]
    except Exception as e:
        print(f"Alpaca news fetch failed ({e}) — continuing without headlines.")
        return []


def is_market_open() -> bool:
    clock = trading_client.get_clock()
    return clock.is_open


def minutes_until_next_open() -> float:
    """
    How many minutes from right now until the next real trading session
    opens. Large (multi-hour/day) on a weekend or holiday morning even if
    the wall-clock time looks like a normal pre-market hour — used to tell
    "today is genuinely about to open" apart from "today just isn't a
    trading day" before running anything tied to a specific clock time.
    """
    clock = trading_client.get_clock()
    if clock.is_open:
        return 0.0
    return (clock.next_open - clock.timestamp).total_seconds() / 60


def get_account():
    return trading_client.get_account()


def _normalize_crypto_symbol(symbol: str) -> str:
    """
    Alpaca's Positions endpoint drops the "/" separator from crypto symbols
    — e.g. a position opened as "BONK/USD" comes back from
    get_all_positions() as "BONKUSD" — while every other Alpaca API this
    codebase uses (order submission, market data) and config.py's own
    universe lists all use the slashed "BASE/QUOTE" form. Left
    unnormalized, a held crypto position's dict key never matches its
    universe entry — silently blocking every sell/cover decision on it
    (rejected in ai_agent._enforce_caps as "symbol not in approved
    universe") — and is_crypto() (which keys off the "/") misclassifies it
    as an equity, corrupting its displayed price to 2dp instead of 6dp
    (a sub-cent memecoin rounds straight to $0.00).

    Reinserts the "/" by matching against this agent's own universe — the
    only place the canonical slashed form is known. No-op for equities
    (never contain a "/" either way) and for anything already slashed.
    """
    if "/" in symbol:
        return symbol
    for u in config.AGENT["universe"]:
        if "/" in u and u.replace("/", "") == symbol:
            return u
    return symbol


def get_open_positions() -> dict:
    """Returns {symbol: position} for all currently held positions, with
    crypto symbols normalized back to their canonical "BASE/QUOTE" form —
    see _normalize_crypto_symbol."""
    return {_normalize_crypto_symbol(p.symbol): p for p in trading_client.get_all_positions()}


def get_pending_buy_info() -> dict[str, float]:
    """
    Returns {symbol: unfilled_qty} for open buy orders.

    Used in two ways by _enforce_caps:
    1. Block duplicate buys for the same symbol (same as the old
       get_pending_buy_symbols() check).
    2. Estimate how much cash is already committed to those pending orders
       so that a new run doesn't double-spend the same dollars — the most
       common cause of negative cash is a pre-market run queuing orders and
       a market-open run seeing the same account.cash (fills haven't landed
       yet) and committing it again to different symbols.
    """
    open_orders = trading_client.get_orders(filter=GetOrdersRequest(status=QueryOrderStatus.OPEN))
    result = {}
    for o in open_orders:
        if o.side != OrderSide.BUY or not o.qty:
            continue
        unfilled = float(o.qty) - float(o.filled_qty or 0)
        if unfilled > 0:
            result[o.symbol] = unfilled
    return result


def get_pending_buy_symbols() -> set:
    return set(get_pending_buy_info().keys())


def get_pending_short_info(held_long_symbols: set) -> dict[str, float]:
    """
    Returns {symbol: unfilled_qty} for open SELL orders that are opening or
    adding to a short position — i.e. the symbol isn't a currently-held long
    position, so this SELL can't be closing one. Mirrors get_pending_buy_info():
    used to block duplicate short orders for the same symbol across runs and
    to estimate how much buying power is already committed to unfilled shorts.
    """
    open_orders = trading_client.get_orders(filter=GetOrdersRequest(status=QueryOrderStatus.OPEN))
    result = {}
    for o in open_orders:
        if o.side != OrderSide.SELL or not o.qty or o.symbol in held_long_symbols:
            continue
        unfilled = float(o.qty) - float(o.filled_qty or 0)
        if unfilled > 0:
            result[o.symbol] = result.get(o.symbol, 0.0) + unfilled
    return result


def get_open_orders_summary() -> list[dict]:
    """
    All currently open (unfilled) orders in a compact form suitable for the
    decision prompt: the agent's instructions have always told it to track
    and cancel/replace its own GTC limit orders, but until this existed the
    context never actually showed them — the model was managing blind, and
    the run log filled up with "an order for this symbol is already
    pending/unfilled" dead ends. Crypto symbols are normalized back to the
    canonical slashed form so they match the universe and held positions.
    """
    open_orders = trading_client.get_orders(filter=GetOrdersRequest(status=QueryOrderStatus.OPEN))
    now = datetime.now(timezone.utc)
    result = []
    for o in open_orders:
        symbol = _normalize_crypto_symbol(o.symbol)
        entry = {
            "symbol": symbol,
            "side": str(o.side).rsplit(".", 1)[-1].lower(),
            "order_type": str(o.type).rsplit(".", 1)[-1].lower() if o.type else None,
            "qty": float(o.qty) if o.qty else None,
            "notional": float(o.notional) if getattr(o, "notional", None) else None,
            "limit_price": float(o.limit_price) if getattr(o, "limit_price", None) else None,
            "age_minutes": round((now - o.submitted_at).total_seconds() / 60, 1) if o.submitted_at else None,
        }
        result.append(entry)
    return result


def cancel_open_orders_for_symbol(symbol: str) -> int:
    """
    Cancels every open order for one symbol and returns how many were
    cancelled. Two callers:
    - _execute, before submitting a sell/cover: shares reserved by a
      pending GTC limit exit make Alpaca reject any new exit order with
      code 40310000 ("held_for_orders") — the single most common execution
      error in the log (21 of Hermes' 41 covers failed this way). Freeing
      the shares first makes an exit decision actually executable.
    - The "cancel" decision action, which lets the model clear an order
      it no longer believes in instead of dead-ending on the
      duplicate-order guard every run until the stale-order sweep fires.

    Symbols are compared with the "/" stripped from both sides because
    Alpaca's orders endpoint, like its positions endpoint, doesn't reliably
    use the slashed crypto form this codebase treats as canonical.
    """
    target = symbol.replace("/", "")
    open_orders = trading_client.get_orders(filter=GetOrdersRequest(status=QueryOrderStatus.OPEN))
    cancelled = 0
    for o in open_orders:
        if o.symbol.replace("/", "") != target:
            continue
        try:
            trading_client.cancel_order_by_id(o.id)
            cancelled += 1
        except Exception as e:
            print(f"Could not cancel open order {o.id} ({o.symbol}): {e}")
    return cancelled


def cancel_stale_open_orders(max_age_hours: float = 20.0) -> list[str]:
    """
    Cancels open (unfilled) orders older than max_age_hours and returns the
    symbols cancelled. Every order this codebase submits is either DAY
    (should resolve — fill or expire — by the end of its own session) or
    GTC limit (meant to be tracked/replaced by the agent, not abandoned).
    In practice, orders have been observed sitting at ACCEPTED for days
    without filling or auto-expiring (see the manual Check Positions /
    Cancel Orders workflows this was previously handled through by hand).

    Left alone, a stale order permanently counts against
    get_pending_buy_info()'s cash-commitment estimate in _enforce_caps,
    silently shrinking the cash every future run thinks it has available —
    real capital taken out of play with no order actually working and no
    code path that ever puts it back. Called at the top of every run so
    this self-heals automatically instead of requiring the manual
    check_positions.py / cancel_orders.py scripts.
    """
    open_orders = trading_client.get_orders(filter=GetOrdersRequest(status=QueryOrderStatus.OPEN))
    now = datetime.now(timezone.utc)
    cancelled = []
    for o in open_orders:
        if not o.submitted_at:
            continue
        age_hours = (now - o.submitted_at).total_seconds() / 3600
        if age_hours < max_age_hours:
            continue
        try:
            trading_client.cancel_order_by_id(o.id)
            cancelled.append(f"{o.symbol} ({str(o.side).rsplit('.', 1)[-1]}, {age_hours:.0f}h old)")
        except Exception as e:
            print(f"Could not cancel stale order {o.id} ({o.symbol}): {e}")
    return cancelled


def get_recent_bars(symbols: list[str], lookback_days: int = 60) -> dict:
    """
    Daily bars for a list of symbols — equities/ETFs, crypto pairs, or a mix
    (see is_crypto()). Splits the list and calls each asset class's own data
    client/endpoint, then merges the results into one {symbol: bars} dict so
    callers (ai_agent._build_context) don't need to know or care which
    symbols were which.

    Uses an explicit start/end date range for the equity leg. Confirmed via
    direct testing that Alpaca's bars endpoint returns nothing at all for
    multi-symbol requests when only `limit` is given (regardless of feed) —
    a date range is required to actually get data back. The crypto leg uses
    the same date range for consistency, though CryptoBarsRequest has no
    `feed` concept (crypto has one consolidated tape, not SIP/IEX).

    Explicitly requests the SIP feed for equities (full consolidated tape
    across all US exchanges) rather than the IEX-only default. This is free
    on the Basic plan as long as the data is more than 15 minutes old, which
    daily bars always are by definition.
    """
    stock_symbols = [s for s in symbols if not is_crypto(s)]
    crypto_symbols = [s for s in symbols if is_crypto(s)]

    end = datetime.now(timezone.utc) - timedelta(days=1)
    start = end - timedelta(days=lookback_days * 2)  # generous buffer for weekends/holidays

    result = {}
    if stock_symbols:
        request = StockBarsRequest(
            symbol_or_symbols=stock_symbols,
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
            feed=DataFeed.SIP,
        )
        result.update(data_client.get_stock_bars(request).data)
    if crypto_symbols:
        request = CryptoBarsRequest(
            symbol_or_symbols=crypto_symbols,
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
        )
        result.update(crypto_data_client.get_crypto_bars(request).data)
    return result


def get_market_screen(top_n: int = 40) -> list[str]:
    """
    Samples today's most-active-by-volume and biggest-moving US equities
    market-wide via Alpaca's screener endpoints — a couple of cheap, single-
    shot calls rather than pulling bars for every listed symbol, so an
    agent's watchlist isn't limited to its hand-picked core list (see
    config.py's *_UNIVERSE lists) and actually samples the whole market each
    run. Movers are included alongside most-actives because a low-float
    stock can be the day's biggest mover on modest volume and never crack a
    volume-ranked list, and vice versa.

    Best-effort: returns [] on any failure (rate limit, endpoint hiccup) so
    a screener outage degrades an agent back to its static core universe
    for that run rather than crashing it — same philosophy as
    _missed_opportunities and the other best-effort blocks in this
    codebase.
    """
    try:
        actives = screener_client.get_most_actives(
            MostActivesRequest(top=top_n, by=MostActivesBy.VOLUME)
        )
        movers = screener_client.get_market_movers(
            MarketMoversRequest(top=max(top_n // 4, 5), market_type=MarketType.STOCKS)
        )
        symbols = {a.symbol for a in actives.most_actives}
        symbols.update(g.symbol for g in movers.gainers)
        symbols.update(l.symbol for l in movers.losers)
        return sorted(symbols)
    except Exception as e:
        print(f"Could not fetch market screen ({e}), falling back to each agent's static core universe only.")
        return []


def get_latest_prices(symbols: list[str]) -> dict[str, dict]:
    """
    Real-time last trade + bid/ask for the given symbols (equity, crypto, or
    a mix — see is_crypto()), keyed by symbol. get_recent_bars() intentionally
    stops at yesterday's close (see its docstring), which is fine for
    SMA/RSI/trend context but leaves a day trader unable to see today's
    actual move or set a sane limit price. This fills that gap.

    Equities use the IEX feed (real-time on the free tier — SIP real-time
    requires a paid subscription; SIP is only used above for daily bars,
    which are always >15min old and free either way). Crypto has no
    feed/subscription distinction — one consolidated tape, always real-time.

    Best-effort: returns {} for a leg that fails entirely, and skips symbols
    individual endpoints didn't return data for — stale/missing intraday
    quotes should never block a run that can still reason from yesterday's
    close.
    """
    stock_symbols = [s for s in symbols if not is_crypto(s)]
    crypto_symbols = [s for s in symbols if is_crypto(s)]

    trades, quotes = {}, {}
    if stock_symbols:
        try:
            trades.update(data_client.get_stock_latest_trade(
                StockLatestTradeRequest(symbol_or_symbols=stock_symbols, feed=DataFeed.IEX)
            ))
            quotes.update(data_client.get_stock_latest_quote(
                StockLatestQuoteRequest(symbol_or_symbols=stock_symbols, feed=DataFeed.IEX)
            ))
        except Exception as e:
            print(f"Could not fetch latest stock trades/quotes ({e}) — continuing without them.")
    if crypto_symbols:
        try:
            trades.update(crypto_data_client.get_crypto_latest_trade(
                CryptoLatestTradeRequest(symbol_or_symbols=crypto_symbols)
            ))
            quotes.update(crypto_data_client.get_crypto_latest_quote(
                CryptoLatestQuoteRequest(symbol_or_symbols=crypto_symbols)
            ))
        except Exception as e:
            print(f"Could not fetch latest crypto trades/quotes ({e}) — continuing without them.")

    result = {}
    for symbol in symbols:
        trade = trades.get(symbol)
        quote = quotes.get(symbol)
        entry = {}
        if trade is not None and trade.price:
            entry["last_price"] = round(float(trade.price), 6 if is_crypto(symbol) else 2)
        if quote is not None and quote.bid_price and quote.ask_price:
            bid, ask = float(quote.bid_price), float(quote.ask_price)
            precision = 6 if is_crypto(symbol) else 2
            entry["bid"] = round(bid, precision)
            entry["ask"] = round(ask, precision)
            mid = (bid + ask) / 2
            if mid:
                entry["spread_pct"] = round((ask - bid) / mid * 100, 3)
        if entry:
            result[symbol] = entry
    return result


def submit_market_order(symbol: str, notional: float, side: OrderSide):
    # Crypto doesn't support DAY orders (there's no daily session to expire
    # at the end of) — GTC for crypto, DAY (existing behavior) for equities.
    order = MarketOrderRequest(
        symbol=symbol,
        notional=round(notional, 2),
        side=side,
        time_in_force=TimeInForce.GTC if is_crypto(symbol) else TimeInForce.DAY,
    )
    return trading_client.submit_order(order)


def submit_qty_order(symbol: str, qty: float, side: OrderSide):
    order = MarketOrderRequest(
        symbol=symbol,
        qty=qty,
        side=side,
        time_in_force=TimeInForce.GTC if is_crypto(symbol) else TimeInForce.DAY,
    )
    return trading_client.submit_order(order)


def close_position(symbol: str):
    """
    alpaca-py's close_position() drops the symbol straight into the request
    path as DELETE /positions/{symbol} with no encoding of the "/"
    separator crypto pairs use — "BONK/USD" becomes the path
    "/positions/BONK/USD", an extra path segment rather than a symbol
    character, and Alpaca 404s ("Not Found"). This was silently breaking
    every sell/cover on a crypto position (confirmed against the run log:
    the model was correctly deciding to close out crypto positions —
    "closing out the lagging BONK/USD position" — but the order submission
    itself failed every time) and, more seriously, the stop-loss backstop's
    crypto-only sweep (_apply_stop_loss_backstop), which also calls this.

    Fix: strip the "/" before it reaches the URL. Alpaca's own positions
    endpoint already returns crypto positions in this unslashed form (see
    _normalize_crypto_symbol) — this is the identifier Alpaca itself uses,
    not a guess.
    """
    return trading_client.close_position(symbol.replace("/", ""))


def submit_limit_order(symbol: str, qty: float, side: OrderSide, limit_price: float):
    """
    Submits a GTC limit order. Used for both limit buys (buy-the-dip price
    targets) and limit sells (take-profit / stop-gain targets).

    GTC (Good Till Cancelled) keeps the order live until it fills or the agent
    explicitly cancels it — appropriate for price targets that may take
    multiple sessions to hit. The agent should track these open orders and
    cancel/replace them if its thesis changes.

    limit_price is rounded to 6dp for crypto rather than 2dp — a sub-cent
    memecoin (e.g. SHIB at ~$0.00002) would round to $0.00 at 2dp, which
    Alpaca would reject outright.
    """
    order = LimitOrderRequest(
        symbol=symbol,
        qty=qty,
        side=side,
        type=OrderType.LIMIT,
        time_in_force=TimeInForce.GTC,
        limit_price=round(limit_price, 6 if is_crypto(symbol) else 2),
    )
    return trading_client.submit_order(order)
