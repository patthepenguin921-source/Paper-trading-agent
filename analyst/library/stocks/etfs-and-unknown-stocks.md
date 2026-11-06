# ETFs and How to Research Stocks Without a Dossier

> Written from background knowledge with a cutoff. Holdings weights, expense ratios, durations and yields drift. Check the issuer's site for current top holdings and stats before relying on a specific number.

---

## Part A: ETFs

### Broad US equity

#### SPY: SPDR S&P 500 ETF Trust
Tracks the S&P 500, which is cap-weighted and heavily concentrated: the top 10 names (mega-cap tech plus a few others) have made up roughly a third or more of the index in recent years. It expresses US large-cap equity beta, which today is largely a bet on mega-cap tech and AI earnings. It is the most liquid ETF in the world, with the deepest options market, and is the default hedge for any long-equity book: short SPY against a basket of longs to isolate stock selection. Quirks: it is structured as a unit investment trust, so it cannot lend securities or reinvest dividends internally, which creates slight tracking drag vs IVV/VOO. Use those for long holds; use SPY for trading and hedging liquidity.

#### QQQ: Invesco QQQ Trust
Tracks the Nasdaq-100: the 100 largest non-financial Nasdaq-listed companies. It is even more concentrated than SPY, with the top names (NVDA, MSFT, AAPL, AMZN, AVGO, META, GOOGL) dominating. It expresses growth/tech beta and behaves like a long-duration asset: it is sensitive to real yields and to AI-capex sentiment. Beta to SPY is typically 1.1-1.3. Use it as a hedge for tech-heavy longs, as a growth-vs-value signal (QQQ/SPY), or as a directional trade on rates and AI headlines. Quirk: Nasdaq applies concentration caps through special rebalances when large weights breach limits.

#### DIA: SPDR Dow Jones Industrial Average ETF
Tracks the 30-stock Dow, which is **price-weighted**: high-priced shares (e.g., GS, MSFT, HD, CAT, UNH historically) carry outsized weight regardless of company size. It expresses old-economy blue-chip exposure with more industrials, financials and healthcare and less mega-cap tech than SPY. It is rarely the best trading instrument; it is mostly useful as a read on "value/blue-chip vs tech" (DIA vs QQQ) and because single-stock moves in high-priced members (a UNH or GS shock) distort it. Pays monthly dividends.

#### IWM: iShares Russell 2000 ETF
Tracks ~2,000 US small caps. A large share of constituents are unprofitable, and the index has heavy regional bank, biotech and industrial weights. It expresses **domestic growth, credit conditions and interest-rate sensitivity**: small caps carry more floating-rate and short-maturity debt, so falling rates and tight credit spreads help, while rising rates and widening spreads hurt. Use it as a risk-appetite gauge (IWM/SPY), a reflation/rate-cut trade, or a short hedge in credit-stress scenarios. Quirks: high beta, prone to sharp short-covering squeezes and false breakouts; Russell reconstitution (historically late June; FTSE Russell has moved toward semiannual reconstitution, verify schedule) causes big closing-auction volume.

#### VTI: Vanguard Total Stock Market ETF
Tracks the CRSP US Total Market Index (~3,500+ stocks across large, mid, small and micro caps). Correlation with SPY is extremely high (~0.99), since large caps dominate cap weights. It expresses total US equity beta with a sliver of small/mid-cap tilt. It is a core long-term holding, not a trading tool; SPY/IVV are more liquid hedges. Use VTI vs SPY divergence only as a (weak) breadth signal.

### International equity

#### EFA: iShares MSCI EAFE ETF
Tracks developed markets ex-US and Canada: Japan, UK, France, Switzerland and Germany are the largest country weights. It is heavier in financials, industrials, healthcare and consumer staples and lighter in tech than the US. It expresses non-US developed equity plus **currency exposure** (unhedged: a falling dollar boosts returns). Use it for "rest of world catch-up" trades, dollar-weakness trades, or Europe value/rotation. Quirk: foreign market hours mean much of the price discovery happens overnight; US trading-session moves reflect futures and FX.

