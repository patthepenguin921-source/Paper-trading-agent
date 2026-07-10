# Agent profitability analysis — 2026-07-09

Data source: `trading_agent_runs` / `trading_agent_decisions` in Supabase
(life-dashboard project), 2026-06-28 through 2026-07-08, plus a code review
of `ai_agent.py` / `alpaca_client.py` / the per-agent instructions.

## Scoreboard (as of 2026-07-08)

| Agent | Start | Latest equity | Closed trades | Win rate | Avg win | Avg loss |
|---|---|---|---|---|---|---|
| Plutus | $100,000 | $102,120 (+2.1%) | 18 | 28% | +0.54% | −0.58% |
| Helios | $100,000 | $99,682 (−0.3%) | 0 | — | — | — |
| Hermes | $10,000 | $9,883 (−1.2%) | 66 | 45% | +0.63% | −0.59% |
| Eris | $100,000 | $98,077 (−1.9%) | 18 | 33% | +2.39% | −1.00% |

Every agent is at or below break-even on realized trading. Plutus' positive
equity is unrealized gains on open positions; its *closed* trades have
negative expectancy.

## The biggest issues, ranked by dollars lost

### 1. Eris couldn't exit crypto positions for three days (execution bug)

Alpaca's positions endpoint returns crypto symbols without the slash
("YFIUSD" for a position opened as "YFI/USD"). Until the fix on 2026-07-09
(`f08bd89`), a held crypto position never matched its universe entry, so
**every sell decision on it was rejected** — either "no long position held
to sell" (model used the slashed form) or "symbol not in approved universe"
(model echoed the unslashed form it saw in `held_positions`).

Between 2026-07-06 and 07-08, Eris had **106 sells rejected as "no
position" and 90 rejected as "not in universe"** — including ~10 separate
attempts across July 7 to lock in a +19.7% gain on YFI/USD that it never
got to keep. Eris' equity went from ~$101k to ~$98k while it watched its
exits bounce.

The remaining gap after `f08bd89`: the *model-output* side is still an
exact-string match. When the model writes "YFIUSD" or "BONK-USD", the
decision is still rejected. Fixed in this change by canonicalizing
decision symbols against the universe.

### 2. Exits fail because shares are tied up in forgotten GTC limit orders

Hermes had **21 of 41 cover decisions error out** with Alpaca code
40310000 ("available: 0 … held_for_orders"): a previous run had queued a
GTC limit exit on the symbol, so when a later run decided to exit at
market, the shares were already reserved and the order was rejected. Eris
hit the same wall 5 times. Net effect: positions the agent had decided to
close stayed open, drifting, sometimes for hours-to-days.

Fixed by cancelling all open orders on a symbol before submitting any exit
for it.

### 3. The agents are told to manage their open orders but cannot see them

Every instructions file says "track your open limit orders and
cancel/replace them" — but `_build_context` never included open orders,
and there was no cancel action. The model was managing blind. Consequences
in the data: **130+ decisions dead-ended as "an order for this symbol is
already pending/unfilled"** (66 for Eris alone), and stale GTC limit
orders sat up to 20 hours blocking both the symbol and the cash committed
to them.

Fixed by adding `open_orders` (with age and limit price) to the decision
context and supporting a `"cancel"` action, plus a shorter stale-order
auto-cancel window for the two day traders.

### 4. Trading on phantom account data (July 7 Alpaca glitch)

From ~14:15 to ~19:00 UTC on 2026-07-07, Alpaca's paper API returned
equity=cash and zero positions (Plutus "lost" 90% of its equity, Helios
79%). The agents were fed that state as fact and kept making decisions on
it — Hermes opened new shorts, Eris issued sells for positions the API
said didn't exist. Nothing in the pipeline sanity-checks account data.

Fixed by adding an anomaly guard: if equity collapsed >20% vs. the last
logged run *and* all positions simultaneously vanished, skip the decision
run and log the anomaly instead of letting the model act on it.

### 5. Negative expectancy — small wins, equal-sized losses, sub-50% hit rates

- Hermes: 66 round trips in 6 sessions, cumulative realized ≈ **−2.4%**;
  July 7 alone was −6.2% across 19 trades. Its shorts repeatedly *chased*
  moves that had already happened (shorting INTC at −9.6% intraday, NVDA
  and QCOM after double-digit slides).
- Plutus: 28% win rate; winners cut at +0.54% average while equity gains
  actually came from positions it happened to keep holding.
- Confidence is uninformative: Hermes' "high"-confidence closed trades
  averaged **−0.22%** vs +0.13% for "medium"; Plutus' high-confidence
  trades were also negative.

Addressed three ways: a code-level per-agent stop-loss backstop
(`max_position_loss_pct` — a disaster cap, generous enough that judgment
still does the work), instructions updates grounded in each agent's actual
numbers (see below), and the open-order visibility above (take-profit
limits were part of the churn).

### 6. Helios is idle, not defensive

Helios bought 10 ETF positions on June 28–29 and has done nothing since —
zero closed trades, ~21% of equity sitting in cash for two weeks, equity
slightly below start. Capital preservation is the mandate, but idle cash
and never rebalancing is drag, not defense. Addressed in instructions: a
deploy-the-core discipline for idle cash and an explicit periodic
review/take-profit rhythm, still within its conservative mandate.

### Non-issues (already resolved, listed to close them out)

- The 71 Plutus / 35 Helios errored runs were June 28–30 Gemini free-tier
  quota exhaustion (gemini-2.5-flash's 20 req/day cap); the move to
  gemini-3.1-flash-lite fixed this — zero API-quota run errors since
  June 30.
- Eris' one-off Groq 413 (payload too large) hasn't recurred since Gemini
  became primary.

## What was implemented (this change)

1. Canonicalize model-returned symbols against the universe (`YFIUSD` →
   `YFI/USD`) before cap enforcement.
2. Cancel a symbol's open orders before submitting a sell/cover for it.
3. Surface open orders in the decision context; add a `"cancel"` action;
   per-agent stale-order max age (8h for Hermes/Eris, 20h default).
4. Account-data anomaly guard (skip run on equity collapse + vanished
   positions).
5. Per-agent `max_position_loss_pct` stop-loss backstop, enforced at the
   start of each run: Hermes 5%, Helios 6%, Plutus 8%, Eris 10%.
6. Data-grounded lessons appended to each agent's instructions (repo files
   and the live Supabase `agent_instructions` rows).
