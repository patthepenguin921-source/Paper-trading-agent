import os

# --------------------------------------------------------------------------
# Per-agent definitions
# --------------------------------------------------------------------------
# Four independent agents share this one codebase but always run as separate
# GitHub Actions jobs (each setting AGENT_ID + its own Alpaca/AI secrets for
# that job only — see .github/workflows/). They never share a brokerage
# account, a risk budget, or a Supabase cache row. AGENT_ID picks which
# entry in AGENTS below is active for a given run.

# Plutus: the original agent. Maximize total returns, willing to take real
# risk to do it (paper money only) — long or short.
PLUTUS_UNIVERSE = [
    # Broad-market / sector ETFs
    "SPY", "QQQ", "DIA", "IWM", "VTI", "VOO", "XLK", "XLF", "XLE", "XLV",
    # Large-cap tech
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO", "ORCL", "CRM",
    # Other large-cap / liquid names across sectors
    "JPM", "V", "MA", "UNH", "HD", "PG", "KO", "PEP", "WMT", "DIS",
    "BAC", "XOM", "CVX", "JNJ", "ABBV", "COST", "MCD", "NKE", "ADBE", "NFLX",
]

# Helios: long-horizon, capital-preservation focused. Broad index and bond/
# treasury exposure plus lower-volatility dividend blue chips. Deliberately
# excludes the higher-beta growth/momentum names Plutus trades.
HELIOS_UNIVERSE = [
    # Broad market
    "SPY", "VOO", "VTI", "DIA",
    # Bonds / treasuries (capital preservation ballast)
    "BND", "AGG", "TLT", "SHY",
    # Defensive sectors
    "XLP", "XLV", "XLU",
    # Dividend-paying blue chips
    "JNJ", "PG", "KO", "PEP", "MCD", "WMT", "JPM", "V", "MA", "HD", "UNH", "COST",
]

# Hermes: news-catalyst day trader. Focuses on liquid large-cap stocks across
# sectors that react meaningfully to earnings, regulatory decisions, macro
# data releases, and other discrete news catalysts, and trades them
# intraday-to-multiday for short-term gains — both long and short. Uses
# Gemini with Google Search grounding for news research (Groq-hosted
# Llama-3.3-70b as fallback) — news context is the primary input, price
# history is secondary. Starts at $10k (displayed as $100k equivalent).
HERMES_UNIVERSE = [
    # Mega-cap tech (frequent earnings/product/regulatory news)
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
    # Semiconductors (supply chain, export controls, earnings-driven)
    "AMD", "INTC", "AVGO", "QCOM", "MU",
    # Financials (rate decisions, regulatory, earnings)
    "JPM", "GS", "BAC", "MS", "C", "V", "MA",
    # Healthcare / pharma (FDA catalysts, trial results, drug pricing)
    "JNJ", "PFE", "MRNA", "ABBV", "LLY", "BMY",
    # Energy (oil price, geopolitical, supply/demand news)
    "XOM", "CVX", "OXY", "SLB",
    # Retail / consumer (CPI, consumer confidence, earnings)
    "WMT", "COST", "TGT", "HD", "NKE", "MCD",
    # High-beta growth (heavily news-driven price swings)
    "COIN", "PLTR", "SQ", "SHOP", "RBLX",
    # Sector ETFs (macro or sector-wide news plays)
    "SPY", "QQQ", "XLK", "XLF", "XLE", "XLV",
]