#### EEM: iShares MSCI Emerging Markets ETF
Tracks large- and mid-cap EM: China, Taiwan (TSMC is a top holding), India and Korea dominate. It expresses EM growth, China policy, the semiconductor cycle (via Taiwan/Korea) and, critically, the **US dollar**: a strong dollar and rising US yields generally hurt EM. Use it as a China/stimulus play, a dollar-direction trade, or a global risk-appetite gauge. Quirk: higher expense ratio than IEMG (the cheaper core alternative), but EEM has the deeper options market. China-specific ETFs (FXI, KWEB) are better for China-only views.

### Treasuries and credit

#### TLT: iShares 20+ Year Treasury Bond ETF
Holds long-dated Treasuries; duration ~16-17 years, so a 1 percentage-point move in long yields moves the price ~16-17% in the opposite direction. It expresses long-term rate expectations, term premium, fiscal/deficit worries and flight-to-quality. Use it to trade rate views, to hedge rate-sensitive equities (utilities, REITs, long-duration tech), or as a deflation/recession hedge. Quirk: in inflationary regimes (2022) stocks and bonds fall together, so TLT is not a reliable equity hedge then. Term-premium-driven sell-offs (supply/deficit fears) can hit TLT even while the Fed is cutting.

#### IEF: iShares 7-10 Year Treasury Bond ETF
Holds intermediate Treasuries; duration ~7 years. It expresses the "belly" of the curve, closest to the 10Y yield that drives mortgage rates and equity valuations. Use it as a cleaner rate proxy than TLT with about half the volatility, or in curve trades (long IEF / short TLT is a steepener; the reverse is a flattener). A better hedge for broad equity valuation than TLT, with less term-premium noise.

#### SHY: iShares 1-3 Year Treasury Bond ETF
Holds short Treasuries; duration ~2 years. It tracks **Fed policy expectations** (2Y yield) and acts as a cash proxy. Price moves are small; most of the return is yield. Use it as a parking place, or watch it as a signal: SHY rallying sharply means the market is pricing faster/deeper Fed cuts (often a growth scare). Pairs: SHY vs TLT shows curve shape.

#### HYG: iShares iBoxx $ High Yield Corporate Bond ETF
Holds US high-yield (junk) corporate bonds; spread duration ~3-4 years. It expresses **credit risk appetite**: it correlates with equities, especially small caps, and widening spreads show up here quickly. Use it as a risk gauge (HYG falling while stocks rise is a warning divergence) or as a hedge for credit-sensitive longs. Quirk: in stress, HYG can trade at a large discount to NAV because the underlying bonds are illiquid (March 2020), so the ETF price leads the bond market. JNK is the alternative.

#### LQD: iShares iBoxx $ Investment Grade Corporate Bond ETF
Holds US investment-grade corporate bonds; duration ~8 years. It expresses a mix of **Treasury rates (the dominant factor) and IG spreads**. Use it alongside HYG and IEF to separate rate moves from credit moves: LQD down with IEF flat = spreads widening; LQD down with IEF down = rates. Like HYG, it can trade at a discount to NAV in crises.

### Commodities

#### GLD: SPDR Gold Shares
Holds physical gold bullion in London vaults; one of the largest commodity ETFs. It expresses inverse real rates, inverse dollar, central-bank demand, geopolitical and fiscal-debasement hedging. Use it as a portfolio hedge against tail risks and currency debasement, a real-rate trade, or a regime signal (GLD vs TLT). Quirks: taxed as a collectible for US investors (not relevant for paper trading). GLDM/IAU have lower fees for long holds. Gold has a history of parabolic moves followed by sharp corrections.

#### SLV: iShares Silver Trust
Holds physical silver. Silver is both a monetary metal and an industrial input (solar panels, electronics), so it acts as **high-beta gold with a cyclical kicker**: it typically rises faster than gold in bull runs and falls harder in risk-off. Use it for a leveraged gold view or a reflation/industrial demand play. Quirks: very volatile, prone to squeezes and spikes; watch the gold/silver ratio for relative value.

#### USO: United States Oil Fund
Holds WTI crude oil **futures**, not physical oil. When the curve is in **contango** (later months more expensive), rolling contracts loses money over time (negative roll yield); in **backwardation** the roll adds return. So USO is a trading vehicle, not a buy-and-hold proxy for oil. After the April 2020 negative-price episode, USO changed its methodology to spread exposure across several contract months and did a reverse split. Use it for short-term crude views; for longer views energy equities (XLE) or the curve shape matter more. Quirk: structured as a commodity pool (K-1 tax form).

