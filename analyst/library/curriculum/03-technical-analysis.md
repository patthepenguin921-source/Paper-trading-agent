# 03: Technical analysis: reading price, the only thing that pays

Fundamentals tell you *what* to own. Price tells you *when*, and whether the market
agrees with you yet. Use technicals for timing, risk placement and confirmation,
never as a substitute for a reason to own something.

## 1. What has real evidence behind it
- **Time-series momentum / trend:** assets that have risen over the past 3–12 months
  tend to keep rising over the next few months. Among the best-documented effects in finance.
- **Cross-sectional momentum / relative strength:** stocks that have outperformed peers
  over ~6–12 months (skipping the most recent month) tend to keep outperforming. Leaders lead.
- **Short-term reversal:** over very short horizons (days to a week), extreme moves tend
  to partially reverse, especially without news. Oversold quality names in uptrends bounce.
- **Post-earnings drift:** see lessons 02 and 05.
- **52-week-high effect:** stocks near their 52-week highs with strong fundamentals tend to
  break through more often than people expect. Anchoring makes investors underreact.

What has weak evidence: most named chart patterns traded mechanically, Fibonacci levels,
Elliott waves. Use them only as rough maps of where other traders may act.

## 2. Your tools (from the brief and `workspace/history/<SYM>.csv`)
| Indicator | How to read it |
|---|---|
| `vs_sma50`, `vs_sma200` | Above both with the 50 above the 200 means an uptrend. Below both means a downtrend. Price crossing back above the 200-day after a long decline is a regime change for that stock. |
| `chg_1m/3m/1y` | Momentum. Rank names within a sector, and prefer leaders for longs and laggards for shorts. |
| `rsi14` | Above 70 is overbought, below 30 is oversold. *In an uptrend, overbought is strength, not a sell signal.* RSI 30–40 pullbacks in strong uptrends are classic buy zones. In downtrends, RSI 60–70 rallies are short zones. |
| `off_52w_high` | Near 0% means at highs (strength). Down 30%+ means a damaged chart. Needs a reason and a base before you buy. |
| `vol20_ann` | Annualized volatility. Use it for sizing (lesson 04) and for setting stop distances. |
| `avg_dollar_vol_m` | Liquidity. Avoid anything with thin dollar volume (under ~$20M/day for our sizes). |
| `today_pct` | Today's move vs yesterday's close. Combine with news to judge whether it is a reaction or noise. |

Computing more from the CSV (do it in your head or by reading rows): recent swing highs
and lows (support/resistance), gap days, volume spikes vs the 20-day average, the
drawdown from peak, and how the stock behaved after its last few earnings dates.

## 3. Trend structure: the backbone
- **Uptrend:** higher highs and higher lows. Buy pullbacks to prior breakout levels or the rising 50-day.
- **Downtrend:** lower highs and lower lows. Short failed rallies at prior breakdown levels or the falling 50-day.
- **Range:** buy support and sell resistance, until it breaks. A breakout from a long base on
  heavy volume is meaningful, and one on light volume often fails.
- **Trend change** needs both a break of structure (e.g. a higher low *and* a break above
  the last lower high) and ideally a catalyst. Bottom-fishing a falling knife without both
  is the most common way to lose money in "cheap" stocks.

## 4. Volume and price together
- Big up day on 2× average volume is institutional accumulation. Big down day on 2×
  volume is distribution. Several distribution days in an index within a few weeks warn
  of a correction.
- Gap up on earnings that *holds* its gains by the close is strong. A gap that fades to red
  is a warning, because sellers used the good news to exit.
- Capitulation: a huge-volume flush that reverses intraday often marks a short-term low.

## 5. Support, resistance and placing stops
- Support/resistance come from prior swing points, gap edges, round numbers and the major
  moving averages. Expect reactions there, not guarantees.
- Put your *thesis invalidation* where the chart proves you wrong: below the higher low
  that defines the uptrend for longs, above the lower high for shorts. If that point is too far
  away for the size you want, **cut the size, don't move the stop.**
- Typical swing stop distances run 1–2.5× the stock's daily volatility over the holding
  window. Daily volatility ≈ `vol20_ann / 16`.

## 6. Relative strength is the professional's chart
Always ask: is this stock beating its sector ETF and SPY over 1 and 3 months? A long in
a stock that's lagging its sector in a rising market is fighting the tape. The best longs
are leaders in leading sectors. The best shorts are laggards in lagging sectors.
