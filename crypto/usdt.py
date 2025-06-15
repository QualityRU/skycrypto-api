import time
from decimal import Decimal
from os import environ as env

from tronapi import Tron as tron_helper
from tronpy.keys import PrivateKey

from crypto.trx import TRX, tron

is_test = env.get('TEST')


class USDT(TRX):
    PK = env.get('TRON_PK')
    if is_test:
        contract = tron.get_contract('TLBaRhANQoJFTqre9Nf1mjuwNWjCJeYqUL')
    else:
        contract = tron.get_contract('TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t')

    DECIMALS = 18 if is_test else 6

    @classmethod
    def from_subunit(cls, val):
        sign = 1
        if val < 0:
            val = abs(val)
            sign = -1
        if is_test:
            return sign * tron_helper.fromSun(tron_helper.fromSun(tron_helper.fromSun(val)))
        return sign * tron_helper.fromSun(val)

    @classmethod
    def to_subunit(cls, val):
        sign = 1
        if val < 0:
            val = abs(val)
            sign = -1
        if is_test:
            return sign * tron_helper.toSun(tron_helper.toSun(tron_helper.toSun(val)))
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
        balance = cls.contract.functions.balanceOf(address)
        return balance

    @classmethod
    def create_tx_in(cls, pk):
        system_address = cls.get_address_from_pk(cls.PK)
        from_address = cls.get_address_from_pk(pk)
        balance = cls.get_balance(pk)
        target_pk = pk + env['HEAT_SALT']
        tx = (
            cls.contract.functions.transfer(system_address, balance)
            .with_owner(from_address)
            .fee_limit(40_000_000)
            .build()
            .sign(PrivateKey.from_passphrase(target_pk.encode()))
            .broadcast()
        )
        tx.wait()
        if tx.result:
            return tx.txid

    @classmethod
    def create_tx_in_cpay(cls, pk):
        target_balance = Decimal('40')
        tron_balance = TRX.get_balance(pk=pk)
        print(tron_balance)
        if tron_balance < target_balance:
            amount_to_send = target_balance - tron_balance
            TRX.create_tx_out(TRX.get_address_from_pk(pk), amount_to_send)
        system_address = cls.get_address_from_pk(cls.PK)
        from_address = cls.get_address_from_pk(pk)
        balance = cls.get_balance(pk)
        target_pk = pk + env['HEAT_SALT']
        tx = (
            cls.contract.functions.transfer(system_address, balance)
            .with_owner(from_address)
            .fee_limit(40_000_000)
            .build()
            .sign(PrivateKey.from_passphrase(target_pk.encode()))
            .broadcast()
        )
        tx.wait()
        balance = cls.get_balance(pk)
        if balance != 0:
            raise Exception('Balance not 0')

        commission = Decimal('10')
        new_tron_balance = TRX.get_balance(pk=pk) - commission

        if new_tron_balance > 0:
            txn = (
                tron.trx.transfer(from_address, system_address, super().to_subunit(new_tron_balance))
                .fee_limit(10_000_000)
                .build()
                .sign(PrivateKey.from_passphrase(target_pk.encode()))
            )
            txn.broadcast().wait()

    @classmethod
    def create_tx_out(cls, target_address, amount):
        target_pk = cls.PK + env['HEAT_SALT']
        tx = (
            cls.contract.functions.transfer(target_address, cls.to_subunit(amount))
            .with_owner(cls.get_address_from_pk(cls.PK))
            .fee_limit(40_000_000)
            .build()
            .sign(PrivateKey.from_passphrase(target_pk.encode()))
            .broadcast()
        )

        try:
            tx.wait()
        except:
            pass

        if tx.result:
            return tx.txid