# Eris: chaos/discord — meme stocks and memecoins. Trades two very different
# asset classes: regular equities with a history of retail-driven, sentiment-
# fueled volatility (real ETFs/stocks, shortable, subject to PDT rules), and
# crypto pairs via Alpaca's separate crypto API (alpaca_client.is_crypto()
# tells them apart by the "/" in the symbol — e.g. "BTC/USD"). Crypto is
# spot-only on Alpaca: no margin, no shorting, ever — enforced in code
# regardless of the allow_short flag below. No fundamentals anchor either
# side of this universe; retail/social sentiment is doing most of the work,
# which is why Reddit coverage below leans crypto- and meme-stock-specific
# subs instead of the general trading ones the other agents use.
ERIS_MEME_STOCKS = [
    "GME", "AMC", "PLTR", "SOFI", "RIVN", "LCID", "COIN", "MSTR", "HOOD",
    "DJT", "BB", "NOK", "CVNA", "IONQ", "RKLB",
]
# Confirmed tradable against Alpaca's live /v2/assets?asset_class=crypto via
# scripts/account_and_crypto_check.py (2026-07-03) — 73 pairs came back;
# this keeps only the USD-quoted ones (dropping the redundant USDC/USDT/BTC-
# quoted duplicates of the same underlying coin) and drops pure stablecoins
# (USDC/USDT/USDG/PAXG), which have ~zero volatility and no sentiment-driven
# opportunity, i.e. exactly the opposite of what this agent is for. Re-run
# that script periodically — Alpaca's crypto lineup changes.
ERIS_MEMECOINS = [
    # Actual memecoins — the purest version of this agent's thesis
    "DOGE/USD", "SHIB/USD", "PEPE/USD", "BONK/USD", "WIF/USD", "TRUMP/USD",
    # Major/blue-chip crypto — still sentiment- and momentum-driven, still
    # no earnings/fundamentals to anchor to, just larger and less volatile
    "BTC/USD", "ETH/USD", "SOL/USD", "XRP/USD", "ADA/USD", "AVAX/USD",
    "DOT/USD", "LINK/USD", "LTC/USD", "BCH/USD",
    # DeFi / altcoins — smaller-cap, still capable of fast sentiment moves
    "UNI/USD", "AAVE/USD", "CRV/USD", "SUSHI/USD", "YFI/USD", "LDO/USD",
    "GRT/USD", "ONDO/USD", "ARB/USD", "POL/USD", "SKY/USD", "RENDER/USD",
    "FIL/USD", "BAT/USD", "XTZ/USD", "HYPE/USD",
]
ERIS_UNIVERSE = ERIS_MEME_STOCKS + ERIS_MEMECOINS

# Both Plutus and Helios paper accounts started at this balance.
STARTING_EQUITY = 100_000.0

