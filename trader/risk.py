"""
Turns proposed decisions (from Claude or the monkey) into concrete orders,
enforcing config.RISK. Pure functions, no I/O.

Decision shape (what agents propose):
    {"symbol": "AAPL", "action": "buy|sell|short|cover",
     "size_pct": 5,            # buy/short: target % of equity for the new money
     "fraction": 1.0,          # sell/cover: share of the position to close (default all)
     "confidence": 0.7, "thesis": "...", "exit_plan": "..."}

Position shape (normalized from Alpaca):
    {"qty": 10.0 (negative for shorts), "market_value": 1234.5 (negative for shorts),
     "unrealized_plpc": -3.2 (percent), "avg_entry_price": 100.0}
"""
import math

from trader.config import RISK

ACTIONS = {"buy", "sell", "short", "cover"}


def normalize_positions(raw: list[dict]) -> dict[str, dict]:
    out = {}
    for p in raw:
        qty = float(p["qty"])
        out[p["symbol"]] = {
            "qty": qty,
            "market_value": float(p.get("market_value") or 0),
            "unrealized_plpc": float(p.get("unrealized_plpc") or 0) * 100,
            "avg_entry_price": float(p.get("avg_entry_price") or 0),
            "current_price": float(p.get("current_price") or 0),
        }
    return out


def stop_loss_exits(positions: dict[str, dict], limit_pct: float = RISK["stop_loss_pct"]) -> list[dict]:
    """Positions down more than limit_pct get closed before anything else runs."""
    exits = []
    for sym, p in positions.items():
        if p["unrealized_plpc"] <= -limit_pct:
            exits.append({
                "symbol": sym,
                "action": "sell" if p["qty"] > 0 else "cover",
                "fraction": 1.0,
                "confidence": 1.0,
                "thesis": f"Stop-loss backstop: down {p['unrealized_plpc']:.1f}% (limit {limit_pct:.0f}%).",
            })
    return exits


def _result(d: dict, status: str, note: str = "", **extra) -> dict:
    return {
        "symbol": d.get("symbol"),
        "action": d.get("action"),
        "size_pct": d.get("size_pct"),
        "confidence": d.get("confidence"),
        "thesis": d.get("thesis"),
        "exit_plan": d.get("exit_plan"),
        "status": status,
        "note": note,
        **extra,
    }


def plan_orders(
    decisions: list[dict],
    equity: float,
    positions: dict[str, dict],
    prices: dict[str, float],
    assets: dict[str, dict],
    risk: dict = RISK,
) -> list[dict]:
    """
    Returns one result per decision, with status 'planned' or 'rejected'.
    Planned results carry 'side' and either 'qty' (open) or 'fraction' (close).
    Exits are processed before entries so they free up room; entries are
    taken highest-confidence first.
    """
    results: list[dict] = []
    seen: set[str] = set()
    cleaned: list[dict] = []
    for d in decisions:
        d = dict(d)
        d["symbol"] = str(d.get("symbol", "")).upper().strip()
        d["action"] = str(d.get("action", "")).lower().strip()
        if d["action"] not in ACTIONS:
            results.append(_result(d, "rejected", f"Unknown action '{d['action']}'"))
            continue
        if not d["symbol"] or d["symbol"] in seen:
            results.append(_result(d, "rejected", "Missing or duplicate symbol"))
            continue
        seen.add(d["symbol"])
        cleaned.append(d)

    # Exposure bookkeeping, updated as we plan.
    long_mv = sum(p["market_value"] for p in positions.values() if p["qty"] > 0)
    short_mv = -sum(p["market_value"] for p in positions.values() if p["qty"] < 0)
    open_symbols = set(positions)

    # 1) exits
    for d in [d for d in cleaned if d["action"] in ("sell", "cover")]:
        pos = positions.get(d["symbol"])
        want_long = d["action"] == "sell"
        if not pos or (pos["qty"] > 0) != want_long:
            held = "nothing" if not pos else ("a long" if pos["qty"] > 0 else "a short")
            results.append(_result(d, "rejected", f"Can't {d['action']} {d['symbol']}: holding {held}"))
            continue
        fraction = d.get("fraction")
        try:
            fraction = 1.0 if fraction in (None, "") else float(fraction)
        except (TypeError, ValueError):
            fraction = 1.0
        fraction = min(1.0, max(0.01, fraction))
        released = abs(pos["market_value"]) * fraction
        if want_long:
            long_mv -= released
        else:
            short_mv -= released
        if fraction >= 0.999:
            open_symbols.discard(d["symbol"])
        results.append(_result(d, "planned", side="sell" if want_long else "buy",
                               fraction=fraction, kind="close"))

    # 2) entries, highest confidence first
    entries = [d for d in cleaned if d["action"] in ("buy", "short")]
    entries.sort(key=lambda d: -(_num(d.get("confidence")) or 0))
    for d in entries:
        sym, is_long = d["symbol"], d["action"] == "buy"
        pos = positions.get(sym)
        price = prices.get(sym)
        asset = assets.get(sym) or {}

        if not asset.get("tradable"):
            results.append(_result(d, "rejected", f"{sym} is not tradable on Alpaca"))
            continue
        if asset.get("class") and asset["class"] != "us_equity":
            results.append(_result(d, "rejected", f"{sym} is not a US stock/ETF"))
            continue
        if not price or price < risk["min_price"]:
            results.append(_result(d, "rejected", f"Price {price} below ${risk['min_price']} minimum or unknown"))
            continue
        if pos and (pos["qty"] > 0) != is_long:
            results.append(_result(d, "rejected", f"Already {'long' if pos['qty'] > 0 else 'short'} {sym}; close it first"))
            continue
        if not is_long and not (asset.get("shortable") and asset.get("easy_to_borrow")):
            results.append(_result(d, "rejected", f"{sym} is not shortable / easy to borrow"))
            continue
        if not pos and len(open_symbols) >= risk["max_positions"]:
            results.append(_result(d, "rejected", f"Already at {risk['max_positions']} positions"))
            continue

        size_pct = _num(d.get("size_pct")) or risk["min_position_pct"]
        size_pct = min(risk["max_position_pct"], max(risk["min_position_pct"], size_pct))
        existing = abs(pos["market_value"]) if pos else 0.0
        notional = min(size_pct / 100 * equity, risk["max_position_pct"] / 100 * equity - existing)
        notional = min(notional, risk["max_gross_exposure_pct"] / 100 * equity - (long_mv + short_mv))
        if not is_long:
            notional = min(notional, risk["max_short_exposure_pct"] / 100 * equity - short_mv)
        qty = math.floor(max(0.0, notional) / price)
        if qty < 1 or qty * price < risk["min_position_pct"] / 100 * equity * 0.5:
            results.append(_result(d, "rejected", "No room left under position/exposure limits"))
            continue

        if is_long:
            long_mv += qty * price
        else:
            short_mv += qty * price
        open_symbols.add(sym)
        results.append(_result(d, "planned", side="buy" if is_long else "sell", qty=qty,
                               est_price=round(price, 2), size_pct=round(qty * price / equity * 100, 2),
                               kind="open"))
    return results


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None
