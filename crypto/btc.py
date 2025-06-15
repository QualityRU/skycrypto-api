from decimal import Decimal
from os import environ as env

from bitcoinrpc.authproxy import AuthServiceProxy


class BTC:
    """
    PK IS ADDRESS!
    """
    RPC = lambda: AuthServiceProxy(env['BTC_NODE'])
    SECONDARY_RPC = lambda: AuthServiceProxy(env['SECONDARY_BTC_NODE'])
    PAYMENTS_RPC = lambda: AuthServiceProxy(env['PAYMENTS_BTC_NODE'])
    LINK = 'https://live.blockcypher.com/btc-testnet/tx/' if env.get('TEST') else "https://www.blockchain.com/btc/tx/"
    DECIMALS = 8

    @classmethod
    def _get_new_address(cls):
        return cls.RPC().getnewaddress()

    @classmethod
    def get_secondary_address(cls):
        return cls.SECONDARY_RPC().getnewaddress()

    @classmethod
    def get_unspents(cls, max_amount):
        return cls.RPC().listunspent(1, 9999999, [], True, {'maximumAmount': max_amount})

    @classmethod
    def wallet_create_psbt(cls, unspents, address, fee=3):
        inputs = [{'txid': unsp['txid'], 'vout': unsp['vout']} for unsp in unspents]
        total_sum = sum([unspent['amount'] for unspent in unspents])
        outputs = [{address: total_sum}]
        fee_sat_b = fee * 1024 / 10**8
        return cls.RPC().walletcreatefundedpsbt(
            inputs,
            outputs, 0,
            {'subtractFeeFromOutputs': [0], 'feeRate': fee_sat_b}
        ), total_sum

    @classmethod
    def finalize_transaction(cls, psbt):
        res = cls.RPC().walletprocesspsbt(psbt)
        res = cls.RPC().finalizepsbt(res['psbt'])
        hex_str = res['hex']
        res = cls.RPC().decoderawtransaction(hex_str)
        print(res)
        return res, hex_str

    @classmethod
    def send_raw_transaction(cls, hex_str):
        return cls.RPC().sendrawtransaction(hex_str)

    @classmethod
    def get_new_pk(cls):
        return cls._get_new_address()

    @classmethod
    def from_subunit(cls, val: Decimal):
        return Decimal(str(val)) / Decimal('10')**Decimal('8')

    @classmethod
    def to_subunit(cls, val):
        return Decimal(str(val)) * Decimal('10')**Decimal('8')

    @classmethod
    def is_address_valid(cls, address):
        return cls.RPC().validateaddress(address)['isvalid']

    @classmethod
    def get_address_from_pk(cls, pk):
        return pk

    @classmethod
    def get_balance(cls, pk=None, address=None, confs=None):
        target = pk or address
        if target:
            res = cls.RPC().getreceivedbyaddress(target, 1)
        else:
            if confs is None:
                res = cls.RPC().getbalance()
            else:
                res = cls.RPC().getbalance('*', confs)
        return cls.to_subunit(res)

    @classmethod
    def get_cpayment_address_balance(cls, address=None):
        res = cls.PAYMENTS_RPC().getreceivedbyaddress(address, 1)
        return cls.to_subunit(res)

    @classmethod
    def get_secondary_balance(cls):
        return cls.SECONDARY_RPC().getbalance()

    @classmethod
    def get_cpayment_node_balance(cls):
        return cls.PAYMENTS_RPC().getbalance()

    @classmethod
    def get_secondary_deposits(cls):
        sec_txs = cls.SECONDARY_RPC().listtransactions('*', 10)
        txs = filter(lambda item: item['category'] == 'receive' and item['confirmations'] == 0, sec_txs)
        return sum([item['amount'] for item in txs])

    @classmethod
    def get_cpayment_node_deposits(cls):
        sec_txs = cls.PAYMENTS_RPC().listtransactions('*', 100)
        txs = filter(lambda item: item['category'] == 'receive' and item['confirmations'] == 0, sec_txs)
        return sum([item['amount'] for item in txs])

    @classmethod
    def get_node_balance(cls, confirmations=0):
        return cls.RPC().getbalance("*", confirmations)

    @classmethod
    def get_total_received(cls, address=None):
        return cls.RPC().getreceivedbyaddress(address, 1)

    @classmethod
    def get_all_transactions(cls, limit=30):
        return cls.RPC().listtransactions("*", limit)

    @classmethod
    def create_tx_out(cls, address, amount_btc, blocks_target=5):
        return cls.SECONDARY_RPC().sendtoaddress(address, amount_btc, '', '', False, False, blocks_target)

    @classmethod
    def create_tx_out_primary(cls, address, amount_btc, blocks_target=5):
        return cls.RPC().sendtoaddress(address, amount_btc, '', '', False, False, blocks_target)

    @classmethod
    def create_tx_out_payments(cls, address, amount_btc, blocks_target=5):
        return cls.PAYMENTS_RPC().sendtoaddress(address, amount_btc, '', '', False, False, blocks_target)

    @classmethod
    def deposit_secondary(cls, amount):
        return cls.RPC().sendtoaddress(cls.get_secondary_address(), amount)

    @classmethod
    def send_many(cls, venue: dict):
        return cls.RPC().sendmany("", venue)

    @classmethod
    def get_transaction(cls, txid):
        return cls.RPC().gettransaction(txid)

    @classmethod
    def get_transaction_fee(cls, txid):
        try:
            tx = cls.RPC().gettransaction(txid)
            fee = abs(tx['fee'])
        except Exception:
            fee = None
        return fee

    @classmethod
    def get_transaction_fee_secondary(cls, txid):
        try:
            tx = cls.SECONDARY_RPC().gettransaction(txid)
            fee = abs(tx['fee'])
        except Exception:
            fee = None
        return fee

    @classmethod
    def get_link(cls, tx_hash):
        return cls.LINK + tx_hash
