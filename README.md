# Paper Trading Agent

An autonomous **AI-driven paper trading agent** for stocks, ETFs, and (as of
Eris) crypto, powered by Gemini and run for free on GitHub Actions. It trades
with simulated money — no real funds are ever at risk. Three of the four
agents (Plutus, Helios, Hermes) never touch crypto by design; Eris is the
one exception, trading meme stocks and memecoins via Alpaca's separate
crypto API — see `alpaca_client.is_crypto()` and `instructions_eris.md`.

## How it works

1. **`.github/workflows/trade.yml`** (and the Helios/Hermes/Eris equivalents)
   are triggered by a Supabase pg_cron job and can also be triggered manually
   from the Actions tab. The intended decision cadence is every 15 minutes
   during market hours; `main.py` self-throttles to that cadence in code
   (`ai_agent.should_throttle_cadence()`) regardless of how often the
   external trigger actually fires, so a faster or misconfigured trigger
   can't cause more-frequent-than-intended trading or burn through API quota.
   Note: this schedule is equity-market-hours-based for all four agents —
   Eris' crypto leg trades 24/7 on Alpaca, but Eris itself only checks in on
   it during the same windows as everyone else's stock trading, for now.
2. **`main.py`** checks Alpaca's market clock and exits immediately if the
   market is closed.
