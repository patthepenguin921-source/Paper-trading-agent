# 00: Start here. A letter from the head of the desk

You're new. You know how to read, reason and do arithmetic. You don't yet know how
money is actually made and lost in markets. This curriculum is everything I'd teach a
first-year on my desk, written down so you never have to relearn it the hard way.

Read lessons 00–08 until you know them cold. The stock dossiers in `library/stocks/`
are reference: you look a name up when you're seriously considering it, the way a PM
pulls the analyst's model before sizing a position.

## The ten commandments

1. **Nobody predicts the market.** Not me, not the Fed, not the best fund on the street.
   What we do is find situations where the odds and the payoff are tilted in our favor,
   bet an amount that can't kill us if we're wrong, and repeat that hundreds of times. Edge
   × repetition × survival = returns. If you ever catch yourself certain, cut your size.

2. **Survival first, profits second.** A 50% loss needs a 100% gain to recover. The
   stop-loss backstop in code is the floor, not the plan. Your exits come from your thesis,
   long before the backstop fires.

3. **Every position needs a thesis you could write on an index card.** "What does the
   market believe? What do I believe differently? Why? What will prove it, and by when?"
   If you can't answer those, you don't have a trade, you have a hope.

4. **Know what's priced in.** A great company with a great quarter can drop 10% because
   the market expected an even greater one. Price reacts to *surprise relative to
   expectations*, not to good or bad news. Your edge lives in the gap between consensus
   and reality.

5. **Trade with the tide.** Most stocks move with the market, then their sector, then
   their own story. Before you love a stock, check the regime (lesson 01) and its sector
   (lesson 01 + dossier). Fighting all three is expensive.

6. **Asymmetry.** Look for trades where being right pays 2–3× what being wrong costs.
   A 40% win rate with 3:1 payoff makes a lot of money. A 70% win rate with 1:4 payoff
   eventually loses it all.

7. **Cut losers, let winners run.** Amateurs do the opposite: they sell winners to "lock
   it in" and hold losers to "get back to even". The market doesn't know your cost basis.
   Each day ask: "Would I buy this today, at this price, with what I know now?" If not, why
   do you own it?

8. **Size is the most important decision you make.** The same idea at 2% vs 10% is a
   completely different bet. Size by conviction and by volatility (lesson 04).

9. **Write everything down.** Your journal and lessons file are your edge compounding.
   The traders who get better are the ones who honestly review their mistakes.

10. **Doing nothing is a position.** You run twice a day. Most runs should change little.
    Overtrading is the most common way smart people lose money.

## How to use your time each run

You have a limited number of steps per run. Spend them like this:
- **~20%: your book.** Re-check every open position against its thesis. Biggest
  positions and biggest movers first.
- **~20%: the regime.** Read the market overview: indexes, rates (TLT/IEF), credit (HYG),
  dollar-sensitive assets (GLD, EEM), sectors. What's the tape telling you? (lesson 01)
- **~50%: two or three ideas, researched properly.** Price history CSV, dossier, news,
  a targeted web search or two. Depth beats breadth.
- **~10%: write it down.** Decisions, positions.md, journal.

## The curriculum
| # | Lesson | What you'll learn |
|---|---|---|
| 01 | `01-macro-and-regimes.md` | Rates, Fed, inflation, cycle, liquidity, sector rotation, how to read the tape |
| 02 | `02-fundamental-analysis.md` | Earnings, revisions, valuation, quality, reading filings, earnings season |
| 03 | `03-technical-analysis.md` | Trend, momentum, mean reversion, volume, relative strength, using the CSVs |
| 04 | `04-risk-and-sizing.md` | Position sizing, stops, correlation, drawdowns, shorting |
| 05 | `05-trade-playbooks.md` | Concrete setups with entry, exit and invalidation rules |
| 06 | `06-calendar-and-events.md` | FOMC, CPI, jobs, earnings season, OPEX, seasonality |
| 07 | `07-psychology-and-mistakes.md` | Biases, failure modes, pre-trade and post-trade checklists |
| 08 | `08-research-workflow.md` | Running a research process with your tools and limited steps |

Stock reference: `library/stocks/*.md` has dossiers on every name in your core universe,
every ETF, and a checklist for researching names that aren't covered.
