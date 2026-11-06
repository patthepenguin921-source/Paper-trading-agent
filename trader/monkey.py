"""
The Monkey: a dart-throwing baseline with no AI and no analysis.

    python -m trader.monkey [--dry-run] [--seed N]

Each run (once per trading day):
  * Each open position has a 1-in-HOLD_DAYS chance of being closed, so the
    average hold is about HOLD_DAYS trading days, with no memory needed.
  * If it holds fewer than TARGET_POSITIONS, it throws 0-3 darts at the
    universe. Each dart picks a random symbol, goes long (70%) or short (30%),
    and gets a random size between 3% and 10% of equity.
  * The only "educated" part: it throws only at liquid, well-known names
    (trader/universe.py), and it obeys the same risk limits as the analyst.

The seed is logged with every run so any day's throws can be replayed.
"""
import argparse
import random
import time

from trader import risk
from trader.alpaca import Alpaca
from trader.execute import run_cycle
from trader.universe import UNIVERSE

HOLD_DAYS = 7
TARGET_POSITIONS = 10
LONG_PROBABILITY = 0.7


def throw_darts(positions: dict[str, dict], rng: random.Random, universe: list[str] = UNIVERSE) -> list[dict]:
    decisions = []
    for sym, p in sorted(positions.items()):
        if rng.random() < 1 / HOLD_DAYS:
            decisions.append({"symbol": sym, "action": "sell" if p["qty"] > 0 else "cover",
                              "confidence": round(rng.random(), 2),
                              "thesis": "The dart says it's time to go."})
    remaining = len(positions) - len(decisions)
    if remaining < TARGET_POSITIONS:
        darts = min(rng.randint(0, 3), TARGET_POSITIONS - remaining)
        candidates = [s for s in universe if s not in positions]
        for sym in rng.sample(candidates, k=min(darts, len(candidates))):
            long_ = rng.random() < LONG_PROBABILITY
            decisions.append({"symbol": sym, "action": "buy" if long_ else "short",
                              "size_pct": round(rng.uniform(3, 10), 1),
                              "confidence": round(rng.random(), 2),
                              "thesis": f"Dart landed on {sym}; coin says {'long' if long_ else 'short'}."})
    return decisions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()
    seed = args.seed if args.seed is not None else int(time.time())
    rng = random.Random(seed)

    client = Alpaca("monkey")
    positions = risk.normalize_positions(client.positions())
    decisions = throw_darts(positions, rng)
    print(f"Seed {seed}: {len(decisions)} darts thrown")
    run_cycle("monkey", decisions, model="none (random)",
              market_view=f"No view. Darts thrown with seed {seed}.",
              summary={"seed": seed}, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
