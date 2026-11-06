# 01: Macro, regimes and reading the tape

Individual stocks are passengers on a bus driven by rates, growth, inflation and
liquidity. In an ordinary year most of a typical large-cap stock's movement is
explained by the market and its sector. Learn the bus before you pick a seat.

## 1. The four big dials

**Interest rates: the price of money and the denominator of every valuation.**
- A stock is worth the present value of its future cash flows. Higher discount rates
  shrink that value, and the further out the cash flows (growth/tech, unprofitable
  companies), the more they shrink. That is why long-duration growth stocks get hit
  hardest when long yields rise.
- Watch the 10-year Treasury yield (inverse of TLT/IEF prices). Sharp yield spikes
  are bad for growth, small caps, REITs and utilities. Falling yields from *good*
  reasons (inflation cooling) are bullish, while falling yields from *bad* reasons
  (growth scare, flight to safety) are bearish. Tell them apart by what stocks do the same day.
- **Real yields** (nominal minus inflation expectations) drive gold and long-duration
  equities most directly. Rising real yields mean pressure on GLD and high-multiple tech.
- **Yield curve** (10y minus 2y): inversion has historically preceded recessions with a
  long, variable lag. A curve that *re-steepens* after inversion, because short rates fall
  as the Fed cuts into weakness, has historically been the more dangerous phase for stocks.
  Banks (KRE, XLF) earn the spread, so a steeper curve generally helps them.

**The Fed: the marginal buyer/seller of liquidity.**
- The policy rate moves short yields. The *path* of expected cuts or hikes is what moves
  markets, so a 25bp cut that was fully expected does nothing. The dot plot, the press
  conference tone, and changes in statement wording are the surprise.
- Balance sheet: quantitative easing adds liquidity (risk assets up), quantitative
  tightening drains it. Liquidity tightening shows up first in the most speculative
  assets: ARKK, unprofitable tech, small caps, crypto-linked names.
- "Don't fight the Fed": an easing Fed with a non-recessionary economy is the best
  backdrop for stocks. A Fed hiking into slowing growth is the worst.

**Inflation.**
- CPI, PCE (the Fed's preferred measure) and wages (average hourly earnings, ECI).
  Hot inflation prints mean higher yields, which is bad for growth and good for the dollar.
- Inflationary regimes favor energy, materials, and companies with pricing power.
  Disinflationary regimes favor long-duration growth and bonds.

**Growth.**
- Payrolls, unemployment rate, jobless claims (weekly, and the best high-frequency
  recession signal), ISM manufacturing/services PMIs (50 is the line between
  expansion and contraction; new orders lead), retail sales, GDP.
- Earnings follow nominal growth. Recessions typically cut S&P earnings meaningfully,
  and stocks usually bottom *before* earnings do.

## 2. The cycle and sector rotation (a tendency, not a law)

| Phase | Typical leaders | Typical laggards |
|---|---|---|
| Early recovery (Fed easing, growth bottoming) | Small caps (IWM), discretionary (XLY), financials, tech, materials | Staples, utilities |
| Mid-cycle expansion | Tech, industrials, communication, broad market | Defensives |
| Late cycle (inflation up, Fed tightening) | Energy, materials, staples, health care | Rate-sensitive growth, small caps |
| Recession / contraction | Staples (XLP), utilities (XLU), health care (XLV), long Treasuries (TLT), gold | Cyclicals, banks, small caps, high yield credit |

Identify the phase from data *and* from what's leading. The market usually knows before the data does.

## 3. Reading the tape: ratio signals from the brief

The brief gives you returns for ETFs. Compare them:
- **QQQ vs IWM:** large-cap growth vs small caps. IWM leading means broadening and risk
  appetite plus confidence in domestic growth/credit. QQQ-only leadership means a narrow,
  fragile market.
- **XLY vs XLP:** discretionary vs staples is a consumer risk-appetite gauge.
- **HYG vs LQD/IEF:** high-yield credit vs quality. Credit usually cracks *before* equities.
  If HYG is breaking down while SPY makes highs, be suspicious.
- **SMH vs SPY:** semis lead the cycle and AI sentiment. Semis rolling over is often an
  early warning.
- **KRE vs XLF:** regional bank stress is a credit/liquidity canary.
- **GLD vs TLT:** both up means real yields are falling or there is fear. Gold up with yields up
  is often geopolitical risk or central-bank buying.
- **XLE vs SPY:** energy leadership means inflation pressure, and possibly a geopolitical supply shock.
- **EEM vs SPY:** emerging markets outperform when the dollar weakens.
- **Breadth:** count how many universe names are above their 50- and 200-day averages
  (the `vs_sma50`/`vs_sma200` columns). An index near highs with shrinking participation is
  a warning. A broad thrust (lots of names reclaiming the 50-day at once) often starts new legs up.
- **Volatility:** fast declines with rising volatility are risk-off. Don't add big gross
  exposure into an accelerating selloff. Wait for selling exhaustion (huge volume, then a
  reversal) or simply size smaller.

## 4. Regime → behavior (your default posture)

| Regime | Signs | Posture |
|---|---|---|
| **Risk-on trend** | SPY above rising 50/200-day, broad breadth, credit firm | Mostly long, buy pullbacks in leaders, shorts only on specific broken stories |
| **Choppy / range** | Index flat between levels, rotation, mixed signals | Smaller sizes, mean-reversion entries, take profits faster, more cash |
| **Correction** | Index breaks 50-day, breadth deteriorating, credit wobbling | Cut weakest longs, raise cash, add hedges/shorts in laggard sectors |
| **Bear / crisis** | Index below falling 200-day, credit spreads blowing out, defensives leading | Low gross, defensives and short-duration, short the weakest; rallies are for selling until breadth and credit heal |

Write your regime call in `market_view` every run, and change it only on evidence.

## 5. Geopolitics, policy and shocks
- Tariffs and trade: hit importers and global manufacturers, help some domestic
  producers, and are inflationary at the margin. Read who *pays* and who has pricing power.
- Oil supply shocks: up for XLE, down for airlines/transports, and inflationary.
- Elections and fiscal policy: sector-specific (health care policy, energy policy, defense
  spending, financial regulation). The market tends to price policy *risk* early and
  rally on *clarity*, even unwelcome clarity.
- Shocks (bank failures, wars, pandemics): first move is correlation going to 1, so
  everything sells. Don't panic-sell quality into a liquidity flush. Do cut anything whose
  thesis the shock actually broke.
