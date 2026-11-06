# Paper Trading Agent: Analyst vs. Monkey

Two paper-trading accounts on Alpaca (simulated money only), compared head to head:

| | **The Analyst** | **The Monkey** |
|---|---|---|
| Brain | Claude (Claude Code on your Claude subscription) | `random.Random`, no AI |
| How it picks | Reads a market brief, about 18 months of price history, news, web research and documents you give it, then writes theses | Throws darts at ~150 liquid stocks/ETFs: random symbol, 70/30 long/short, random size |
| How it exits | Its own written exit plans, re-checked every run | Each position has a 1-in-7 chance of being sold per day |
| Runs | 2× per trading day + a weekly Saturday review | 1× per trading day |
| Memory | `analyst/memory/` (lessons, position theses, journal), committed back to the repo after every run | None |
| Cost | $0 extra: uses your Claude plan's usage, no API key | $0 |

Both obey **identical risk limits enforced in code** (`trader/config.py`): ≤10% per position,
≤15 positions, ≤100% gross exposure (no leverage), ≤40% short exposure, shortable/easy-to-borrow
checks, no stocks under $5, and a 15% stop-loss backstop.

## How a run works

```
pg_cron (Supabase) ──dispatch──▶ analyst.yml
  1. trader/brief.py     Alpaca keys ─▶ workspace/brief.md + history/*.csv
  2. claude -p           NO Alpaca keys, no shell: reads brief, playbook, memory,
                         library; WebSearch/WebFetch; writes decisions.json + memory
  3. trader/execute.py   Alpaca keys ─▶ stop-loss backstop, risk checks, market orders,
                         logs to Supabase
  4. git commit          analyst/memory/** pushed back to main
```

The monkey runs through the same `execute.py`, so both agents face identical rules.
Claude never holds the brokerage keys, and nothing it reads on the web can
place an order outside the risk limits.

## Steering the analyst ("training" it)

Claude can't be fine-tuned on a subscription. The analyst gets smarter through what it reads
and what it remembers:

- **`analyst/playbook.md`**: your strategy rules. You edit this, and Claude never does.
- **`analyst/library/`**: drop in PDFs, notes, research, annual reports or articles. The analyst
  reads new ones and logs its takeaways in `library/INDEX.md`.
- **`analyst/memory/`**: Claude's own notebook: `lessons.md` (curated during the Saturday
  review), `positions.md` (thesis + exit plan per holding), `journal/` (one file per run).

## Setup

### 1. Alpaca: two paper accounts
Reset (or create) two paper accounts at <https://app.alpaca.markets>, then add these repo
secrets (**Settings → Secrets and variables → Actions**):

- `ALPACA_ANALYST_KEY`, `ALPACA_ANALYST_SECRET`
- `ALPACA_MONKEY_KEY`, `ALPACA_MONKEY_SECRET`

Give both accounts the same starting balance so the comparison is fair.

### 2. Claude subscription token (no API key)
On your own computer, with Claude Code installed and logged in to your Claude account:

```bash
claude setup-token
```

Save the printed token as the repo secret `CLAUDE_CODE_OAUTH_TOKEN`. It's valid for about a year.

### 3. Supabase
`SUPABASE_URL` / `SUPABASE_KEY` (service role) are already set. Apply `supabase/schema.sql`
(tables) and then `supabase/cron.sql` (schedule). The cron file also retires the old
four-agent triggers.

### 4. Try it
Actions → **Analyst (Claude)** → Run workflow with `dry_run` ticked: everything runs but
no orders are sent. Do the same for **Monkey (random)**.

## Usage budget (Claude Pro)
Each analyst run is one Claude Code session (Sonnet, capped at 60 turns), roughly the
size of a medium coding task. Two a day plus a weekly review fits within Pro, but it
shares the same 5-hour/weekly limits as your normal Claude use. To spend less, delete the
`analyst-pm` cron job. To spend more, add another time slot in `supabase/cron.sql`.

## Layout
```
trader/        config, alpaca client, risk, execute, brief, monkey, snapshot, prompt
analyst/       PROMPT.md, modes/, playbook.md, memory/, library/
supabase/      schema.sql, cron.sql
.github/workflows/  analyst.yml, monkey.yml, snapshot.yml, ci.yml
tests/
```
