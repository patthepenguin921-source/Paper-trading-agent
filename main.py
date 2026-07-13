"""
Entry point. Run on a schedule by .github/workflows/trade.yml (and the
analogous trade_helios.yml/trade_eris.yml/crypto_afterhours_trade.yml).

Stocks & ETFs trade equity-market hours only, but an agent can also hold
crypto (24/7 on Alpaca — see alpaca_client.is_crypto()); paper trading only
(no real money, ever — see alpaca_client.py). The day is split into three
phases (see schedule.market_phase(), boundaries fixed in ET so they're
correct across the EST/EDT switch with no manual adjustment):

  - "quiet" (roughly 5pm-8:30am ET, plus all weekend): no equity activity —
    no Gemini call, no Alpaca call, no Supabase write for an agent with no
    crypto in its universe. An agent that does hold crypto (currently only
    Eris) instead runs ai_agent.run_crypto_afterhours() here: a real,
    crypto-only decision cycle, not just a check-in. The Supabase-triggered
    dispatch that drives trade_*.yml is itself scoped to market hours, so in
    practice this branch is reached on a real cadence via
    crypto_afterhours_trade.yml's own independent schedule, not that one.
  - "pre_market_review" (8:30-8:45am ET, once a day): reviews yesterday's
    activity and current portfolio, gets one chance to queue a buy ahead
    of the open. Guarded by a real trading-day check (minutes_until_next_
    open) so a holiday/weekend morning that happens to look like 8:30am ET
    doesn't trigger a real review for a session that isn't actually
    starting soon.
  - "active_window" (9:15am-5pm ET): the regular intraday cadence — still
    double-checks Alpaca's real market-open status before spending a
    Gemini call, same as before.
"""
import alpaca_client as ac
import ai_agent
import config


def main():
    print(f"Agent: {config.AGENT['label']} ({config.AGENT_ID})")

    phase = ai_agent.market_phase()
    print(f"Phase: {phase}")

    if phase == "quiet":
        if not any(ac.is_crypto(s) for s in config.AGENT["universe"]):
            print("Overnight pause — doing nothing this tick.")
            return
        if ai_agent.should_throttle_cadence():
            print("A crypto off-hours decision run already happened within the intended cadence — skipping duplicate cron tick.")
            return
        print("Equity markets are closed, but this agent trades crypto 24/7 — running the off-hours crypto-only cycle.")
        ai_agent.run_crypto_afterhours()
        return

    if phase == "pre_market_review":
        minutes_to_open = ac.minutes_until_next_open()
        if minutes_to_open > 120:
            print(f"Looks like 8:30am ET, but the next real session is {minutes_to_open:.0f} min away "
                  "(holiday/weekend) — skipping the pre-market review.")
            return
        if ai_agent.should_throttle_cadence():
            print("Pre-market review already ran within this window — skipping duplicate cron tick.")
            return
        print("Running the once-daily pre-market review.")
        ai_agent.run_premarket_review()
        return

    # phase == "active_window"
    if not ac.is_market_open():
        print("Market is closed (holiday/weekend, or just outside actual session hours). Logging a check-in.")
        ai_agent.log_idle(market_open=False)
        return

    if ai_agent.should_throttle_cadence():
        print("A decision run already happened within the intended ~15-minute cadence — skipping duplicate cron tick.")
        return

    print("Market is open — running AI agent.")
    ai_agent.run()
    print("Run complete.")


if __name__ == "__main__":
    main()
