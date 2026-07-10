"""
Read-only diagnostic: prints the active agent's account equity/cash/buying
power, plus every crypto pair Alpaca currently lists as tradable on this
account. NOT part of the trading pipeline — used to sanity-check config.py's
starting_equity/ERIS_MEMECOINS assumptions against the real account instead
of guessing. Prints to the job log only; writes nothing to the repo.
"""
import os

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetAssetsRequest
from alpaca.trading.enums import AssetClass, AssetStatus

API_KEY = os.environ["ALPACA_API_KEY"]
SECRET_KEY = os.environ["ALPACA_SECRET_KEY"]
AGENT_ID = os.environ.get("AGENT_ID", "plutus")

trading_client = TradingClient(API_KEY, SECRET_KEY, paper=True)

account = trading_client.get_account()
print(f"=== {AGENT_ID} account ===")
print(f"equity: {account.equity}")
print(f"cash: {account.cash}")
print(f"buying_power: {account.buying_power}")
print(f"shorting_enabled: {getattr(account, 'shorting_enabled', None)}")

assets = trading_client.get_all_assets(
    GetAssetsRequest(asset_class=AssetClass.CRYPTO, status=AssetStatus.ACTIVE)
)
tradable = sorted(a.symbol for a in assets if a.tradable)
print(f"\n=== {len(tradable)} tradable crypto pairs ===")
for symbol in tradable:
    print(symbol)