3. **`ai_agent.py`** gathers account state, open positions, and recent
   price stats for the universe in `config.py` (crypto and equity symbols
   both, for Eris — merged transparently by `alpaca_client.get_recent_bars`/
   `get_latest_prices`), plus each agent's own slice of today's market-wide
   most-active/biggest-mover US equities (`alpaca_client.get_market_screen`,
   sized per agent by `dynamic_universe_top_n` in `config.py`) so the
   watchlist isn't limited to each agent's hand-picked core list — see
   `_build_context`'s `effective_universe`. Held positions are always
   included in that fetch too, even if they've since fallen out of both the
   core list and today's screen. It also cancels any open orders that never
   resolved (see `alpaca_client.cancel_stale_open_orders`) so they stop
   tying up cash indefinitely, and builds a news/politics/society
   briefing — a Gemini
   call that synthesizes real Alpaca News API headlines plus, for the
   sentiment-driven agents (Hermes/Eris), live keyless retail-sentiment
   aggregators: ApeWisdom's Reddit ticker-mention leaderboards (stocks and
   crypto), StockTwits' trending symbols, CoinGecko trending, and the
   Crypto Fear & Greed index (see `ai_agent._fetch_retail_sentiment`;
   `.github/workflows/test-sentiment-sources.yml` re-verifies the
   endpoints on demand). Direct Reddit scraping needs OAuth credentials
   (`REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET` secrets) — Reddit's public
   endpoints 403 GitHub Actions IPs, so without those secrets the Reddit
   leg is skipped and the aggregators carry the sentiment signal alone.
   No agent uses Google-Search-grounded research: grounding
   isn't available on the free tier (the grounded call 429s instantly),
   and leaving it enabled for Plutus/Helios silently served them a stale
   June-30 briefing for 9 days. The briefing is cached in Supabase and
   refreshed at most every `NEWS_REFRESH_MINUTES` (so a fast cron doesn't
   re-search every run); the decision prompt states the briefing's actual
   age, warns when it's stale, includes the raw dated headlines so the
   model can verify specifics against a primary source, and a push
   notification fires (at most every 6h) if the refresh keeps failing.
   Both feed into a separate Gemini call
   (alongside the agent's instructions file) that returns
   buy/sell/short/cover/hold decisions with reasoning (short/cover only for
   agents with `allow_short` set — see the table below; crypto symbols are
   always long-only regardless of that flag, since Alpaca crypto is
   spot-only). The decision context includes the agent's own open
   (unfilled) orders, and a `cancel` action lets it clear one; sells and
   covers auto-cancel that symbol's open orders first so a pending GTC
   limit exit can't block them (Alpaca error 40310000, "held_for_orders").
   A per-run sanity check also skips the decision call entirely if Alpaca
   returns obviously-broken account state (equity collapsed while all
   positions simultaneously vanished — it happened for ~5 hours on
   2026-07-07), a per-agent stop-loss backstop closes any position
   past its `max_position_loss_pct` before the AI is consulted, and a
   daily loss circuit breaker (`max_daily_loss_pct`) blocks new buys/shorts
   for the rest of the day once equity has fallen that far below the day's
   first reading — exits and cancels still work, and the model is told the
   breaker is active so it spends the run managing positions instead of
   proposing entries that would be rejected. The decision context also
   includes the agent's own recent closed-trade track record
   (`ai_agent._recent_trade_outcomes`): its last 20 realized trades with
   rolling win rate, average win/loss, and expectancy, so it reasons with
   memory of how its recent trading actually went instead of re-running
   the same losing thesis blind. See
   `docs/profitability-analysis-2026-07-09.md` for the review that led to
   all of this.
4. **Hard risk caps in `config.py` are enforced in code** — the AI's
   judgment never overrides them. Max new buys per run and position sizing
   are checked before any order is placed (see the table below for current
   per-agent values — some caps, like max open positions and the cash
   floor, have deliberately been removed in favor of the AI weighing that
   context itself; see `instructions.md`'s "Lessons learned" section).
5. **Every run is logged to Supabase** (`trading_agent_runs` and
   `trading_agent_decisions` tables in the life-dashboard project) — that's
   your window into what the agent decided and why.
6. **`alpaca_client.py`** is the only file that talks to Alpaca, pinned to
   `paper=True` so it can never place a live order.
7. **Executed trades and run failures push a notification** to the Plutus
   dashboard (trading-agent-dashboard repo) — enable alerts from the bell in
   its nav once it's added to your home screen.

## Steering the agent

Edit **`instructions.md`** — that's the agent's system prompt and trading
philosophy. Tell the assistant what you want changed (risk tolerance,
things to avoid/prioritize, lessons learned) and it'll update and push the
file. The agent reads it fresh on every run, so changes take effect
immediately on the next scheduled run.

## Reviewing what it's done

Query the Supabase tables directly, or build a view into them from your
Command Deck dashboard:

- `trading_agent_runs` — one row per run: account state, overall reasoning,
  the news/politics/society briefing in play that run, whether the market
  was open, any errors.
- `trading_agent_decisions` — one row per symbol the agent acted on: the
  action, quantity, confidence, full reasoning text, and the resulting
  order ID/status (including why something was skipped if a risk cap
  blocked it).
- `agent_news_context` — single cached row holding the most recent news/
  politics/society briefing and when it was last researched.

## Setup

Repo secrets required (**Settings → Secrets and variables → Actions**), per
agent following the `<BASE>_<AGENT>` naming convention (Plutus, the original
agent, uses no suffix — see any agent-specific workflow file for the exact
names each one reads):

- `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` (plus `_HELIOS`/`_HERMES`/`_ERIS`
  variants) — your Alpaca **paper** trading keys. One key pair per agent,
  each its own separate paper account. For Eris, the same key pair is used
  for both its equity and crypto trades — Alpaca doesn't split those into
  separate credentials.
- `GEMINI_API_KEY` (plus `_HELIOS`/`_HERMES`/`_ERIS` and `_2` variants) —
  from Google AI Studio (aistudio.google.com). Free tier covers this
  comfortably: the decision call runs every minute during market hours, and
  the news-research call (with Google Search grounding) only runs once every
  `NEWS_REFRESH_MINUTES` thanks to the Supabase cache, not every run. One
  caveat: on the free tier, Google's terms allow your prompts/responses to
  be used to improve their models. That's the trade-off for $0 — fine for
  paper-trading test data, just worth knowing.
- `SUPABASE_URL` / `SUPABASE_KEY` — already set, pointing at the
  life-dashboard project, shared across all agents.

You can trigger a run immediately from the **Actions** tab via
"Run workflow" (workflow_dispatch), without waiting for the schedule.

## Manual one-off orders

`.github/workflows/manual-order.yml` lets you fire a single buy/sell from
the Actions tab outside the AI agent's normal decision loop — useful for
testing. Results get written to `last_order_result.json` in the repo.

## Risk guardrails (config.py)

Per-agent, set in the `AGENTS` dict in `config.py`. `max_open_positions` and
the cash floor are intentionally `None`/`0` for every agent right now — see
`instructions.md`'s "Lessons learned" section for why (position sizing and
the AI's own equity-floor judgment are the real guardrails there instead).

| Setting | Plutus | Helios | Hermes | Eris | Meaning |
|---|---|---|---|---|---|
| `max_open_positions` | none | none | none | none | Cap on simultaneous open positions |
| `max_new_buys_per_run` | 3 | 2 | none | none | Cap on new positions (buys/shorts) opened in a single run |
| `position_size_pct_min`–`max` | 4%–18% | 3%–10% | 5%–25% | 3%–15% | Position size range as a fraction of equity; the AI picks within it, code clamps if it doesn't |
| `min_cash_buffer_pct` | 0% | 0% | 0% | 0% | Cash always kept in reserve |
| `allow_short` | yes | yes | yes | yes | Whether "short"/"cover" decisions are allowed, enforced in code. Crypto symbols are long-only regardless of this flag — Alpaca crypto has no margin/shorting at all. |
| `max_position_loss_pct` | 8% | 6% | 5% | 10% | Stop-loss **backstop**: any position whose unrealized loss exceeds this is closed at market at the start of the next run, before the AI is called. A disaster brake for tail moves between runs — the AI's own exit judgment is still expected to fire long before this does. |
| `max_daily_loss_pct` | 5% | 3% | 5% | 7% | Daily loss **circuit breaker**, the account-level sibling of the row above: once equity is this far below the day's first logged reading, new buys/shorts are rejected in code for the rest of the trading day (sells/covers/cancels still work). Born from Hermes' 2026-07-07: −6.2% in one session, with new shorts still being opened after −4%. |
| `stale_order_max_age_hours` | 20h | 20h | 8h | 8h | Unfilled orders older than this are auto-cancelled at the start of each run so they stop reserving shares/cash. Shorter for the two day traders — an 8-hour-old limit order is a different session's thesis at their holding period. |

All four agents can now short (their equity/ETF positions, at least) — the
instructions files frame it differently per agent's mandate (Plutus:
another way to express real conviction; Helios: a defensive/hedging tool
only, kept to the same high bar as a buy; Hermes: a full second direction
to trade, same as a long; Eris: available on meme stocks, never on
memecoins).

Hermes and Eris are the two day traders: no cap on trades per run, and both
get real-time last-trade/bid-ask quotes merged into their market data
(`use_live_quotes`), on top of the daily-bar history every agent gets,
since a day trader reasoning only from yesterday's close can't set a sane
limit price intraday. Eris keeps a narrower sizing range than Hermes despite
the uncapped trade count — see `instructions_eris.md` for why (tail risk in
a sentiment-only universe, not conviction).
