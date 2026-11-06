"""
Minimal Alpaca REST client. Uses the PAPER trading base URL only, so no code
path here can place a live order.
"""
import time
from datetime import datetime, timedelta, timezone

import requests

from trader import config


class Alpaca:
    def __init__(self, agent_id: str):
        key, secret = config.credentials(agent_id)
        self.agent_id = agent_id
        self.s = requests.Session()
        self.s.headers.update({"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret})

    # -- plumbing ----------------------------------------------------------
    def _req(self, method: str, url: str, **kw):
        for attempt in range(4):
            r = self.s.request(method, url, timeout=30, **kw)
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(2 ** attempt)
                continue
            break
        if r.status_code >= 400:
            raise RuntimeError(f"Alpaca {method} {url} -> {r.status_code}: {r.text[:300]}")
        return r.json() if r.text else None

    def _trade(self, method: str, path: str, **kw):
        return self._req(method, f"{config.PAPER_BASE_URL}{path}", **kw)

    def _data(self, path: str, params: dict):
        return self._req("GET", f"{config.DATA_BASE_URL}{path}", params=params)

    # -- account -----------------------------------------------------------
    def clock(self) -> dict:
        return self._trade("GET", "/v2/clock")

    def account(self) -> dict:
        return self._trade("GET", "/v2/account")

    def positions(self) -> list[dict]:
        return self._trade("GET", "/v2/positions")

    def open_orders(self) -> list[dict]:
        return self._trade("GET", "/v2/orders", params={"status": "open", "limit": 200})

    def cancel_all_orders(self):
        return self._trade("DELETE", "/v2/orders")

    def fills(self, days: int = 30) -> list[dict]:
        after = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        return self._trade("GET", "/v2/account/activities/FILL",
                           params={"after": after, "direction": "desc", "page_size": 100}) or []

    def portfolio_history(self, period: str = "3M") -> dict:
        return self._trade("GET", "/v2/account/portfolio/history",
                           params={"period": period, "timeframe": "1D"}) or {}

    def asset(self, symbol: str) -> dict | None:
        try:
            return self._trade("GET", f"/v2/assets/{symbol}")
        except RuntimeError:
            return None

    # -- orders ------------------------------------------------------------
    def market_order(self, symbol: str, qty: int, side: str, client_order_id: str | None = None) -> dict:
        body = {"symbol": symbol, "qty": str(int(qty)), "side": side,
                "type": "market", "time_in_force": "day"}
        if client_order_id:
            body["client_order_id"] = client_order_id[:48]
        return self._trade("POST", "/v2/orders", json=body)

    def close_position(self, symbol: str, fraction: float = 1.0) -> dict:
        params = {}
        if fraction < 0.999:
            params["percentage"] = f"{max(1.0, fraction * 100):.2f}"
        return self._trade("DELETE", f"/v2/positions/{symbol}", params=params)

    # -- market data -------------------------------------------------------
    def daily_bars(self, symbols: list[str], days: int = 400) -> dict[str, list[dict]]:
        """Split/dividend-adjusted daily bars, oldest first. Uses the SIP feed,
        which the free plan allows for data more than 15 minutes old."""
        out: dict[str, list[dict]] = {}
        start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        end = (datetime.now(timezone.utc) - timedelta(minutes=16)).isoformat()
        for i in range(0, len(symbols), 50):
            chunk = symbols[i:i + 50]
            token = None
            while True:
                params = {"symbols": ",".join(chunk), "timeframe": "1Day", "start": start,
                          "end": end, "adjustment": "all", "feed": "sip", "limit": 10000}
                if token:
                    params["page_token"] = token
                resp = self._data("/v2/stocks/bars", params)
                for sym, bars in (resp.get("bars") or {}).items():
                    out.setdefault(sym, []).extend(bars)
                token = resp.get("next_page_token")
                if not token:
                    break
        return out

    def snapshots(self, symbols: list[str]) -> dict[str, dict]:
        """Latest trade + today's/yesterday's daily bar (IEX feed, real time on free plan)."""
        out = {}
        for i in range(0, len(symbols), 100):
            chunk = symbols[i:i + 100]
            out.update(self._data("/v2/stocks/snapshots", {"symbols": ",".join(chunk), "feed": "iex"}) or {})
        return out

    def latest_price(self, symbol: str) -> float | None:
        snap = self.snapshots([symbol]).get(symbol) or {}
        trade = snap.get("latestTrade") or {}
        price = trade.get("p") or (snap.get("dailyBar") or {}).get("c") or (snap.get("prevDailyBar") or {}).get("c")
        return float(price) if price else None

    def movers(self, top: int = 15) -> dict:
        try:
            return self._data("/v1beta1/screener/stocks/movers", {"top": top}) or {}
        except RuntimeError:
            return {}

    def most_actives(self, top: int = 20) -> list[dict]:
        try:
            return (self._data("/v1beta1/screener/stocks/most-actives", {"top": top, "by": "volume"}) or {}).get("most_actives", [])
        except RuntimeError:
            return []

    def news(self, symbols: list[str] | None = None, limit: int = 50) -> list[dict]:
        params = {"limit": min(limit, 50), "exclude_contentless": "true", "sort": "desc"}
        if symbols:
            params["symbols"] = ",".join(symbols)
        try:
            return (self._data("/v1beta1/news", params) or {}).get("news", [])
        except RuntimeError:
            return []
