from os import environ as env

from tronapi import Tron as tron_helper
from uuid import uuid4

from tronpy import Tron
from tronpy.defaults import conf_for_name
from tronpy.exceptions import AddressNotFound
from tronpy.keys import PrivateKey
from tronpy.providers import HTTPProvider

is_test = env.get('TEST')

if is_test:
    tron = Tron(HTTPProvider(api_key="779be010-4fae-47ad-aa95-f362487ccc42", endpoint_uri=conf_for_name('nile')))
    # tron = Tron(HTTPProvider(api_key="779be010-4fae-47ad-aa95-f362487ccc42"))
else:
    tron = Tron(HTTPProvider(api_key="34ba8075-fa18-4a64-b208-18eaa81c142b"))


class TRX:
    PK = env.get('TRON_PK')
    DECIMALS = 6

    @classmethod
    def get_new_pk(cls):
        return str(uuid4())

    @classmethod
    def is_address_valid(cls, address):
        return tron.is_address(address)

    @classmethod
    def get_address_from_pk(cls, pk):
        full_pk = pk + env['HEAT_SALT']
        return tron.get_address_from_passphrase(full_pk)['base58check_address']

    @classmethod
    def _get_pk(cls, passphrase):
        return tron.get_address_from_passphrase(passphrase)['private_key']

    @classmethod
    def from_subunit(cls, val):
        sign = 1
        if val < 0:
            val = abs(val)
            sign = -1
        return sign * tron_helper.fromSun(val)

    @classmethod
    def to_subunit(cls, val):
        sign = 1
        if val < 0:
            val = abs(val)
            sign = -1
        return sign * tron_helper.toSun(val)

    @classmethod
    def get_balance(cls, pk=None, address=None):
        if pk is not None:
            address = cls.get_address_from_pk(pk)
        elif address is not None:
            if not cls.is_address_valid(address):
                raise ValueError('address not valid')
        else:
            address = cls.get_address_from_pk(cls.PK)
        try:
            balance = tron.get_account_balance(address)
        except AddressNotFound:
            balance = 0
        return balance

    @classmethod
    def get_link(cls, tx_hash):
        if env.get('TEST'):
            return f'https://nile.tronscan.org/#/transaction/{tx_hash}'
        else:
            return f'https://tronscan.org/#/transaction/{tx_hash}'

    @classmethod
    def create_tx_out(cls, target_address, amount):
        target_pk = cls.PK + env['HEAT_SALT']
        txn = (
            tron.trx.transfer(cls.get_address_from_pk(cls.PK), target_address, cls.to_subunit(amount))
                .build()
                .sign(PrivateKey.from_passphrase(target_pk.encode()))
        )
        txn.broadcast().wait()
        return txn.txid

    @classmethod
    def freeze(cls, amount):
        target_pk = cls.PK + env['HEAT_SALT']
        txn = (
            tron.trx.freeze_balance(cls.get_address_from_pk(cls.PK), cls.to_subunit(amount))
                .build()
                .sign(PrivateKey.from_passphrase(target_pk.encode()))
        )
        txn.broadcast()
        return txn

    @classmethod
    def unfreeze(cls, amount):
        target_pk = cls.PK + env['HEAT_SALT']
        txn = (
            tron.trx.unfreeze_balance(cls.get_address_from_pk(cls.PK), cls.to_subunit(amount))
                .build()
                .sign(PrivateKey.from_passphrase(target_pk.encode()))
        )
        txn.broadcast()
        return txn

    @classmethod
    def get_transaction(cls, txid):
        transaction = tron.get_transaction_info(txid)
        return transaction
