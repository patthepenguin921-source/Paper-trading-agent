"""
Agent definitions and the hard risk limits enforced in code.

There are exactly two agents, each with its own Alpaca *paper* account:

- analyst: Claude (via Claude Code on your Claude subscription, no API key)
  reads a market brief, its playbook, its own memory and any documents you
  drop in analyst/library/, then writes decisions. Python validates and
  places them.
- monkey: no AI at all. Throws darts at a list of liquid stocks/ETFs: random
  picks, random direction, random size, random exits. It is the benchmark the
  analyst has to beat to prove it is adding anything.

Both agents get identical risk limits so the comparison is fair.
"""
import os

AGENTS = {
    "analyst": {
        "name": "The Analyst",
        "key_env": "ALPACA_ANALYST_KEY",
        "secret_env": "ALPACA_ANALYST_SECRET",
    },
    "monkey": {
        "name": "The Monkey",
        "key_env": "ALPACA_MONKEY_KEY",
        "secret_env": "ALPACA_MONKEY_SECRET",
    },
}

# Hard limits, the same for both agents. Code clamps or rejects anything
# outside them; neither Claude nor the dice can override these.
RISK = {
    # Largest single position as % of equity (at entry).
    "max_position_pct": 10.0,
    # Smallest position worth opening, as % of equity.
    "min_position_pct": 1.0,
    # Most simultaneous open positions.
    "max_positions": 15,
    # Total long + short market value can't exceed this % of equity (no leverage).
    "max_gross_exposure_pct": 100.0,
    # Total short market value can't exceed this % of equity.
    "max_short_exposure_pct": 40.0,
    # Any position down more than this % from entry is closed at the start
    # of every run, before any new decisions. A disaster brake, not a strategy.
    "stop_loss_pct": 15.0,
    # Don't trade anything priced under this (penny-stock guard).
    "min_price": 5.0,
}

PAPER_BASE_URL = "https://paper-api.alpaca.markets"
DATA_BASE_URL = "https://data.alpaca.markets"


def agent(agent_id: str) -> dict:
    if agent_id not in AGENTS:
        raise SystemExit(f"Unknown agent '{agent_id}'. Expected one of: {', '.join(AGENTS)}")
    return AGENTS[agent_id]


def credentials(agent_id: str) -> tuple[str, str]:
    a = agent(agent_id)
    key, secret = os.environ.get(a["key_env"]), os.environ.get(a["secret_env"])
    if not key or not secret:
        raise SystemExit(
            f"Missing Alpaca paper credentials for '{agent_id}': set the "
            f"{a['key_env']} and {a['secret_env']} repository secrets."
        )
    return key, secret