### Select Sector SPDRs (S&P 500 sectors)

#### XLK: Technology Select Sector SPDR
S&P 500 information-technology stocks. Extremely concentrated in NVDA, MSFT, AAPL and AVGO (capping rules limit single-name weights, which can force rebalancing flows). It expresses AI/semiconductor and software spending, plus long-duration growth sensitivity to real yields. Note: since the 2018 GICS change, GOOGL and META sit in XLC, and since 2023 Visa/Mastercard moved to XLF, so XLK is now mostly hardware, semis and software. Use it as a tech hedge or AI-cycle trade.

#### XLF: Financial Select Sector SPDR
S&P 500 financials: BRK.B, JPM, V, MA, BAC, WFC, GS and others; payments (V/MA) added in 2023 diluted the bank weighting. It expresses the yield curve (steeper helps net interest margins), credit quality, capital markets activity and deregulation. Use it as a cyclical/reflation trade, a rate-curve view, or (vs KRE) a big-bank vs regional-bank stress gauge.

#### XLE: Energy Select Sector SPDR
S&P 500 energy: XOM and CVX combined are a large share (often ~40%), then COP, EOG, SLB, WMB, KMI, MPC, PSX, OXY and others. It expresses oil prices (with a lag and damped by the curve), inflation/value rotation and capital-return themes. Use it as the cleanest oil-equity hedge, an inflation trade, or the short leg against energy-stock longs. It has historically been one of the few sectors to rally during inflationary sell-offs (2022).

#### XLV: Health Care Select Sector SPDR
S&P 500 healthcare: LLY, UNH, JNJ, ABBV, MRK, TMO, ABT, ISRG and others; LLY has become a dominant weight on GLP-1 obesity drugs. It expresses defensive growth plus policy risk (drug pricing, Medicare, tariffs on pharma). Use it as a defensive rotation trade or to hedge pharma longs. Quirk: single-name shocks (UNH, LLY) can drive the whole ETF.

#### XLY: Consumer Discretionary Select Sector SPDR
S&P 500 discretionary, dominated by AMZN and TSLA (together often near or over 40%), plus HD, MCD, BKNG, LOW, TJX, NKE, SBUX. It expresses consumer spending, but behaves partly like a two-stock tech fund. Use it vs XLP as a consumer risk-appetite gauge, keeping in mind AMZN/TSLA distortion. For a purer consumer read use equal-weight (RSPD) or retail (XRT).

#### XLP: Consumer Staples Select Sector SPDR
S&P 500 staples: COST, WMT, PG, KO, PEP, PM, MDLZ, MO, CL and others. It expresses defensiveness and dividend stability; low beta. Sensitive to rates (bond proxy) and to input-cost inflation and GLP-1 demand fears. Use it as a defensive rotation trade, a hedge in risk-off, or the denominator in the XLY/XLP risk ratio.

#### XLI: Industrial Select Sector SPDR
S&P 500 industrials: GE Aerospace, CAT, RTX, UBER, HON, UNP, ETN, BA, DE, LMT, GEV and others, spanning aerospace/defense, machinery, transports, electrical equipment. It expresses the capex cycle, ISM manufacturing, infrastructure and defense spending, and (increasingly) electrification/data-center build-out. Use it as a cyclical/reflation trade; transports (IYT) are a classic Dow Theory confirmation.

#### XLU: Utilities Select Sector SPDR
S&P 500 utilities: NEE, SO, DUK, CEG, VST, AEP, SRE, D and others. Traditionally a **bond proxy** (moves inverse to long yields, defensive), but since 2024 it has also carried an **AI power-demand** factor via CEG, VST and NRG, which trade like growth stocks. Use it as a defensive/rate trade, and read it carefully: XLU outperforming because of independent power producers is a risk-on AI signal, not a defensive one.

#### XLB: Materials Select Sector SPDR
S&P 500 materials: LIN is the largest weight, plus SHW, ECL, APD, FCX, NEM, NUE, DOW, DD, VMC, MLM. It expresses global industrial demand, the dollar (weak dollar helps), China, and commodities. It's small and concentrated in LIN. Use it as a reflation trade, or in tandem with copper/gold ratios. Metals-specific ETFs (COPX, GDX) give purer exposure.

