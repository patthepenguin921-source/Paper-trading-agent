# 04: Risk and sizing: how you stay in the game

The best traders in the world are wrong 40–50% of the time. They make money because
their losses are small and their wins are large. This lesson is the difference.

## 1. Position sizing
Start from **risk**, not from conviction alone:
1. Decide where the thesis is wrong (your stop/invalidation level). Distance = D%.
2. Decide how much of the account you're willing to lose if wrong. Default 0.5–1.0% of
   equity per idea, up to ~1.5% for your very best ideas.
3. Position size % ≈ risk % ÷ D%. Example: risk 0.75% with a stop 8% away gives ~9% of equity.
4. Clip to the code limits (≤10%) and to conviction tiers:

| Conviction | Size | Typical situation |
|---|---|---|
| Starter / speculative | 2–4% | Interesting but unproven, or before a catalyst |
| Solid | 5–7% | Thesis plus confirming price action and fundamentals |
| Highest | 8–10% | Multiple independent reasons align: fundamentals, revisions, trend, catalyst, regime |

5. **Volatility-adjust:** a stock with 60% annual vol (`vol20_ann`) needs roughly half the
   position of one with 30% vol for the same risk.

Scale in when proven right: start at half size, add on confirmation (a successful
retest, an earnings beat), never add to losers.

## 2. Portfolio construction
- **Correlation is hidden concentration.** Five semis longs are one bet. Group holdings by
  factor (AI/semis, rates-sensitive, consumer, energy/inflation, defensives) and keep any
  single theme under ~30–35% of equity unless it's a deliberate, high-conviction call.
- **Net and gross exposure:** net = long − short. In risk-on regimes run net 60–100%. In
  choppy markets, 30–60%. In corrections, 0–30% or lower. Gross is capped at 100% by code.
- **Hedges:** if you're long a lot of tech and worried about the market, shorting QQQ or SMH
  (or a weak name in the group) hedges market risk while keeping your stock-picking edge.
- **Cash** is a legitimate allocation. You have no benchmark-hugging obligation.

## 3. Exits: the half of trading nobody teaches
- **Thesis exit:** the reason you bought is gone (guidance cut, catalyst failed, story
  changed). Sell regardless of P&L.
- **Stop exit:** price hit the invalidation level. Sell. Don't renegotiate with yourself.
- **Target exit:** price reached your fair value or target and the risk/reward is no longer
  attractive. Trim or sell. Let part run if the trend is strong and fundamentals keep improving.
- **Time exit:** the catalyst came and went and nothing happened. Capital has opportunity
  cost. If a position is "dead money" for a month with no catalyst, recycle it.
- **Trailing logic:** as a winner runs, move your mental stop up (e.g. below the rising
  50-day or the most recent higher low) so a big gain can't turn into a loss.
- Remember: you only run twice a day and code closes anything down 15%. Set realistic
  invalidation levels inside that, and write them in `positions.md`.

## 4. Drawdown discipline
- Account down 5% from peak: review every position and cut the weakest thesis.
- Down 10%: halve gross exposure and trade only A+ setups until you've recovered half.
- Losing streak (e.g. 5 losers in a row): stop, review in your journal what's common to them,
  and reduce size until a couple of winners come. Usually it's the regime, not bad luck.

## 5. Shorting: a different animal
- Losses are unbounded and the long-term drift of the market is up. Short with a
  **specific catalyst and timeframe**, not just "it's overvalued". Overvalued stocks can
  double.
- Best shorts: broken fundamentals (falling estimates, guidance cuts) plus broken charts (below
  falling 50/200-day, failed rallies) plus a weak sector. Ideally into or after a negative catalyst.
- **Squeeze risk:** high short interest plus a small float plus heavy retail attention can produce
  violent rallies. Avoid shorting meme-prone names. Code also rejects hard-to-borrow names.
- Size shorts smaller than longs (start 2–5%). Cover into capitulation (huge-volume
  flushes), because shorts make their money in the decline, not by waiting for zero.
- Index/sector ETF shorts (SPY, QQQ, IWM, SMH, XLY, KRE...) are cleaner hedges than single
  names: no single-company squeeze risk.

## 6. Expected value: the only math that matters
EV = P(win) × avg win − P(loss) × avg loss. Track your actual numbers in the weekly
review (win rate, average win, average loss, by setup type). Kill setups with negative EV and
size up the ones with demonstrated positive EV.
