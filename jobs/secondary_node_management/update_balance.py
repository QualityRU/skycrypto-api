import os
from decimal import Decimal

from crypto.btc import BTC
from utils.db_sessions import session_scope
from utils.logger import logger


def update():
    balance = BTC.get_secondary_balance() + BTC.get_secondary_deposits()
    threshold = '0.05'
    deposit = '0.05'
    if balance < Decimal(threshold):
        tx_hash = BTC.deposit_secondary(Decimal(deposit))
        logger.info(f'New secondary deposit on {deposit} BTC, {tx_hash}')
        with session_scope() as session:
            session.execute(
                "INSERT INTO secondarydeposits (tx_hash, amount) VALUES (:tx_hash, :amount)",
                {'tx_hash': tx_hash, 'amount': deposit}
            )
