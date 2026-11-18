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
- **A reinforcing fundamental catalyst is not a reason to size up right before a binary
  event, even on a working position.** 2026-11-16: confirmed via web search that the 10Y
  hit 5.14% with a December Fed hike fully priced -- a genuine, independent second reason
  the ORCL short should work (rising rates raise the cost of servicing its ~$169B debt).
  Passed on adding size anyway because NVDA earnings the next day is a binary for the
  whole AI-compute complex Oracle sits in -- a good fundamental case doesn't override bad
  entry timing into event risk. Revisit once the print resolves; this is the discipline to
  grade next review.
- **Second closed trade: UNH, 11 days held, roughly flat-to-small-loss.** Bought 2026-11-06
  ~395.63 on a genuine fundamentals-plus-defensive-rotation thesis; closed 2026-11-17
  ~390 after a sector-wide Sen. Warren healthcare-breakup headline (named UnitedHealth/
  CVS/Cigna explicitly) drove a -5.2% gap that broke the trailing stop. Fundamentals never
  broke -- this is a clean stop-exit, not a thesis failure, same pattern as the ABNB loss.
  New wrinkle: the identical political headline first hit the stock 2026-11-02 for only
  -1.7% and I correctly read it as already-priced-in noise on 11-15/16 -- the same story
  can stay immaterial for two weeks and then suddenly become the dominant driver with no
  new substantive development, just louder repetition plus a sector read-through (CVS
  also fell hard same day). Don't anchor on "I already checked this headline and it didn't
  matter" -- re-weigh magnitude and breadth (is the whole group moving, not just one name)
  each time it resurfaces, not just whether the content is new.
- **Acted on an intraday stop breach instead of waiting for a close-below-stop
  confirmation for the first time (UNH, 2026-11-17).** The written rule says "close below
  the stop," but price was already ~5% through it mid-morning on a fresh, sector-
  corroborated catalyst, and the next check wasn't until the PM run. Flagged as a specific
  discipline to grade next review: did acting early avoid further downside, or was it
  premature relative to how the stock closed that day? If early exits on intraday
  breaches keep getting proven right, make the rule explicitly intraday for large,
  catalyst-driven gaps; if they get proven wrong (price recovers and closes back above the
  stop), tighten back to requiring an actual close.
- **The intraday-stop call on UNH got a fast, strong confirmation: a second, independent
  fundamental catalyst hit the very next session.** Exited 2026-11-17 on a Warren political
  breakup headline; on 2026-11-18 a separate CMS Medicare Advantage audit/clawback proposal
  (up to $90B industry-wide) sent UNH down another -11.5% (CVS -5.2%, Humana similar).
  Political and regulatory risk compounded within 24 hours on the same name -- a reminder
  that once one thesis-threatening headline fires, don't assume the risk is a one-time,
  priced-in event; check whether it's attracting follow-on scrutiny before even considering
  a re-entry on valuation alone.