AGENTS = {
    "plutus": {
        "label": "Plutus",
        "universe": PLUTUS_UNIVERSE,
        # Switched from gemini-2.5-flash: that model's free-tier allocation on
        # this project turned out to be a hard 20 requests/day (confirmed via
        # the actual 429 response body — "limit: 20, model: gemini-2.5-flash"
        # — well below the 100-1500/day figures generic docs/guides cite, and
        # nowhere near enough even at a 15-minute decision cadence). Then
        # moved off gemini-2.5-flash-lite too, once AI Studio's Rate Limit
        # page (confirmed visually, not just from a 429 body) showed it was
        # ALSO capped at 20 RPD on this project — same ceiling, different
        # model name. gemini-3.1-flash-lite carries a 500 RPD / 15 RPM quota
        # on the same project, confirmed via the same Rate Limit page, which
        # comfortably covers even 15-minute polling across market hours.
        "gemini_model": "gemini-3.1-flash-lite",
        "ai_backend": "gemini",
        "instructions_file": "instructions.md",
        # Grounding with Google Search is NOT available on this project's
        # free tier (no Cloud Billing linked) — the grounded news call 429s
        # instantly, and did so on every single run from 2026-06-30 to
        # 2026-07-09, burning ~30s of retries per run and silently serving
        # the model a June-30 cached briefing labeled as fresh. Same
        # limitation Hermes/Eris hit and worked around from day one: ground
        # the briefing in real Alpaca News API headlines instead.
        "news_search_grounded": False,
        # No hard cap on open positions — removed per Carter's request
        # (2026-06-30). Position sizing (position_size_pct_min/_max) and
        # max new buys per run remain the real risk controls; an open-
        # position count limit was redundant with those and just blocked
        # good opportunities once the portfolio happened to be diversified.
        "max_open_positions": None,
        "max_new_buys_per_run": 3,
        # A range, not a fixed number — the model picks where in this band
        # to size each buy based on its own conviction (see size_pct in the
        # decision schema in ai_agent.py). Code only clamps to the range;
        # it doesn't pick the number. Replaces the old single
        # position_size_pct, which forced every buy to the same fraction
        # of equity regardless of how strongly the model felt about it,
        # producing artificially even position sizes across the portfolio.
        "position_size_pct_min": 0.04,
        "position_size_pct_max": 0.18,
        # 0 = no hard cash-floor cap. It can deploy all of its cash if it has
        # a real reason to — the equity-floor goal (stay above
        # STARTING_EQUITY) is the actual guardrail now, weighed by the model
        # itself rather than blocked by code.
        "min_cash_buffer_pct": 0.0,
        # Short selling: "willing to take real risk" already describes
        # Plutus, and a short is just a bet in the other direction — no
        # reason to leave that tool out. Enforced in code (ai_agent
        # rejects "short"/"cover" unless this flag is set), same mechanism
        # as Hermes.
        "allow_short": True,
        "news_refresh_minutes": 30,
        "starting_equity": 100_000.0,
        # Stop-loss BACKSTOP, not a trading rule: any position whose
        # unrealized loss exceeds this fraction is closed at market at the
        # start of the next run, before the model is even called. Judgment
        # is still expected to exit losers long before this fires (the
        # 2026-07-09 profitability review found losers being held while
        # winners were cut at +0.5%) — this only caps the tail so a single
        # runaway loser can't quietly eat the account between decisions.
        "max_position_loss_pct": 0.08,
        # Daily loss CIRCUIT BREAKER, the account-level sibling of the
        # per-position backstop above: if equity has fallen more than this
        # fraction below the day's first logged reading, new buys/shorts are
        # rejected in code for the rest of the trading day (sells, covers,
        # and cancels still work — the agent can and should keep managing
        # its way out). Motivated by Hermes' 2026-07-07: −6.2% realized in
        # a single session across 19 trades, most of them opened *after*
        # the day had already gone badly. A bad day should end in damage
        # control, not in doubling down.
        "max_daily_loss_pct": 0.05,
        # How long an unfilled order can sit before the start-of-run sweep
        # cancels it (see alpaca_client.cancel_stale_open_orders).
        "stale_order_max_age_hours": 20.0,
        # No cap on open-position count or per-sector concentration was
        # legally possible to hit before this: sizing alone (up to 18% of
        # equity per buy) could still land Plutus fully concentrated in one
        # correlated cluster (e.g. mega-cap tech) with no code stopping it.
        # See sectors.py — this caps aggregate exposure (held + pending) to
        # any single sector bucket as a fraction of equity.
        "max_sector_concentration_pct": 0.40,
    },
    "helios": {
        "label": "Helios",
        "universe": HELIOS_UNIVERSE,
        "gemini_model": "gemini-3.1-flash-lite",
        "ai_backend": "gemini",
        "instructions_file": "instructions_helios.md",
        # Same free-tier grounding limitation as Plutus — see the comment
        # there. Headline-grounded synthesis instead of live search.
        "news_search_grounded": False,
        "max_open_positions": None,
        "max_new_buys_per_run": 2,
        # Tighter range than Plutus, consistent with capital-preservation —
        # but still a range the model sizes within, not one fixed number.
        "position_size_pct_min": 0.03,
        "position_size_pct_max": 0.10,
        "min_cash_buffer_pct": 0.0,
        # Short selling is available here too now — instructions_helios.md
        # frames it as a defensive/hedging tool consistent with Helios'
        # capital-preservation mandate, not an invitation to trade more.
        "allow_short": True,
        "news_refresh_minutes": 180,
        "starting_equity": 100_000.0,
        # Tightest backstop of the four — capital preservation is the whole
        # mandate, and Helios' low-volatility universe should never see a
        # position this far underwater without something being truly wrong.
        "max_position_loss_pct": 0.06,
        # Tightest daily breaker of the four — a capital-preservation book
        # down 3% in one day is already a five-alarm event; adding to it is
        # never the right response.
        "max_daily_loss_pct": 0.03,
        "stale_order_max_age_hours": 20.0,
        # Tightest of the four, consistent with the capital-preservation
        # mandate — see sectors.py and the comment on Plutus' equivalent key.
        "max_sector_concentration_pct": 0.30,
    },
    "hermes": {
        "label": "Hermes",
        "universe": HERMES_UNIVERSE,
        # Uses Gemini on its own isolated Google AI Studio project so its
        # quota is completely separate from Plutus/Helios. Groq
        # (GROQ_API_KEY in the workflow) is the fallback if Gemini quota is
        # exhausted.
        "ai_backend": "gemini",
        "gemini_model": "gemini-3.1-flash-lite",
        "instructions_file": "instructions_hermes.md",
        # This project has no Cloud Billing linked, and Grounding with
        # Google Search isn't part of the Gemini free tier — confirmed
        # against the live API: a grounded call 429s immediately even on a
        # brand-new key, while a plain call on the same key succeeds. Free
        # workaround (see _research_news_gemini): skip the google_search
        # tool and ground the news briefing in real Alpaca News API
        # headlines + Reddit sentiment instead of live search.
        "news_search_grounded": False,
        "max_open_positions": None,
        # No cap on new positions per run — day trading means acting on
        # every genuine catalyst/setup a run finds, not just the first two.
        # size_pct range + available cash/margin are the real risk controls.
        "max_new_buys_per_run": None,
        # Wider than before and wider than Plutus's max — day trading with a
        # tight hold period means conviction should translate into size, not
        # just into being right more often. Still a range the model sizes
        # within based on its own conviction, not a fixed number.
        "position_size_pct_min": 0.05,
        "position_size_pct_max": 0.25,
        "min_cash_buffer_pct": 0.0,
        # Fractional/notional orders: Alpaca supports notional market orders
        # (e.g. "buy $500 of NVDA") which fills fractional shares automatically.
        # Enabled for Hermes because its $10k equity makes whole-share rounding
        # waste a meaningful % of each position. Only applies to market BUYS —
        # limit orders and shorts still use integer qty (Alpaca doesn't support
        # fractional/notional short selling at all).
        "use_notional": True,
        # Short selling: Hermes can profit from names it expects to drop, not
        # just ones it expects to rise. Enforced in code (ai_agent._enforce_caps
        # checks this flag before allowing a "short" decision) — Plutus/Helios
        # leave this unset and stay long-only regardless of what the model says.
        "allow_short": True,
        # Real-time last-trade/bid-ask quotes merged into the watchlist context
        # (ai_agent._build_context), on top of the daily-bar history every agent
        # gets. A day trader reasoning only from yesterday's close is missing
        # today's actual move and can't set a sane limit price — this closes
        # that gap. Plutus/Helios don't need it at their holding period.
        "use_live_quotes": True,
        "news_refresh_minutes": 15,
        # Reddit subreddits to scrape for retail sentiment on each news refresh.
        # Hot posts are prepended to the Gemini news research prompt so the model
        # can factor in what retail traders are actually talking about right now.
        "reddit_subreddits": ["daytrading", "wallstreetbets", "stocks", "StockMarket", "options"],
        # Hermes paper account started at $10k (not $100k like Plutus/Helios).
        # The dashboard shows its real $10k-based figures rather than
        # scaling them up to look like a $100k account.
        "starting_equity": 10_000.0,
        # Tight backstop for a day trader: at an intraday-to-a-few-days
        # holding period, a position 5% underwater is a thesis that already
        # failed. Judgment should exit far earlier; this caps the tail.
        "max_position_loss_pct": 0.05,
        # The agent this breaker was designed around: July 7 was −6.2% in
        # one session, with new shorts still being opened after −4%. At 5%
        # the day would have ended in position management instead.
        "max_daily_loss_pct": 0.05,
        # Day-trading horizon: an unfilled limit order from 8+ hours ago is
        # working a thesis from a different session. The 20h default the
        # other agents use let stale GTC orders block a symbol (and its
        # committed cash) for most of a trading day.
        "stale_order_max_age_hours": 8.0,
        # The concrete scenario this cap exists for (see sectors.py): at 25%
        # max sizing, Hermes could otherwise legally end up 100% in four
        # semiconductor stocks that all move together.
        "max_sector_concentration_pct": 0.40,
    },
    "eris": {
        "label": "Eris",
        "universe": ERIS_UNIVERSE,
        "ai_backend": "gemini",
        "gemini_model": "gemini-3.1-flash-lite",
        "instructions_file": "instructions_eris.md",
        # Same free-tier grounding limitation as Hermes (no Cloud Billing on
        # this project) — ground in real Alpaca News headlines + Reddit
        # sentiment instead of live search. See _research_news_gemini.
        "news_search_grounded": False,
        "max_open_positions": None,
        # No cap on new positions per run, same reasoning as Hermes — the
        # position-sizing range below is the real risk control, and a
        # sentiment-driven universe like this one produces opportunities in
        # bursts, not evenly spaced out.
        "max_new_buys_per_run": None,
        # Narrower than Hermes despite the uncapped trade count — memecoins
        # and meme stocks carry real tail risk (a memecoin can go to zero;
        # a meme stock can gap 50% overnight on no fundamentals at all), so
        # conviction should still translate into more trades before it
        # translates into bigger ones.
        "position_size_pct_min": 0.03,
        "position_size_pct_max": 0.15,
        "min_cash_buffer_pct": 0.0,
        # Essential here, not just a nice-to-have: crypto needs fractional
        # sizing to be usable at all (nobody's buying a whole BTC), and meme
        # stocks benefit from it the same way Hermes does. Only applies to
        # market buys — see alpaca_client.py for how limit orders get
        # fractional crypto qty a different way.
        "use_notional": True,
        # Applies to meme stocks only — crypto shorting is rejected in code
        # regardless of this flag (Alpaca crypto is spot-only, no margin).
        # See ai_agent._enforce_caps and alpaca_client.is_crypto().
        "allow_short": True,
        # Even more essential than for Hermes: memecoin prices move fast
        # and daily bars alone would leave the model reasoning from a stale
        # close on something that can move double digits in an hour.
        "use_live_quotes": True,
        "news_refresh_minutes": 15,
        # Crypto- and meme-stock-specific communities rather than the
        # general trading subs Hermes uses — this is where memecoin/meme-
        # stock sentiment actually originates.
        "reddit_subreddits": [
            "wallstreetbets", "CryptoCurrency", "SatoshiStreetBets",
            "CryptoMoonShots", "dogecoin", "pennystocks",
        ],
        # Unlike Hermes, Eris' paper account started at the standard $100k
        # (confirmed against the live account via
        # scripts/account_and_crypto_check.py, 2026-07-03 — it was wrongly
        # assumed to be $10k like Hermes when this agent was first added,
        # which made the dashboard display $1,000,000 after multiplying by
        # a display_scale that should never have been set). No display
        # scaling needed — same scale as Plutus/Helios.
        "starting_equity": 100_000.0,
        # Loosest backstop of the four: memecoins routinely swing 10%+ on
        # noise, and a tighter cap would just stop this agent out of every
        # position it takes. This is strictly the "a memecoin is collapsing
        # and no run has caught it yet" disaster brake.
        "max_position_loss_pct": 0.10,
        # Loosest daily breaker, same reasoning as its loose per-position
        # backstop: memecoins swing hard on noise and a portfolio of them
        # can easily be down 5% at lunch and up by the close. This only
        # stops a genuinely broken day, not a normal volatile one.
        "max_daily_loss_pct": 0.07,
        # Same day-trading reasoning as Hermes.
        "stale_order_max_age_hours": 8.0,
        # Tighter than Plutus/Hermes despite Eris' otherwise loosest risk
        # profile: every crypto pair buckets into one "Crypto" sector (see
        # sectors.py), so this cap is the main thing standing between
        # "diversified across memecoins" and "one leveraged bet on crypto
        # sentiment broadly" — worth erring tighter here specifically.
        "max_sector_concentration_pct": 0.35,
    },
}

