"""
Builds the analyst's research workspace before Claude runs.

    python -m trader.brief analyst [--out workspace] [--allow-closed]

Writes:
  workspace/brief.md        account, positions, recent fills, performance vs
                            SPY, market overview, movers, a stats table for
                            the whole universe, and news headlines
  workspace/history/X.csv   about 18 months of daily OHLCV for every symbol
                            in the brief, so Claude can study price history
                            in depth for anything it's considering
  workspace/brief.json      the same data as JSON

Claude's step runs without the Alpaca keys, so everything it might need
from Alpaca has to be gathered here, ahead of time.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from trader import indicators, risk
from trader.alpaca import Alpaca
from trader.config import RISK
from trader.universe import UNIVERSE

ET = ZoneInfo("America/New_York")
OVERVIEW = ["SPY", "QQQ", "IWM", "DIA", "TLT", "GLD", "USO", "HYG", "XLK", "XLF", "XLE",
            "XLV", "XLY", "XLP", "XLI", "XLU", "XLB", "XLRE", "XLC", "SMH"]
COLS = ["close", "chg_1d", "chg_5d", "chg_1m", "chg_3m", "chg_1y", "rsi14", "vs_sma50",
        "vs_sma200", "off_52w_high", "vol20_ann", "avg_dollar_vol_m"]


def _table(rows: dict[str, dict], cols=COLS) -> str:
    head = "| symbol | " + " | ".join(cols) + " |\n|" + "---|" * (len(cols) + 1) + "\n"
    body = ""
    for sym, st in rows.items():
        body += f"| {sym} | " + " | ".join("" if st.get(c) is None else str(st[c]) for c in cols) + " |\n"
    return head + body


def _set_output(name: str, value: str):
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a") as f:
            f.write(f"{name}={value}\n")


def build(agent_id: str, out: str, allow_closed: bool) -> bool:
    client = Alpaca(agent_id)
    clock = client.clock()
    is_open = bool(clock.get("is_open"))
    _set_output("market_open", str(is_open).lower())
    if not is_open and not allow_closed:
        print(f"Market closed (next open {clock.get('next_open')}). Skipping brief.")
        return False

    os.makedirs(f"{out}/history", exist_ok=True)
    now_et = datetime.now(timezone.utc).astimezone(ET)
    account = client.account()
    raw_positions = client.positions()
    positions = risk.normalize_positions(raw_positions)
    equity = float(account["equity"])

    movers = client.movers(15)
    gainers = [m["symbol"] for m in movers.get("gainers", [])]
    losers = [m["symbol"] for m in movers.get("losers", [])]
    actives = [m["symbol"] for m in client.most_actives(20)]

    symbols = sorted(set(UNIVERSE) | set(OVERVIEW) | set(positions) | set(gainers) | set(losers) | set(actives))
    bars = client.daily_bars(symbols, days=550)
    stats = {}
    for sym in symbols:
        b = bars.get(sym) or []
        if not b:
            continue
        stats[sym] = indicators.summarize(b)
        with open(f"{out}/history/{sym.replace('/', '_')}.csv", "w") as f:
            f.write("date,open,high,low,close,volume\n")
            for x in b:
                f.write(f"{x['t'][:10]},{x['o']},{x['h']},{x['l']},{x['c']},{x['v']}\n")

    # Live prices for today's move (snapshots are real time on IEX).
    snaps = client.snapshots(symbols)
    for sym, snap in snaps.items():
        price = (snap.get("latestTrade") or {}).get("p")
        prev = (snap.get("prevDailyBar") or {}).get("c")
        if sym in stats and price and prev:
            stats[sym]["live"] = round(float(price), 2)
            stats[sym]["today_pct"] = round((float(price) / float(prev) - 1) * 100, 2)

    fills = client.fills(30)
    history = client.portfolio_history("3M")
    news_market = client.news(None, 40)
    news_held = client.news(sorted(positions)[:40], 30) if positions else []

    # ---- markdown -----------------------------------------------------------
    md = [f"# Market brief: {now_et:%A %Y-%m-%d %H:%M} ET",
          f"Market open: **{is_open}**. Next close: {clock.get('next_close')}. Next open: {clock.get('next_open')}.", ""]

    md += ["## Account",
           f"- Equity: ${equity:,.2f} | Cash: ${float(account['cash']):,.2f} | "
           f"Long MV: ${float(account.get('long_market_value', 0)):,.2f} | "
           f"Short MV: ${float(account.get('short_market_value', 0)):,.2f}",
           f"- Day change: {((equity / float(account['last_equity']) - 1) * 100) if float(account.get('last_equity') or 0) else 0:.2f}%", ""]

    eq = [x for x in (history.get("equity") or []) if x]
    if len(eq) >= 2:
        spy = [float(b["c"]) for b in (bars.get("SPY") or [])][-len(eq):]
        spy_ret = (spy[-1] / spy[0] - 1) * 100 if len(spy) >= 2 else None
        md += ["## Performance (last ~3 months of account history)",
               f"- Account: {(eq[-1] / eq[0] - 1) * 100:.2f}% over {len(eq)} trading days"
               + (f" | SPY over the same days: {spy_ret:.2f}%" if spy_ret is not None else ""), ""]

    md += ["## Open positions"]
    if positions:
        md.append("| symbol | qty | side | avg entry | price | P/L % | % of equity |\n|---|---|---|---|---|---|---|")
        for sym, p in sorted(positions.items(), key=lambda kv: -abs(kv[1]["market_value"])):
            md.append(f"| {sym} | {abs(p['qty']):g} | {'long' if p['qty'] > 0 else 'SHORT'} | "
                      f"{p['avg_entry_price']:.2f} | {p['current_price']:.2f} | {p['unrealized_plpc']:.2f} | "
                      f"{abs(p['market_value']) / equity * 100:.1f} |")
    else:
        md.append("No open positions (all cash).")
    md.append("")

    md += ["## Fills in the last 30 days (newest first)"]
    if fills:
        for f_ in fills[:40]:
            md.append(f"- {f_.get('transaction_time', '')[:16]} {f_.get('side')} {f_.get('qty')} {f_.get('symbol')} @ {f_.get('price')}")
    else:
        md.append("None.")
    md.append("")

    md += ["## Market overview (indexes, rates, commodities, sectors)",
           _table({s: stats[s] for s in OVERVIEW if s in stats}, ["live", "today_pct"] + COLS[1:]), ""]

    def mover_rows(lst):
        return {s: stats[s] for s in lst if s in stats}
    md += ["## Today's top gainers (all US stocks; many are illiquid, so check volume and price)",
           _table(mover_rows(gainers), ["live", "today_pct", "chg_1m", "avg_dollar_vol_m"]),
           "## Today's top losers", _table(mover_rows(losers), ["live", "today_pct", "chg_1m", "avg_dollar_vol_m"]),
           "## Most active by volume", _table(mover_rows(actives), ["live", "today_pct", "chg_1m", "avg_dollar_vol_m"]), ""]

    md += ["## Universe stats (core liquid stocks/ETFs; full daily history in workspace/history/<SYMBOL>.csv)",
           _table({s: stats[s] for s in UNIVERSE if s in stats and s not in OVERVIEW}, ["live", "today_pct"] + COLS[1:]), ""]

    def news_lines(items):
        return [f"- {n.get('created_at', '')[:16]} [{','.join(n.get('symbols', [])[:5])}] {n.get('headline', '')} ({n.get('source', '')})"
                for n in items]
    md += ["## News on held positions", *(news_lines(news_held) or ["None."]), "",
           "## General market news", *(news_lines(news_market) or ["None."]), ""]

    md += ["## Hard risk limits (enforced in code; orders outside them are clipped or rejected)",
           *[f"- {k}: {v}" for k, v in RISK.items()], ""]

    with open(f"{out}/brief.md", "w") as f:
        f.write("\n".join(md))
    with open(f"{out}/brief.json", "w") as f:
        json.dump({"generated_at": now_et.isoformat(), "clock": clock, "account": account,
                   "positions": positions, "stats": stats, "movers": movers, "most_actives": actives,
                   "fills": fills[:100], "news": news_held + news_market}, f, default=str)
    print(f"Brief written to {out}/brief.md ({len(stats)} symbols, {len(positions)} positions)")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("agent", nargs="?", default="analyst")
    ap.add_argument("--out", default="workspace")
    ap.add_argument("--allow-closed", action="store_true")
    args = ap.parse_args()
    build(args.agent, args.out, args.allow_closed)


if __name__ == "__main__":
    main()