#### XLRE: Real Estate Select Sector SPDR
S&P 500 real estate: PLD, AMT, WELL, EQIX, SPG, O, PSA, DLR, CCI, CBRE and others. Heavy in towers, data centers, logistics, healthcare REITs. It expresses long-term interest rates (cap rates) plus specialty secular themes. Use it as a rate-sensitive trade (pair vs TLT) or to hedge REIT longs. It does not have much office exposure.

#### XLC: Communication Services Select Sector SPDR
S&P 500 communications: META and GOOGL/GOOG dominate (together often near half), plus NFLX, TMUS, T, VZ, DIS, CMCSA, CHTR, EA, TTWO. It expresses digital advertising and AI platform plays, with a telecom/media defensive tail. Use it as a hedge for internet/ad longs or a digital-ad cycle trade. Quirk: in practice it's a two-stock fund on most days.

### Thematic and industry

#### SMH: VanEck Semiconductor ETF
Holds ~25 large semiconductor companies, cap-weighted with caps: NVDA is the largest (often ~20%), with TSM, AVGO, AMD, ASML, QCOM, MU, AMAT, LRCX, KLAC, INTC. Includes foreign ADRs (TSM, ASML), unlike the domestic-only SOXX. It expresses the AI data-center buildout and the global semiconductor cycle, with high beta (~1.4-1.7 to SPY). Use it as the main AI-cycle trade or hedge for semi longs. SMH vs SPY is the market's AI-leadership gauge. Export controls (China) and hyperscaler capex guidance move it.

#### XBI: SPDR S&P Biotech ETF
**Modified equal-weighted** basket of US biotech, so small and mid-cap clinical-stage names carry as much weight as profitable large caps. It expresses risk appetite, funding conditions (rates, IPO/follow-on windows), M&A activity and FDA/regulatory climate. Very sensitive to rates and the speculative cycle. Use it as a speculative-appetite gauge or a rate-cut beneficiary trade; compare with IBB (cap-weighted, larger profitable names). Quirk: binary clinical/regulatory events in individual names make it noisy.

#### KRE: SPDR S&P Regional Banking ETF
Modified equal-weighted basket of US regional and community banks. It expresses net interest margins, the yield-curve shape, deposit stability, credit quality (especially commercial real estate), and deregulation/M&A. It collapsed in the March 2023 SVB/Signature/First Republic episode; it is the go-to gauge of US banking stress. Use it for curve-steepener or deregulation trades, or short it as a hedge against credit/CRE stress. Quirk: heavy short interest at times, so squeezes can be violent.

#### ARKK: ARK Innovation ETF
Actively managed, concentrated (~30-50 names) "disruptive innovation" fund: historically TSLA, COIN, ROKU, HOOD, PLTR, CRSP, SHOP and other high-growth, mostly unprofitable or high-multiple names. It expresses **long-duration, high-beta speculative growth**: very sensitive to real yields, liquidity and retail sentiment. Use it as a speculative-froth gauge (ARKK rallying hard = risk appetite at extremes) or a short-side hedge for speculative longs. Quirks: the manager publishes holdings daily (front-running possible), fund flows drive the underlying names, and returns depend on manager discretion, not an index.

---

### Reading the tape with ETFs

Relative performance between ETFs tells you what regime the market is in. Look at ratios over 1-week, 1-month and 3-month windows, not single days. Confirm with at least two signals before calling a regime shift.

