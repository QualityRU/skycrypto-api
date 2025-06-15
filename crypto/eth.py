import requests
from web3 import Web3, HTTPProvider
from os import environ as env
import time

from web3.exceptions import TransactionNotFound

from utils.logger import logger

if env.get('TEST'):
    web3 = Web3(HTTPProvider('https://goerli.infura.io/v3/36748d0ec5e0460db2e5d3e699601bee'))
    chain = 5
else:
    web3 = Web3(HTTPProvider('https://mainnet.infura.io/v3/39eb4de888bf411c8cc901ed11516e45'))
    chain = 1


class ETH:
    DECIMALS = 18
    PK = env.get('ETH_PK')
    gas = 21000

    @classmethod
    def get_new_pk(cls):
        return web3.eth.account.create().privateKey.hex()

    @classmethod
    def from_subunit(cls, val):
        sign = 1
        if val < 0:
            val = abs(val)
            sign = -1
        return sign * web3.fromWei(val, 'ether')

    @classmethod
    def to_subunit(cls, val):
        sign = 1
        if val < 0:
            val = abs(val)
            sign = -1
        return sign * web3.toWei(val, 'ether')

    @classmethod
    def is_address_valid(cls, address):
        return web3.isAddress(address.lower())

    @classmethod
    def get_address_from_pk(cls, pk):
        return web3.eth.account.privateKeyToAccount(pk).address

    @classmethod
    def get_balance(cls, pk=None, address=None):
        if pk is not None:
            address = cls.get_address_from_pk(pk)
        elif address is not None:
            if not web3.isAddress(address.lower()):
                raise ValueError('address not valid')
        else:
            address = cls.get_address_from_pk(cls.PK)

        return web3.eth.getBalance(address)

    @classmethod
    def get_gas_price(cls, default_net_commission):
        try:
            gas_price = int(requests.get(
                'https://api.etherscan.io/api?module=gastracker&action=gasoracle'
            ).json()['result']['FastGasPrice'])
            logger.info(f'Got gas price from etherscan: {gas_price}')
        except Exception as e:
            logger.error(e)
            gas_price = default_net_commission
        gas_price = min(gas_price, 200)
        gas_price = max(gas_price, 20)
        return gas_price

    @classmethod
    def get_net_commission(cls, gas_price, units=False):
        net_commission = int(cls.gas * web3.toWei(gas_price, 'gwei'))
        if units:
            net_commission = web3.fromWei(net_commission, 'ether')
        return net_commission

    @classmethod
    def _create_tx(cls, amount, to, from_address, gas_price):
        amount = cls.to_subunit(amount)
        gas_price = web3.toWei(gas_price, 'gwei')
        value_with_commission = amount - int(cls.gas * gas_price)
        logger.info(f'New tx: amount {cls.from_subunit(amount)}, gas price: {web3.fromWei(gas_price, "gwei")} gwei')
        transaction = {
            'to': to,
            'value': int(value_with_commission),
            'gas': cls.gas,
            'gasPrice': gas_price,
            'nonce': web3.eth.getTransactionCount(from_address),
            'chainId': chain
        }
        return transaction

    @classmethod
    def create_tx_out(cls, address, amount, gas_price):
        account = web3.eth.account.privateKeyToAccount(cls.PK)
        to = web3.toChecksumAddress(address)
        full_net_commission = cls.get_net_commission(gas_price, units=True)
        tx = cls._create_tx(
            amount=amount+full_net_commission, to=to,
            from_address=account.address, gas_price=gas_price
        )
        signed_txn = web3.eth.account.signTransaction(tx, private_key=cls.PK)
        tx_hash = web3.eth.sendRawTransaction(signed_txn.rawTransaction)
        return tx_hash.hex()

    @classmethod
    def create_tx_in(cls, pk, gas_price, **kwargs):
        balance = cls.get_balance(pk=pk)
        system_address = web3.eth.account.privateKeyToAccount(cls.PK).address
        from_address = web3.eth.account.privateKeyToAccount(pk).address
        tx = cls._create_tx(
            amount=cls.from_subunit(balance), to=system_address,
            from_address=from_address, gas_price=gas_price
        )
        signed_txn = web3.eth.account.signTransaction(tx, private_key=pk)
        tx_hash = web3.eth.sendRawTransaction(signed_txn.rawTransaction)

        return tx_hash.hex()

    @classmethod
    def create_tx_in_cpay(cls, pk):
        gas_price = cls.get_gas_price(0)
        return cls.create_tx_in(pk, gas_price)

    @classmethod
    def get_link(cls, tx_hash):
        if env.get('TEST'):
            return f'https://rinkeby.etherscan.io/tx/{tx_hash}'
        else:
            return f'https://etherscan.io/tx/{tx_hash}'

    @classmethod
    def is_transaction_delievered(cls, tx_hash):
        try:
            return bool(web3.eth.getTransactionReceipt(tx_hash))
        except TransactionNotFound:
            return False

    @classmethod
    def get_transaction(cls, tx_hash):
        return web3.eth.getTransaction(tx_hash)

    @classmethod
    def get_tx_amount(cls, tx_hash):
        while True:
            try:
                tx = web3.eth.getTransaction(tx_hash)
            except TransactionNotFound:
                tx = None
            if tx:
                return int(tx['value'])
            time.sleep(2)

        # raise Exception('Can not find transaction')
