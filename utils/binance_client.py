import os

from binance import Client


class BinanceClient:
    def __init__(self):
        self.client = Client(os.getenv('BINANCE_KEY'), os.getenv('BINANCE_SECRET'))

    def trade(self, symbol, side, quantity):
        symbol = f'{symbol.upper()}USDT'
        order = self.client.order_market(
            side=side,
            symbol=symbol,
            quantity=quantity
        )

    def get_balance(self, symbol):
        try:
            return self.client.get_asset_balance(asset=symbol.upper())['free']
        except Exception:
            return 0

    def get_symbol_price(self, symbol):
        return self.client.get_symbol_ticker(symbol=symbol)['price']


binance_client = BinanceClient()
