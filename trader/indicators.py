"""Pure price-history math. No I/O, so it's easy to test."""
import math


def pct_change(closes: list[float], n: int) -> float | None:
    if len(closes) <= n or closes[-1 - n] == 0:
        return None
    return (closes[-1] / closes[-1 - n] - 1) * 100


def sma(closes: list[float], n: int) -> float | None:
    if len(closes) < n:
        return None
    return sum(closes[-n:]) / n


def rsi(closes: list[float], n: int = 14) -> float | None:
    if len(closes) <= n:
        return None
    gains = losses = 0.0
    for a, b in zip(closes[-n - 1:-1], closes[-n:]):
        d = b - a
        if d > 0:
            gains += d
        else:
            losses -= d
    if losses == 0:
        return 100.0
    rs = (gains / n) / (losses / n)
    return 100 - 100 / (1 + rs)


def annualized_vol(closes: list[float], n: int = 20) -> float | None:
    if len(closes) <= n:
        return None
    rets = [math.log(b / a) for a, b in zip(closes[-n - 1:-1], closes[-n:]) if a > 0 and b > 0]
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var) * math.sqrt(252) * 100


def summarize(bars: list[dict]) -> dict:
    """One row of stats from oldest-first daily bars ({'c','h','l','v',...})."""
    closes = [float(b["c"]) for b in bars]
    if not closes:
        return {}
    window = bars[-252:]
    hi = max(float(b["h"]) for b in window)
    lo = min(float(b["l"]) for b in window)
    avg_vol = sum(float(b["v"]) for b in bars[-20:]) / min(20, len(bars))
    s50, s200 = sma(closes, 50), sma(closes, 200)
    r = lambda x: None if x is None else round(x, 2)
    return {
        "close": r(closes[-1]),
        "chg_1d": r(pct_change(closes, 1)),
        "chg_5d": r(pct_change(closes, 5)),
        "chg_1m": r(pct_change(closes, 21)),
        "chg_3m": r(pct_change(closes, 63)),
        "chg_1y": r(pct_change(closes, 252)),
        "rsi14": r(rsi(closes)),
        "vs_sma50": r((closes[-1] / s50 - 1) * 100) if s50 else None,
        "vs_sma200": r((closes[-1] / s200 - 1) * 100) if s200 else None,
        "off_52w_high": r((closes[-1] / hi - 1) * 100) if hi else None,
        "above_52w_low": r((closes[-1] / lo - 1) * 100) if lo else None,
        "vol20_ann": r(annualized_vol(closes)),
        "avg_dollar_vol_m": r(avg_vol * closes[-1] / 1e6),
    }