- **QQQ vs IWM (mega-cap growth vs small caps).** QQQ leading = narrow, quality/AI-led market, often with tight financial conditions or growth concerns; investors pay for balance sheets and secular growth. IWM leading = broadening, reflation, rate-cut expectations, easier credit. A sustained IWM breakout is the classic "breadth is improving" signal; failed IWM rallies are common, so require follow-through.
- **XLY vs XLP (discretionary vs staples).** Rising ratio = consumer risk-on; falling ratio = defensive rotation, often ahead of growth slowdowns. Strip out AMZN/TSLA effects by cross-checking with equal-weight or retail (XRT).
- **HYG vs LQD and HYG vs TLT/IEF (credit risk).** HYG outperforming LQD/Treasuries = credit risk appetite is healthy. HYG lagging while SPX makes new highs = a bearish divergence; credit often leads equities at turns. A sharp HYG gap below NAV is a stress signal.
- **KRE vs XLF (regional vs big banks).** KRE lagging XLF = funding or credit stress concentrated in smaller banks (deposits, CRE); it flagged March 2023. KRE leading = curve steepening, deregulation, soft-landing optimism.
- **SMH vs SPY (AI leadership).** Rising = the AI capex trade is driving the market; falling = AI fatigue or a capex scare. When SMH breaks down while SPY holds, index leadership is at risk because of the semis' weight in SPY/QQQ.
- **GLD vs TLT (which hedge works).** Both up = falling real rates and fear (classic risk-off, deflationary scare). GLD up and TLT down = inflation, fiscal-debasement or term-premium fears; bonds are not hedging, so gold is the preferred hedge. GLD down and TLT up = disinflation and a strong dollar.
- **Copper vs gold (growth vs fear).** Rising copper/gold ratio = growth optimism, usually tracking higher 10Y yields and cyclical leadership (XLI, XLB, XLF). Falling ratio = growth scare, defensive positioning, falling yields. Use FCX/NEM or COPX/GDX as equity proxies if copper futures data isn't handy.
- **Other quick tells.** XLU and XLP leading with TLT rising = defensive regime. XLE leading with TLT falling = inflation regime. EEM/EFA outperforming SPY with a falling dollar = global reflation. ARKK/XBI ripping = speculative froth; when they fail while SPY rises, risk appetite is fading under the surface.

**Regime summary (rule of thumb):**
| Signal set | Likely regime |
|---|---|
| IWM > QQQ, XLY > XLP, HYG > LQD, copper/gold up, KRE > XLF | Risk-on / reflation / broadening |
| QQQ > IWM, SMH > SPY, HYG stable, TLT flat | Narrow AI/quality-led bull |
| XLP/XLU > XLY, TLT up, GLD up, HYG lagging, copper/gold down | Risk-off / growth scare |
| XLE up, TLT down, GLD up, QQQ lagging | Inflation / stagflation scare |
| KRE collapsing vs XLF, HYG gapping lower | Credit / funding stress: reduce gross exposure |

---

## Part B: Researching a stock that has no dossier

Run this checklist before opening a position in any unfamiliar ticker. Take notes as you go; if you can't answer the core items, don't trade it, or trade it small.

### 1. Tradability: liquidity and price
- **Average daily dollar volume.** Prefer well over $20M/day for meaningful positions. Below a few $M/day, slippage and gap risk dominate any edge.
- **Price level.** Sub-$5 stocks carry penny-stock dynamics (wider spreads, institutional restrictions, manipulation risk). Under $1 risks exchange delisting notices.
- **Spread and volatility.** Check bid-ask spread as a percentage of price and the average true range (ATR). Use ATR to size and set stops.
- **Exchange.** NYSE/Nasdaq listed vs OTC. OTC names are low-information and generally off-limits.
- **Market cap** to classify mega/large/mid/small/micro. Micro-caps (under ~$300M) need extra care.

### 2. What the company actually does
- Read the **10-K Item 1 (Business)**: segments, revenue mix, customers, competitors, geographic exposure.
- Identify **how it makes money** and the 2-3 metrics that drive the stock (e.g., same-store sales, ARR, net interest margin, backlog, production volumes).
- Note customer concentration and any single-product or single-trial dependence.

### 3. Filings to read
- **10-K Item 1A (Risk Factors):** skim for unusual ones (going concern, material weakness, dependence on financing, regulatory investigations).
- **10-K Item 7 (MD&A)** and the **latest 10-Q:** revenue trend, margins, cash burn, liquidity and debt maturities.
- **Recent 8-Ks:** earnings releases, guidance changes, executive departures, auditor changes, financing (ATM programs, convertible notes, PIPEs), M&A, delisting notices.
- **Proxy (DEF 14A)** if governance matters: insider control, dual-class shares, compensation.
- **S-1/S-3/424B filings:** shelf registrations and offerings signal coming dilution.
- **Form 4s:** insider buying (meaningful) or heavy selling clusters.
- **13D/13G:** activist or large holders entering/exiting.

