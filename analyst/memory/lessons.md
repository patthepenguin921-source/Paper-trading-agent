# Lessons learned

Curated by the analyst. It's rewritten during each weekly review, so keep it
short and evidence-backed.

_(Week 2 review, 2026-11-14. One closed trade (ABNB), two open (UNH, ORCL short).
Still a small sample -- treat anything below without multiple data points as a
working hypothesis, not settled doctrine.)_

- **First closed trade: ABNB PEAD, 5 days held, ~-4.4%.** Bought 2026-11-06 ~190.46 on a
  genuine Q3 beat-and-raise gap; sold 2026-11-11 ~182 when price traded back inside the
  unfilled gap (playbook A's precise invalidation) after four straight weak sessions.
  Fundamentals never broke -- analysts were still raising price targets the same week I
  exited -- so this was a clean stop-exit on a failed technical setup, not a bad-news
  trade. Write the playbook A exit plan around the actual gap boundary (prior session's
  high/low), not a round-number soft stop -- it's a more precise, less arguable
  invalidation and made this exit easy to act on from intraday data.
- **A genuine earnings beat is not sufficient for a playbook A long -- the gap still has
  to hold.** CSCO (2026-11-13): strongest rev/EPS growth in 15 years, beat and raised,
  yet fell -6.3% because the market judged the *quality* of the beat as weak (250bps
  non-GAAP gross margin decline, soft Q2 guide) and three banks cut price targets same
  day. A beat that gaps down is closer to a broken-story signal than a PEAD setup, even
  without a guidance cut -- always check the stock actually gapped up *and held it*.
- **Credit-vs-growth divergence correctly separated a factor unwind from a systemic
  correction, two weeks running.** HYG/LQD stayed firm all week (RSI ~52-76, roughly
  flat-to-above 50d) while QQQ/SMH broke hard (QQQ now slightly below its own 200d,
  SMH -13% below its 50d). Read this as "AI/semis factor unwind," not "broad bear
  market," and stayed net long in unrelated sectors (UNH) instead of de-risking
  everywhere. Still check this divergence every run -- HYG's vs_sma50 turned slightly
  negative (-0.26%) for the first time this week, worth watching for a genuine crack.
- **Don't credit cash with alpha -- and the math now backs this up precisely.** Account
  return since inception (-0.12%) is almost exactly explained by the three trades made
  (ABNB -4.4% on 5% size, UNH +3% on 6% size, ORCL short -2% on 4% size netting to
  roughly -0.12% of equity) -- cash itself contributed ~zero. The account still beat SPY
  (-0.12% vs -1.62%) only because the index fell further, not because of stock-picking
  edge. Keep separating "beat the market" from "found an edge" -- they're different
  claims and only closed-trade expectancy proves the second one.
- **Patience on short entries validated: passing on premature shorts and premature
  reclaims both paid off the same week.** Waited out ORCL/NOW/CAT making new lows before
  shorting (playbook D requires a failed rally, not a flush) -- ORCL's bounce stalling
  below its 50d and rolling over became the account's first short (2026-11-13). Separately,
  the QCOM/TXN/AVGO/AMD "reclaim" from 11-11/11-12 fully reversed on 11-13, confirming
  that one calendar session of relative strength is noise until it survives a second,
  independent session. Two different disciplines (wait for failed rally; wait for a
  second session), both vindicated in the same week.
- **First short (ORCL) was entered on a bounce that stalled below resistance, not a
  textbook reclaim-then-fail of the 50d** -- the stock never got above its 50d (closest
  -6.1% below) before rolling over. Backed by a genuine, worsening fundamental catalyst
  (blew through its own $20B capital-raise cap within 5 days, S&P downgrade to BBB-), so
  treated as meeting playbook D's "failed rally, not a flush" bar. One week in: -2.1% on
  a small bounce, well inside the stop, no verdict yet -- still the trade to watch to
  settle whether "stalls below resistance" is as reliable an entry as a true
  reclaim-then-fail.
- **A real, confirmed catalyst doesn't override the "don't chase" rule by itself.** AMD
  jumped on a genuine Google Cloud EPYC-chip win, but had already run ~26% in two days
  with RSI back to 47 before I could act -- passed. A catalyst explains *why* a stock
  moved, not that the entry price is still good; still need a pullback or a confirmed
  hold above resistance.
- **A scandal/governance headline on a name you don't own is not an automatic short --
  and even after it resolves, a settled story still isn't a short until price action
  confirms it.** NVDA's CEO scandal (Jensen Huang resignation) gave two separate,
  independent disqualifiers at two different times: an unresolved binary first, then an
  accelerating flush (not a failed rally) after it resolved. Keep checking both
  conditions independently rather than treating "the news finally happened" as a green
  light by itself.
- **Confidence scores are only being recorded inconsistently.** Only the ORCL short
  (0.58) has an explicit numeric confidence tagged in the journal; ABNB/UNH entries
  didn't get one. Can't assess calibration without several tagged data points -- tag
  every new trade with an explicit confidence score going forward, not just the
  playbook letter, so there's something to grade in a few weeks.
- **First live trades sized at the low end of their tier on purpose** (ABNB 5%, UNH 6%,
  both "solid" tier capped near the bottom) to de-risk the first real test of the
  process. Reasonable for trade #1-2; revisit sizing once there's a longer track record,
  but no reason yet to size up given only one closed trade (a loss) exists.
- **Macro note for next week: bond market now pricing Fed hikes for Dec/Jan**, not cuts
  (per 2026-11-14 coverage), with the 10Y having touched 5% intraday on 11-13 -- a new,
  explicit hawkish repricing on top of the existing AI/semis factor unwind. If this
  broadens into credit (HYG cracking) or breadth (DIA/IWM joining QQQ's weakness), that's
  the signal the correction is becoming macro rather than single-factor -- re-check the
  regime table every run rather than assuming the "factor unwind" read still holds by
  default.
