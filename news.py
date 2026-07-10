"""
News/sentiment research: Alpaca headlines, Reddit (OAuth + public-JSON
fallback), ApeWisdom/StockTwits retail sentiment, and the Gemini/Groq
research calls that turn all of it into the news_context string fed to the
decision prompt. See _get_news_context for the entry point ai_agent.py uses.
"""
import os
from datetime import datetime, timedelta, timezone

import requests

import config
import alpaca_client as ac
from backends import _gemini_generate, _groq_generate
from store import SUPABASE_URL, _supabase_headers, _notify

REDDIT_CLIENT_ID = os.environ.get("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.environ.get("REDDIT_CLIENT_SECRET", "")


def _reddit_oauth_token(user_agent: str) -> str | None:
    """
    Application-only OAuth token for Reddit's API (client_credentials
    grant). Reddit's public .json endpoints 403 GitHub Actions' datacenter
    IPs outright — confirmed in the run logs: every subreddit, every run,
    since the Reddit feature was added — so the authenticated API is the
    only path that actually works from CI. Requires a (free) registered
    script app: REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET repo secrets.
    Returns None (and the caller falls back to the public endpoint) if the
    secrets aren't configured or the token request fails.
    """
    if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
        return None
    try:
        resp = requests.post(
            "https://www.reddit.com/api/v1/access_token",
            auth=(REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET),
            data={"grant_type": "client_credentials"},
            headers={"User-Agent": user_agent},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("access_token")
    except Exception as e:
        print(f"Reddit OAuth token request failed ({e}); falling back to public endpoint.")
        return None


def _fetch_reddit_posts() -> str:
    """
    Pulls hot posts from stock/trading subreddits — via Reddit's OAuth API
    when REDDIT_CLIENT_ID/REDDIT_CLIENT_SECRET are configured (the only
    path that works from GitHub Actions; see _reddit_oauth_token), else the
    public .json endpoints (works locally, 403s from CI). Returns a
    formatted block of the most-upvoted, non-stickied posts to be prepended
    to the news research prompt as real-time retail sentiment context.

    Best-effort — a Reddit outage or rate-limit should never block a run.
    """
    subreddits = config.AGENT.get("reddit_subreddits", [])
    if not subreddits:
        return ""

    # Not agent-specific — used to be hardcoded to say "hermes" even when
    # Eris (or any future agent) called this.
    user_agent = f"trading-agent-{config.AGENT_ID}/1.0 (paper trading research bot)"
    token = _reddit_oauth_token(user_agent)
    if token:
        base_url = "https://oauth.reddit.com"
        headers = {"User-Agent": user_agent, "Authorization": f"Bearer {token}"}
    elif os.environ.get("GITHUB_ACTIONS") == "true":
        # No OAuth creds and we're on an Actions runner: the public
        # endpoints 403 these IPs 100% of the time, so skip the 5-6 doomed
        # requests per refresh. Retail sentiment still flows from the
        # keyless aggregators (_fetch_retail_sentiment).
        return ""
    else:
        base_url = "https://www.reddit.com"
        headers = {"User-Agent": user_agent}

    lines = []
    for sub in subreddits:
        try:
            resp = requests.get(
                f"{base_url}/r/{sub}/hot.json",
                params={"limit": 8},
                headers=headers,
                timeout=8,
            )
            if not resp.ok:
                print(f"Reddit r/{sub}: HTTP {resp.status_code}, skipping.")
                continue
            posts = resp.json().get("data", {}).get("children", [])
            for post in posts:
                p = post.get("data", {})
                if p.get("stickied"):   # skip mod announcements
                    continue
                title = p.get("title", "").strip()
                score = p.get("score", 0)
                n_comments = p.get("num_comments", 0)
                if title:
                    lines.append(f"r/{sub} | ↑{score} | {n_comments} comments | {title}")
        except Exception as e:
            print(f"Reddit r/{sub} fetch failed ({e}), skipping.")

    if not lines:
        return ""
    return (
        "## Reddit retail sentiment (hot posts right now)\n"
        + "\n".join(lines)
        + "\n"
    )


_SENTIMENT_UA = {"User-Agent": "trading-agent/1.0 (paper trading research bot)"}


def _fetch_apewisdom(filter_name: str, universe_tickers: set) -> str:
    """
    ApeWisdom aggregates ticker mention counts and upvotes across Reddit's
    trading subs (WSB and the rest) — the same underlying signal as scraping
    Reddit directly, already tallied per ticker, one keyless request.
    filter_name: "all-stocks" or "all-crypto". Tickers also in this agent's
    universe get flagged so the research model knows which ones it can act on.
    """
    try:
        resp = requests.get(
            f"https://apewisdom.io/api/v1.0/filter/{filter_name}/page/1",
            headers=_SENTIMENT_UA, timeout=10,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])[:15]
        if not results:
            return ""
        lines = []
        for r in results:
            # ApeWisdom marks crypto tickers with a ".X" suffix ("BTC.X") —
            # confirmed against the live API from the probe workflow. Strip
            # it so universe matching and display use the bare ticker.
            ticker = (r.get("ticker") or "").upper().removesuffix(".X")
            mentions = r.get("mentions") or 0
            prev = r.get("mentions_24h_ago") or 0
            trend = ""
            if prev:
                change = (int(mentions) - int(prev)) / int(prev) * 100
                trend = f", {change:+.0f}% vs 24h ago"
            in_universe = ticker in universe_tickers or f"{ticker}/USD" in universe_tickers
            lines.append(
                f"#{r.get('rank')} {ticker}{' (IN YOUR UNIVERSE)' if in_universe else ''}"
                f" — {mentions} Reddit mentions{trend}, {r.get('upvotes') or 0} upvotes"
            )
        label = "stocks" if filter_name == "all-stocks" else "crypto"
        return (
            f"Reddit ticker-mention leaderboard for {label} (ApeWisdom, aggregated "
            "across trading subreddits, most-mentioned first):\n" + "\n".join(lines)
        )
    except Exception as e:
        print(f"ApeWisdom {filter_name} fetch failed ({e}), skipping.")
        return ""


def _fetch_stocktwits_trending(universe_tickers: set) -> str:
    """Top trending symbols on StockTwits right now — a direct 'what is
    retail watching' signal, one keyless request."""
    try:
        resp = requests.get(
            "https://api.stocktwits.com/api/2/trending/symbols.json",
            headers=_SENTIMENT_UA, timeout=10,
        )
        resp.raise_for_status()
        symbols = resp.json().get("symbols", [])[:20]
        if not symbols:
            return ""
        names = [
            s.get("symbol", "").upper()
            + (" (IN YOUR UNIVERSE)" if s.get("symbol", "").upper() in universe_tickers else "")
            for s in symbols if s.get("symbol")
        ]
        return "Trending symbols on StockTwits right now (most retail chatter first): " + ", ".join(names)
    except Exception as e:
        print(f"StockTwits trending fetch failed ({e}), skipping.")
        return ""


def _fetch_crypto_trending() -> str:
    """CoinGecko's trending-searches list plus the Crypto Fear & Greed index
    — the two standard keyless crypto-sentiment reads. Crypto agents only."""
    parts = []
    try:
        resp = requests.get(
            "https://api.coingecko.com/api/v3/search/trending",
            headers=_SENTIMENT_UA, timeout=10,
        )
        resp.raise_for_status()
        coins = [c.get("item", {}) for c in resp.json().get("coins", [])][:7]
        names = [f"{c.get('symbol', '?').upper()} ({c.get('name', '?')})" for c in coins]
        if names:
            parts.append("Most-searched coins on CoinGecko right now: " + ", ".join(names))
    except Exception as e:
        print(f"CoinGecko trending fetch failed ({e}), skipping.")
    try:
        resp = requests.get("https://api.alternative.me/fng/?limit=1", headers=_SENTIMENT_UA, timeout=10)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        if data:
            parts.append(
                f"Crypto Fear & Greed index: {data[0].get('value')} ({data[0].get('value_classification')})"
            )
    except Exception as e:
        print(f"Fear & Greed fetch failed ({e}), skipping.")
    return "\n".join(parts)


def _fetch_retail_sentiment() -> str:
    """
    Combined retail-sentiment block for the news research prompt. Reddit
    direct (OAuth) if credentials ever get configured, else/plus the keyless
    aggregators above. Only agents with reddit_subreddits configured (the
    sentiment-driven ones — Hermes, Eris) get any of this; Plutus/Helios
    don't trade on retail chatter.
    """
    if not config.AGENT.get("reddit_subreddits"):
        return ""
    universe = set(config.AGENT["universe"])
    has_crypto = any(ac.is_crypto(s) for s in universe)
    # Crypto pairs are "BONK/USD" in the universe; sentiment sources use bare tickers.
    bare = {s.split("/")[0] for s in universe} | universe

    sections = [
        _fetch_reddit_posts(),  # empty unless REDDIT_CLIENT_ID/SECRET work
        _fetch_apewisdom("all-stocks", bare),
    ]
    if has_crypto:
        sections.append(_fetch_apewisdom("all-crypto", bare))
    sections.append(_fetch_stocktwits_trending(bare))
    if has_crypto:
        sections.append(_fetch_crypto_trending())

    sections = [s for s in sections if s]
    if not sections:
        return ""
    return (
        "## Retail sentiment (live, aggregated from Reddit mentions / StockTwits"
        + (" / CoinGecko" if has_crypto else "") + ")\n"
        + "\n\n".join(sections)
        + "\n"
    )


def _trim_to_last_sentence(text: str) -> str:
    """
    Model output that hits its max-token limit gets cut mid-sentence
    ("BAC: No"), which looks broken on the dashboard. If the text doesn't
    end at a sentence/line boundary, trim back to the last complete one.
    """
    text = text.rstrip()
    if not text or text[-1] in ".!?)":
        return text
    # Prefer cutting at the last completed line, then the last sentence end.
    for sep in ("\n", ". "):
        idx = text.rfind(sep)
        if idx > len(text) * 0.5:  # only trim if we keep most of the content
            return text[: idx + (1 if sep == ". " else 0)].rstrip()
    return text


def _fetch_headline_block() -> str:
    """
    Real, timestamped headlines for this agent's universe from Alpaca's News
    API — grounds the research step in actual events instead of letting the
    model fill a template. Empty string if nothing came back.
    """
    items = ac.fetch_news_headlines(config.AGENT["universe"])
    if not items:
        return ""
    lines = []
    for n in items:
        syms = ",".join(n["symbols"][:4])
        when = n["created_at"][:16].replace("T", " ")
        lines.append(f"- [{when} UTC] ({syms}) {n['headline']} — {n['source']}")
    return "Real recent headlines for the portfolio universe (Alpaca News API):\n" + "\n".join(lines)


def _research_news_gemini() -> str:
    """News research via Gemini (all Gemini-backed agents). Uses live
    google_search grounding by default, gated by the agent's
    news_search_grounded config flag (default True).

    Hermes runs with news_search_grounded=False: its Google AI Studio
    project has no Cloud Billing linked, and Grounding with Google Search
    is not part of the free tier — confirmed directly against the API,
    where a grounded call gets 429 RESOURCE_EXHAUSTED immediately (even on
    a brand-new, never-used key) while a plain generateContent call on the
    identical key succeeds. Rather than pay for grounding, Hermes instead
    grounds itself in the real, dated headlines from Alpaca's News API
    (_fetch_headline_block) and Reddit hot posts, both already fetched
    below regardless of this flag, and asks the model to synthesize from
    those plus its training knowledge instead of searching live.

    For agents with reddit_subreddits configured (Hermes), Reddit hot posts are
    prepended so Gemini synthesizes retail sentiment alongside other context."""
    grounded = config.AGENT.get("news_search_grounded", True)
    reddit_block = _fetch_retail_sentiment()
    headline_block = _fetch_headline_block()

    symbols = ", ".join(config.AGENT["universe"])
    if grounded:
        system_prompt = (
            "You are a markets research assistant. Use Google Search to find what is "
            "actually relevant to trading decisions right now. Cover, briefly:\n"
            "- Major market-wide headlines from the last 24-48 hours (Fed/rate "
            "decisions, inflation or jobs data, other major economic releases)\n"
            "- Political developments with plausible market impact: legislation, "
            "elections, regulatory or policy actions, geopolitical events or "
            "conflicts, trade policy\n"
            "- Broader societal or cultural trends that could shift consumer "
            "behavior, sentiment, or demand in specific sectors\n"
            f"- Company-specific news for tickers in this universe: {symbols}. "
            "ONLY mention tickers that actually have notable news — never "
            "enumerate tickers to say they have no news, and never write "
            "per-ticker 'no news' lines. Silence about a ticker means nothing "
            "notable.\n\n"
            "Stay strictly factual and neutral — describe events and their "
            "plausible market relevance only. Never state your own political "
            "opinion or take a side on a political issue. Write 200-300 words as "
            "short plain-text bullet-style lines (no markdown headers, no asterisks). "
            "End with a complete sentence — do not trail off."
        )
    else:
        system_prompt = (
            "You are a markets research assistant. You do not have live web search "
            "this run — base your briefing strictly on the real headlines and retail "
            "sentiment provided below, plus general macro/sector themes from your "
            "training knowledge. Cover, briefly:\n"
            "- Market-wide themes suggested by the provided headlines (Fed/rate "
            "decisions, inflation or jobs data, other major economic releases)\n"
            "- Political or regulatory developments visible in the provided headlines "
            "and their plausible market impact\n"
            f"- Company-specific implications for tickers in this universe: {symbols}, "
            "ONLY if the provided headlines actually mention them — never enumerate "
            "tickers to say they have no news.\n\n"
            "Stay strictly factual and neutral — describe events and their plausible "
            "market relevance only. Never state your own political opinion or take a "
            "side on a political issue. Do not invent specific dated events that "
            "aren't in the provided headlines — general, undated macro context from "
            "training knowledge is fine, fabricated specifics are not. Write 150-250 "
            "words as short plain-text bullet-style lines (no markdown headers, no "
            "asterisks). End with a complete sentence — do not trail off."
        )

    parts = []
    if reddit_block:
        parts.append(
            "Here is real-time retail sentiment data (aggregated Reddit ticker "
            "mentions, StockTwits trending, and crypto sentiment indices where "
            "relevant) to factor into your research:\n\n" + reddit_block
        )
    if headline_block:
        parts.append(headline_block)
    parts.append(
        "Now research current market-relevant news, politics, and societal trends."
        if grounded else
        "Now synthesize a market-relevant news/politics/societal briefing from the above."
    )
    user_message = "\n\n".join(parts)

    text = _gemini_generate(
        system_prompt,
        user_message,
        tools=[{"google_search": {}}] if grounded else None,
        json_mode=False,
        max_output_tokens=1200,
    )
    return _trim_to_last_sentence(text)


def _research_news_groq() -> str:
    """
    News research via Groq (Hermes). Groq doesn't offer live web search,
    so this is a pure text call asking the model to surface relevant market
    context from its training data. The price-history data in the decision
    prompt already provides the quantitative picture; this adds qualitative
    sector/company context the model knows about.
    """
    symbols = ", ".join(config.AGENT["universe"])
    system_prompt = (
        "You are a markets research assistant. Based on your training knowledge, "
        "summarize what is broadly relevant to trading decisions for a portfolio "
        "focused on these tickers: " + symbols + ".\n\n"
        "Cover briefly:\n"
        "- Key macro themes currently affecting markets (rates, inflation, growth)\n"
        "- Sector-level tailwinds or headwinds relevant to the tickers above\n"
        "- Any well-known catalysts or risk events (earnings seasons, regulatory "
        "cycles, product launches) for companies in this universe\n"
        "- General sentiment context for high-beta growth vs. defensive names\n\n"
        "Be concise — 150-200 words, plain-text bullet-style lines. "
        "Never enumerate tickers to say they have no news — only mention a "
        "ticker if you have something concrete about it. "
        "End with a complete sentence — do not trail off."
    )
    # Groq has no live web search, so real headlines from Alpaca's News API
    # are the model's only source of fresh, dated facts — lead with them.
    headline_block = _fetch_headline_block()
    user_message = "Provide a brief market context briefing for the tickers in my universe."
    if headline_block:
        user_message = (
            headline_block
            + "\n\nUsing these real headlines as your primary source of fresh "
            "information, provide a brief market context briefing for the "
            "tickers in my universe. Cite the headline events you rely on."
        )
    text = _groq_generate(
        system_prompt,
        user_message,
        json_mode=False,
        max_output_tokens=700,
    )
    return _trim_to_last_sentence(text)


def _research_news() -> str:
    """Dispatch news research to the right backend based on agent config."""
    if config.AGENT.get("ai_backend") == "groq":
        return _research_news_groq()
    return _research_news_gemini()


def _alert_stale_news(age_minutes: float, cached: dict):
    """
    Notifies (throttled to once per 6h via agent_news_context.
    last_stale_alert_at) when the news briefing being served is well past
    its refresh interval AND a refresh attempt just failed. Exists because
    exactly this happened silently for 9 days: Plutus/Helios' grounded news
    call started 429ing on 2026-06-30 and every run after that quietly fell
    back to the June-30 cache with nothing surfacing the degradation.
    Best-effort — never blocks the run.
    """
    try:
        if age_minutes < 3 * config.AGENT["news_refresh_minutes"]:
            return
        last_alert = cached.get("last_stale_alert_at")
        if last_alert:
            last_alert_at = datetime.fromisoformat(last_alert.replace("Z", "+00:00"))
            if (datetime.now(timezone.utc) - last_alert_at) < timedelta(hours=6):
                return
        _notify(
            "News briefing is stale",
            f"The news refresh keeps failing — the briefing in use is {age_minutes / 60:.1f}h old "
            f"(refresh interval: {config.AGENT['news_refresh_minutes']} min). Check the run logs.",
        )
        requests.patch(
            f"{SUPABASE_URL}/rest/v1/agent_news_context",
            headers={**_supabase_headers(), "Prefer": "return=minimal"},
            params={"agent_id": f"eq.{config.AGENT_ID}"},
            json={"last_stale_alert_at": datetime.now(timezone.utc).isoformat()},
            timeout=15,
        ).raise_for_status()
    except Exception as e:
        print(f"Could not send/record stale-news alert ({e}) — non-fatal.")


def _get_news_context() -> tuple[str | None, float | None]:
    """
    Returns (briefing, age_minutes) — a cached news/politics/society
    briefing plus how old it is, refreshing it via _research_news() if the
    cache is missing or older than this agent's news_refresh_minutes
    setting. Cached in Supabase (agent_news_context, one row per agent_id)
    so a fast cron doesn't re-search every run, and so each agent's refresh
    cadence doesn't collide with the other's. The age travels with the
    content so the decision prompt can say honestly how fresh the briefing
    is — a model told "refreshed every 30 min" will treat a 9-day-old
    briefing as current fact, which is exactly what happened to
    Plutus/Helios between 2026-06-30 and 2026-07-09.

    Never blocks a trading run: any failure here falls back to the stale
    cache (with its real age), or (None, None), rather than raising — a bad
    news search is not a reason to skip a whole trade decision.
    """
    cached = None
    cached_age_minutes = None
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/agent_news_context",
            headers=_supabase_headers(),
            params={"agent_id": f"eq.{config.AGENT_ID}", "select": "content,updated_at,last_stale_alert_at"},
            timeout=15,
        )
        resp.raise_for_status()
        rows = resp.json()
        if rows:
            cached = rows[0]
    except Exception as e:
        print(f"Could not load cached news context from Supabase ({e}).")

    if cached and cached.get("updated_at"):
        try:
            updated_at = datetime.fromisoformat(cached["updated_at"].replace("Z", "+00:00"))
            cached_age_minutes = (datetime.now(timezone.utc) - updated_at).total_seconds() / 60
            if cached_age_minutes < config.AGENT["news_refresh_minutes"]:
                return cached.get("content"), cached_age_minutes
        except Exception as e:
            print(f"Could not parse cached news context timestamp ({e}), refreshing.")

    try:
        fresh = _research_news()
        # Upsert, not update-only: a PATCH silently matches zero rows and
        # no-ops for any agent that has never had a cache row (e.g. a newly
        # added agent), which meant that agent could never get a row created
        # and would re-attempt this expensive google_search-grounded call
        # every single run, with no fallback ever available on failure.
        requests.post(
            f"{SUPABASE_URL}/rest/v1/agent_news_context",
            headers={**_supabase_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
            params={"on_conflict": "agent_id"},
            json={
                "agent_id": config.AGENT_ID,
                "content": fresh,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            timeout=30,
        ).raise_for_status()
        return fresh, 0.0
    except Exception as e:
        print(f"Could not refresh news context ({e}), falling back to stale cache if any.")
        if cached and cached_age_minutes is not None:
            _alert_stale_news(cached_age_minutes, cached)
        return (cached.get("content"), cached_age_minutes) if cached else (None, None)