### 4. Earnings and event calendar
- Find the **next earnings date** and whether it's confirmed. Avoid entering a full position right before earnings unless the trade is explicitly an earnings bet.
- Look at **historical earnings-day moves** (and the options-implied move if available) to understand gap risk.
- Note other catalysts: FDA dates (PDUFA), trial readouts, investor days, lock-up expirations (~180 days post-IPO), index inclusion/deletion, court rulings, product launches.

### 5. Short interest, borrow, ownership and float
- **Short interest as % of float** and **days to cover.** Above ~20% of float = squeeze risk for shorts and crowded-bear signal for longs.
- **Borrow availability and fee** (hard-to-borrow lists). High borrow fees make shorts expensive and indicate crowding.
- **Float size.** Low-float names (under ~20M shares) move violently on small volume.
- **Ownership:** institutional %, insider %, any controlling holder. High insider ownership can align incentives but reduce liquidity.

### 6. Recent news and why it's moving
- Pull the last 1-3 months of headlines, press releases and analyst actions. **Identify the reason for the current move** before trading it. Unexplained moves on no news are a red flag.
- Distinguish real fundamental news (earnings beat, contract, approval) from promotional news (vague partnerships, "AI pivot" press releases, paid stock promotion).
- Check if the move is sector-wide (peers/ETF moving too) or idiosyncratic.

### 7. Sector and market context
- Identify the **sector ETF and 2-3 closest peers**; compare relative performance and valuation (EV/sales, P/E, EV/EBITDA as appropriate).
- Assess how the name behaves in the current regime (use the "Reading the tape" section). A high-beta small cap in a risk-off regime is a headwind for longs.
- Check correlation with the factor it's riding (rates, oil, AI, crypto, China).

### 8. Red flags (any one should cut size; several = don't trade, or only as a short with tight risk)
- **Dilution:** active ATM programs, recent or frequent offerings, warrants and convertible notes (especially floor-less or "toxic" convertibles), rapid share count growth.
- **Going-concern** language in the auditor's report or the 10-Q; cash runway under ~12 months.
- **Reverse splits**, especially repeated ones, and Nasdaq/NYSE minimum bid-price deficiency notices.
- **Auditor changes, late filings (NT 10-K/10-Q), restatements, material weaknesses.**
- **SPAC origins:** de-SPACs historically have high failure rates, heavy dilution from warrants and earnouts, and redemptions leaving low float.
- **Meme dynamics:** heavy retail chatter, extreme options volume relative to stock volume, and short-squeeze narratives. Price can disconnect from fundamentals for long stretches in both directions.
- **Pump patterns:** sudden volume spikes on obscure news, promotional press releases, recently changed business focus to a hot theme (AI, crypto, quantum, nuclear), large holders or affiliates selling into strength, and Chinese/offshore small-cap IPOs with tiny floats. Never short these without a plan for violent squeezes; never chase them long.
- Regulatory or legal overhangs: SEC investigations, short-seller reports, class actions.

### 9. Sizing a lower-information name
- **Default to a fraction of normal size**: e.g., half size or less for a name you researched today versus one with a full dossier, and smaller still for small/micro caps, low float, or any red flag.
- **Size by volatility:** target a fixed dollar risk per trade; position size = risk budget / (stop distance), where stop distance is a multiple of ATR. Higher ATR means fewer shares.
- **Respect liquidity:** keep the position small relative to average daily volume (a few percent of ADV at most) so you can exit in a gap.
- **Define the thesis, invalidation level and time stop before entry.** If the reason for the trade can't be stated in one or two sentences with a clear "wrong if" condition, don't take it.
- **Avoid holding through binary events** (earnings, FDA decisions) in low-information names unless that is the intended trade and it's sized for a total loss of the gap.
- **Shorts need extra caution:** losses are unbounded, borrow can be recalled, and squeezes hit hardest in exactly the low-float, high-short-interest names that look most overvalued. Size shorts smaller than longs and use hard stops.
- **Scale in only on confirmation:** start small and add only if the thesis is validated by price action and new information, never to average down in an unfamiliar name.
- **Write a mini-dossier** (business, drivers, catalysts, risks, levels) so the next decision about this name has context.