AGENT_ID = os.environ.get("AGENT_ID", "plutus")


def _load_dynamic_agent(agent_id: str) -> dict:
    """
    Agents created through the dashboard's "Add agent" flow aren't hardcoded
    above — they live in the `agents` Supabase table instead, so adding one
    doesn't require touching this file or redeploying. Only called when
    AGENT_ID isn't one of the hardcoded entries in AGENTS.

    Unlike instructions (which fall back to a local file if Supabase is
    unreachable), there's no local fallback here — a dynamic agent only
    exists in Supabase, so a failed lookup is a real failure, not something
    to silently paper over.
    """
    import requests  # local import: keep this off the hot path for the two hardcoded agents

    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        raise ValueError(
            f"Unknown AGENT_ID '{agent_id}' (not one of {list(AGENTS)}), and "
            "SUPABASE_URL/SUPABASE_KEY aren't set to look it up dynamically."
        )

    resp = requests.get(
        f"{supabase_url}/rest/v1/agents",
        headers={"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"},
        params={"id": f"eq.{agent_id}", "active": "eq.true", "select": "*"},
        timeout=15,
    )
    resp.raise_for_status()
    rows = resp.json()
    if not rows:
        raise ValueError(
            f"Unknown AGENT_ID '{agent_id}' — not hardcoded in config.py and no "
            "active row for it in the agents table."
        )
    row = rows[0]
    return {
        "label": row["label"],
        "universe": row["universe"],
        "ai_backend": row.get("ai_backend") or "gemini",
        "gemini_model": row.get("gemini_model") or "gemini-3.1-flash-lite",
        "groq_model": row.get("groq_model") or "llama-3.3-70b-versatile",
        # Dynamic agents have no local .md fallback — _load_instructions()
        # requires the Supabase agent_instructions row to exist for these.
        "instructions_file": None,
        "max_open_positions": None,
        "max_new_buys_per_run": int(row.get("max_new_buys_per_run", 2)),
        "position_size_pct_min": float(row.get("position_size_pct_min", 0.04)),
        "position_size_pct_max": float(row.get("position_size_pct_max", 0.15)),
        "min_cash_buffer_pct": float(row.get("min_cash_buffer_pct", 0.0)),
        "news_refresh_minutes": int(row.get("news_refresh_minutes", 60)),
        "starting_equity": float(row.get("starting_equity", 100_000.0)),
        "display_scale": int(row.get("display_scale", 1)),
        "max_position_loss_pct": (
            float(row["max_position_loss_pct"]) if row.get("max_position_loss_pct") else 0.08
        ),
        "max_daily_loss_pct": (
            float(row["max_daily_loss_pct"]) if row.get("max_daily_loss_pct") else 0.05
        ),
        "stale_order_max_age_hours": float(row.get("stale_order_max_age_hours") or 20.0),
        "max_sector_concentration_pct": (
            float(row["max_sector_concentration_pct"]) if row.get("max_sector_concentration_pct") else 0.40
        ),
    }


if AGENT_ID in AGENTS:
    AGENT = AGENTS[AGENT_ID]
else:
    AGENT = _load_dynamic_agent(AGENT_ID)
    AGENTS[AGENT_ID] = AGENT

# --------------------------------------------------------------------------
# Settings shared by every agent
# --------------------------------------------------------------------------
LOOKBACK_DAYS = 60          # days of price history shown to the agent per symbol (60 needed for SMA-50)

# Push notifications — fired on executed trades and on run failures.
NOTIFY_URL = "https://trading-agent-dashboard-mu.vercel.app/api/notify"

