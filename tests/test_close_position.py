"""
alpaca_client.close_position: the underlying SDK call builds its request as
DELETE /positions/{symbol} with the symbol dropped straight into the URL
path, unencoded. A crypto pair like "BONK/USD" turns that into
"/positions/BONK/USD" — an extra path segment, not a symbol character —
which Alpaca 404s on. Confirmed against the live run log: every crypto
sell/cover was silently failing with "error: Not Found" (see
docs/profitability-analysis-2026-07-09.md-adjacent incident, fixed here).
"""
from unittest.mock import MagicMock, patch

import alpaca_client as ac


def test_close_position_strips_slash_for_crypto_symbol():
    with patch.object(ac.trading_client, "close_position") as mock_close:
        mock_close.return_value = MagicMock()
        ac.close_position("BONK/USD")
        mock_close.assert_called_once_with("BONKUSD")


def test_close_position_leaves_equity_symbol_unchanged():
    with patch.object(ac.trading_client, "close_position") as mock_close:
        mock_close.return_value = MagicMock()
        ac.close_position("AAPL")
        mock_close.assert_called_once_with("AAPL")
