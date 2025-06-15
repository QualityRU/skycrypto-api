from decimal import Decimal

import requests

from crypto.trx import TRX
from crypto.usdt import USDT
from data_handler import dh
from system.constants import TRANSACTION_TYPE, Action, OperationTypes
from system.funds_changer import change_frozen
from utils.db_sessions import session_scope
from utils.logger import logger
from utils.utils import create_operation


def _get_tx_to_withdraw(session):
    q = """
        SELECT t.id, u.id, amount_units, to_address, nickname, sky_commission, tx_type
        FROM transactions t 
        LEFT JOIN wallet w ON t.wallet_id = w.id
        LEFT JOIN "user" u ON w.user_id = u.id
        WHERE NOT is_confirmed AND type = 'out' AND symbol = 'usdt' AND 
            NOT is_baned AND NOT u.is_deleted AND NOT t.is_deleted AND tx_hash IS NULL
        ORDER BY t.created_at
        LIMIT 1
    """
    return session.execute(q).fetchone()


def _get_tx_fee(txid):
    current_rate = requests.get(
        'https://api.coingecko.com/api/v3/simple/price?ids=tron&vs_currencies=usd'
    ).json()['tron']['usd']
    try:
        fee = TRX.get_transaction(txid)['fee']
    except Exception as e:
        logger.exception(e)
        fee = 0
    commission = TRX.from_subunit(fee) * Decimal(str(current_rate))
    return commission


def _create_tx(*, to_address, amount, transaction_id, user_id, nickname, sky_commission):
    q = f"""
        UPDATE transactions 
        SET is_confirmed = TRUE, processed_at = NOW()
        WHERE id = {transaction_id}
    """
    with session_scope() as session:
        session.execute(q)
        amount_change_frozen = sky_commission + amount
        change_frozen(user_id=user_id, msg=f'Withdraw /u{nickname}', symbol='usdt', session=session,
                      amount=-amount_change_frozen)

    tx_hash = USDT.create_tx_out(to_address, amount)
    logger.info(f'Withdraw usdt txid: {tx_hash}')
    try:
        fee = _get_tx_fee(tx_hash)
    except Exception as e:
        logger.exception(e)
        fee = Decimal('0')

    if tx_hash:
        total_commission = sky_commission - fee
        q = f"""
            UPDATE transactions 
            SET tx_hash = '{tx_hash}', commission = {total_commission}, is_confirmed = TRUE, processed_at = NOW()
            WHERE id = {transaction_id}
        """
        with session_scope() as session:
            session.execute(q)
        return tx_hash


def _create_notification(transaction_id, user_id, session):
    q = f"""
            INSERT INTO notification (user_id, symbol, type, transaction_id) 
            VALUES ({user_id}, 'usdt', '{TRANSACTION_TYPE}', {transaction_id})
        """
    session.execute(q)


def _process_tx(transaction_id, user_id, amount, tx_hash, sky_commission, tx_type):
    with session_scope() as session:
        _create_notification(transaction_id, user_id, session)
        amount_change_frozen = sky_commission + amount
        op_type = OperationTypes.plain if tx_type == 1 else OperationTypes.public_api
        action = Action.transaction if tx_type == 1 else Action.api_withdrawal
        create_operation(
            session, user_id, tx_hash, 'usdt',
            None, -amount_change_frozen, action=action,
            operation_type=op_type
        )


def send_withdraw_tx():
    if not dh.get_withdraw_status('usdt'):
        return
    with session_scope() as session:
        t = _get_tx_to_withdraw(session)
    if t:
        transaction_id, user_id, amount, to_address, nickname, sky_commission, tx_type = t
        tx_hash = _create_tx(
            to_address=to_address, amount=amount,
            transaction_id=transaction_id, user_id=user_id,
            nickname=nickname, sky_commission=sky_commission
        )
        if tx_hash:
            _process_tx(transaction_id, user_id, amount, tx_hash, sky_commission, tx_type)
