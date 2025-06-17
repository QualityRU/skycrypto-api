from crypto.eth import ETH
from crypto.btc import BTC
# from crypto.usdt import USDT


class Manager:
    def __init__(self):
        self.currencies = {
            'eth': ETH,
            'btc': BTC,
            # 'usdt': USDT
        }

    def from_subunit(self, symbol, val):
        f = getattr(self.currencies[symbol], 'from_subunit')
        return f(val)

    def to_subunit(self, symbol, val):
        f = getattr(self.currencies[symbol], 'to_subunit')
        return f(val)

    def get_address_from_pk(self, symbol, pk):
        f = getattr(self.currencies[symbol], 'get_address_from_pk')
        return f(pk)

    def get_balance(self, symbol, pk):
        f = getattr(self.currencies[symbol], 'get_balance')
        return f(pk)

    def get_new_pk(self, symbol):
        f = getattr(self.currencies[symbol], 'get_new_pk')
        return f()

    def is_address_valid(self, symbol, address):
        f = getattr(self.currencies[symbol], 'is_address_valid')
        return f(address)

    def get_link(self, symbol, tx_hash):
        f = getattr(self.currencies[symbol], 'get_link')
        return f(tx_hash)

    def get_transaction(self, symbol, tx_hash):
        f = getattr(self.currencies[symbol], 'get_transaction')
        return f(tx_hash)


manager = Manager()
