"""
Symbol -> sector mapping, used only by risk.py's sector-concentration cap
(_enforce_caps). Nothing else in this codebase needs sector data, so this
stays a flat, hand-maintained map rather than a live data source — the
universes in config.py change rarely enough that this is cheap to keep in
sync, and a wrong/missing entry only affects the concentration cap (falls
back to "Unclassified", see sector_of()), never order execution itself.

Buckets are grouped by *correlation*, not strict GICS classification, where
the two disagree — e.g. TSLA/RIVN/LCID/CVNA sit in Automotive/EV rather than
being split across Consumer Discretionary and Industrials, because the
whole point of this cap is catching "legally 100% in four names that move
together" (see docs/profitability-analysis-2026-07-09.md's semiconductor
example), not producing an accurate 10-K sector classification.

Broad-market ETFs (SPY, QQQ, VTI, ...) and bonds/treasuries are exempt
(mapped to None) — a position in a diversified index isn't a concentration
risk the way four single-name semiconductor bets are, and capping it would
just get in the way of the model using them as the low-conviction ballast
they're meant to be.
"""

SECTOR_MAP: dict[str, str] = {
    # ---- Technology (large-cap tech, software, and tech-adjacent names not
    # already covered by Semiconductors or Automotive/EV) ----
    "AAPL": "Technology", "MSFT": "Technology", "GOOGL": "Technology",
    "AMZN": "Technology", "META": "Technology", "ORCL": "Technology",
    "CRM": "Technology", "ADBE": "Technology", "PLTR": "Technology",
    "SHOP": "Technology", "SQ": "Technology", "BB": "Technology",
    "NOK": "Technology", "MSTR": "Technology", "IONQ": "Technology",
    "XLK": "Technology",

    # ---- Semiconductors (split out from Technology — the concrete example
    # this cap exists for: "Hermes at 25% max sizing can legally end up
    # 100% in four semiconductor stocks that all move together") ----
    "NVDA": "Semiconductors", "AVGO": "Semiconductors", "AMD": "Semiconductors",
    "INTC": "Semiconductors", "QCOM": "Semiconductors", "MU": "Semiconductors",

    # ---- Financials (banks, payments, brokerages, and fintech/crypto-
    # adjacent equities whose price action tracks the sector) ----
    "JPM": "Financials", "V": "Financials", "MA": "Financials",
    "BAC": "Financials", "GS": "Financials", "MS": "Financials",
    "C": "Financials", "HOOD": "Financials", "SOFI": "Financials",
    "COIN": "Financials", "XLF": "Financials",

    # ---- Healthcare / Pharma ----
    "UNH": "Healthcare", "JNJ": "Healthcare", "ABBV": "Healthcare",
    "PFE": "Healthcare", "MRNA": "Healthcare", "LLY": "Healthcare",
    "BMY": "Healthcare", "XLV": "Healthcare",

    # ---- Energy ----
    "XOM": "Energy", "CVX": "Energy", "OXY": "Energy", "SLB": "Energy",
    "XLE": "Energy",

    # ---- Consumer Staples (defensive, non-discretionary) ----
    "PG": "Consumer Staples", "KO": "Consumer Staples", "PEP": "Consumer Staples",
    "WMT": "Consumer Staples", "COST": "Consumer Staples", "XLP": "Consumer Staples",

    # ---- Consumer Discretionary (retail/leisure spend) ----
    "HD": "Consumer Discretionary", "MCD": "Consumer Discretionary",
    "NKE": "Consumer Discretionary", "TGT": "Consumer Discretionary",
    "GME": "Consumer Discretionary",

    # ---- Communication Services / Media ----
    "DIS": "Communication Services", "NFLX": "Communication Services",
    "RBLX": "Communication Services", "AMC": "Communication Services",
    "DJT": "Communication Services",

    # ---- Automotive / EV (kept separate from Consumer Discretionary and
    # Industrials — TSLA/RIVN/LCID/CVNA move together on EV-sector news far
    # more than they move with the rest of either of those buckets) ----
    "TSLA": "Automotive/EV", "RIVN": "Automotive/EV", "LCID": "Automotive/EV",
    "CVNA": "Automotive/EV",

    # ---- Aerospace / Industrials ----
    "RKLB": "Aerospace/Industrials",

    # ---- Utilities ----
    "XLU": "Utilities",

    # ---- Broad-market / diversified index ETFs — exempt from the cap ----
    "SPY": None, "QQQ": None, "DIA": None, "IWM": None, "VTI": None, "VOO": None,

    # ---- Bonds / treasuries — exempt from the cap ----
    "BND": None, "AGG": None, "TLT": None, "SHY": None,
}

# Every "/"-formatted symbol (crypto pair, see alpaca_client.is_crypto) maps
# to this single bucket rather than being enumerated individually — Eris is
# the only agent that trades crypto, and the coins move together on BTC/ETH
# sentiment closely enough that per-coin sub-buckets would be false
# precision for what this cap is trying to catch.
_CRYPTO_SECTOR = "Crypto"


def sector_of(symbol: str) -> str | None:
    """
    Returns the sector bucket for `symbol`:
    - every crypto pair (contains "/") always maps to the single "Crypto"
      bucket, regardless of coin;
    - a symbol explicitly in SECTOR_MAP returns its mapped sector, or None
      if it's explicitly exempt from the concentration cap (broad-market
      ETFs, bonds);
    - anything else (a real symbol missing from the map — e.g. a newly
      added universe entry nobody's categorized yet) returns "Unclassified"
      rather than exempting it silently, so a gap in this file fails toward
      "capped together with other unclassified names" instead of toward
      "no cap at all."
    """
    if "/" in symbol:
        return _CRYPTO_SECTOR
    return SECTOR_MAP.get(symbol, "Unclassified")
