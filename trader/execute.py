"""
Shared execution path for both agents: stop-loss backstop, risk checks,
order placement, logging.

    python -m trader.execute analyst workspace/decisions.json [--dry-run]

Claude never places orders itself. It writes decisions.json and this script,
which holds the Alpaca keys, decides what actually gets traded.
"""
import argparse
import json
import os
import sys

from trader import risk, store
from trader.alpaca import Alpaca


def run_cycle(agent_id: str, decisions: list[dict], *, market_view: str = "",
              model: str = "", summary: dict | None = None, dry_run: bool = False) -> dict:
    client = Alpaca(agent_id)
    trigger = os.environ.get("RUN_TRIGGER", "manual")
    clock = client.clock()
    if not clock.get("is_open"):
        print("Market is closed; nothing to execute.")
        store.log_run(agent_id, market_open=False, trigger=trigger, model=model,
                      market_view=market_view, summary=summary or {})
        return {"market_open": False, "results": []}

    if not dry_run:
        # Everything is a DAY market order, so anything still open is stale.
        client.cancel_all_orders()

    account = client.account()
    equity = float(account["equity"])
    positions = risk.normalize_positions(client.positions())

    stops = risk.stop_loss_exits(positions)
    stopped = {s["symbol"] for s in stops}
    proposals = stops + [d for d in decisions if str(d.get("symbol", "")).upper() not in stopped]

    entry_syms = sorted({str(d.get("symbol", "")).upper() for d in proposals
                         if str(d.get("action", "")).lower() in ("buy", "short")} - {""})
    assets = {s: (client.asset(s) or {}) for s in entry_syms}
    prices = {}
    if entry_syms:
        for sym, snap in client.snapshots(entry_syms).items():
            trade = snap.get("latestTrade") or {}
            p = trade.get("p") or (snap.get("dailyBar") or {}).get("c") or (snap.get("prevDailyBar") or {}).get("c")
            if p:
                prices[sym] = float(p)

    results = risk.plan_orders(proposals, equity, positions, prices, assets)

    for r in results:
        if r["status"] != "planned":
            continue
        if dry_run:
            r["status"] = "dry_run"
            continue
        try:
            if r["kind"] == "close":
                order = client.close_position(r["symbol"], r["fraction"])
            else:
                order = client.market_order(r["symbol"], r["qty"], r["side"],
                                            client_order_id=f"{agent_id}-{r['symbol']}-{os.urandom(4).hex()}")
            r["order_id"] = order.get("id")
            r["status"] = "submitted"
            r["qty"] = r.get("qty") or _f(order.get("qty"))
        except Exception as e:  # one bad order shouldn't stop the rest
            r["status"] = "error"
            r["note"] = (r.get("note") + " " if r.get("note") else "") + str(e)[:300]

    for r in results:
        flag = {"submitted": "OK ", "dry_run": "DRY", "rejected": "NO ", "error": "ERR"}.get(r["status"], "?  ")
        print(f"[{flag}] {r['action']:5} {r['symbol']:6} qty={r.get('qty') or r.get('fraction') or '-'} {r.get('note') or ''}")

    run_id = store.log_run(
        agent_id, market_open=True, trigger=trigger, model=model, market_view=market_view,
        equity=equity, cash=float(account["cash"]), num_positions=len(positions),
        summary={**(summary or {}), "dry_run": dry_run,
                 "submitted": sum(r["status"] == "submitted" for r in results),
                 "rejected": sum(r["status"] == "rejected" for r in results)},
    )
    store.log_decisions(run_id, agent_id, [_row(r) for r in results])
    return {"market_open": True, "results": results, "run_id": run_id}


def _row(r: dict) -> dict:
    keep = ("symbol", "action", "size_pct", "qty", "confidence", "thesis", "exit_plan",
            "status", "note", "order_id", "est_price", "fraction")
    row = {k: r.get(k) for k in keep}
    row["confidence"] = _f(row["confidence"])
    row["size_pct"] = _f(row["size_pct"])
    row["qty"] = _f(row["qty"])
    return row


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("agent")
    ap.add_argument("decisions_file")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    summary = {}
    try:
        with open(args.decisions_file) as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        # Still run, so the stop-loss backstop fires and the failure is logged.
        print(f"Could not read {args.decisions_file}: {e}", file=sys.stderr)
        payload, summary["error"] = {}, f"decisions file unreadable: {e}"

    decisions = payload.get("decisions") or []
    if not isinstance(decisions, list):
        decisions, summary["error"] = [], "decisions is not a list"
    if payload.get("journal"):
        summary["journal"] = str(payload["journal"])[:8000]
    run_cycle(args.agent, decisions, market_view=str(payload.get("market_view", ""))[:4000],
              model=os.environ.get("AGENT_MODEL", payload.get("model", "")),
              summary=summary, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
