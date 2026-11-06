"""
Records equity + positions for both agents (no trading, no AI). Feeds the
dashboard's equity curves and positions view.

    python -m trader.snapshot [--force]

Skips quietly outside roughly 9:00-16:30 ET on weekdays unless --force.
"""
import argparse
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from trader import config, risk, store
from trader.alpaca import Alpaca

ET = ZoneInfo("America/New_York")


def snapshot(agent_id: str):
    client = Alpaca(agent_id)
    account = client.account()
    positions = risk.normalize_positions(client.positions())
    spy = None
    try:
        spy = client.latest_price("SPY")
    except Exception as e:
        print(f"SPY price unavailable: {e}")
    store.insert("pt_snapshots", {
        "agent_id": agent_id,
        "equity": float(account["equity"]),
        "cash": float(account["cash"]),
        "long_value": float(account.get("long_market_value") or 0),
        "short_value": float(account.get("short_market_value") or 0),
        "spy_price": spy,
        "positions": [{"symbol": s, **p} for s, p in sorted(positions.items())],
    })
    print(f"{agent_id}: equity ${float(account['equity']):,.2f}, {len(positions)} positions")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    now = datetime.now(timezone.utc).astimezone(ET)
    in_window = now.weekday() < 5 and (9, 0) <= (now.hour, now.minute) <= (16, 30)
    if not in_window and not args.force:
        print(f"Outside snapshot window ({now:%a %H:%M} ET); skipping.")
        return
    for agent_id in config.AGENTS:
        try:
            snapshot(agent_id)
        except SystemExit as e:  # missing credentials for one agent shouldn't block the other
            print(e)
        except Exception as e:
            print(f"{agent_id}: snapshot failed: {e}")


if __name__ == "__main__":
    main()
