"""
The dartboard: liquid, well-known US stocks and ETFs.

The monkey picks only from here, so it can't hit illiquid junk. The analyst
always gets stats for these in its brief, but it may trade any US-listed
stock or ETF that passes the risk checks, including today's movers and
anything it researched on its own.
"""

ETFS = [
    "SPY", "QQQ", "DIA", "IWM", "VTI", "EFA", "EEM", "TLT", "IEF", "SHY",
    "GLD", "SLV", "USO", "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI",
    "XLU", "XLB", "XLRE", "XLC", "SMH", "XBI", "KRE", "ARKK", "HYG", "LQD",
]

STOCKS = [
    # Tech / communication
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "AVGO", "ORCL", "CRM", "ADBE",
    "AMD", "INTC", "QCOM", "TXN", "MU", "AMAT", "LRCX", "IBM", "CSCO", "NOW",
    "INTU", "PANW", "CRWD", "SNOW", "PLTR", "UBER", "SHOP", "NFLX", "DIS", "TSLA",
    # Financials
    "JPM", "BAC", "WFC", "GS", "MS", "C", "SCHW", "BLK", "V", "MA",
    "AXP", "PYPL", "COF", "BRK.B",
    # Health care
    "UNH", "JNJ", "LLY", "PFE", "MRK", "ABBV", "TMO", "ABT", "AMGN", "GILD",
    "CVS", "ISRG", "VRTX", "REGN",
    # Consumer
    "WMT", "COST", "HD", "LOW", "TGT", "MCD", "SBUX", "NKE", "KO", "PEP",
    "PG", "CL", "MDLZ", "PM", "MO", "BKNG", "ABNB", "CMG", "LULU",
    # Industrials / energy / materials
    "BA", "CAT", "DE", "GE", "HON", "LMT", "RTX", "UPS", "FDX", "UNP",
    "XOM", "CVX", "COP", "SLB", "OXY", "LIN", "FCX", "NEM",
    # Other
    "T", "VZ", "TMUS", "NEE", "DUK", "SO", "AMT", "PLD", "F", "GM",
]

UNIVERSE = ETFS + STOCKS
