from decimal import Decimal

from crypto.eth import ETH, web3
from data_handler import dh
from utils.db_sessions import session_scope
from system.funds_changer import change_frozen
from system.settings import db
from system.constants import TRANSACTION_TYPE, withdraws_activation_statuses, Action, OperationTypes
from utils.logger import logger
from utils.utils import create_operation


def _is_withdrawing_now(session):
    q = """
        SELECT EXISTS(
            SELECT 1 
            FROM transactions t 
            LEFT JOIN wallet w ON t.wallet_id = w.id
            WHERE type = 'out' AND NOT is_confirmed AND symbol = 'eth' AND tx_hash IS NOT NULL AND NOT t.is_deleted
        )
    """
    return session.execute(q).fetchone()[0]


def _get_tx_to_withdraw(session):
    q = """
        SELECT t.id, u.id, amount_units, to_address, sky_commission
        FROM transactions t 
        LEFT JOIN wallet w ON t.wallet_id = w.id
        LEFT JOIN "user" u ON w.user_id = u.id
        WHERE NOT is_confirmed AND type = 'out' AND symbol = 'eth' AND 
            NOT is_baned AND NOT u.is_deleted AND NOT t.is_deleted AND tx_hash IS NULL
        ORDER BY t.created_at
        LIMIT 1
    """
    return session.execute(q).fetchone()


def _get_withdrawing_tx(session):
    q = """
        SELECT t.id, tx_hash, u.id, amount_units, nickname, sky_commission, tx_type
        FROM transactions t 
        LEFT JOIN wallet w ON t.wallet_id = w.id
        LEFT JOIN "user" u ON w.user_id = u.id
        WHERE NOT is_confirmed AND type = 'out' AND NOT t.is_deleted AND tx_hash IS NOT NULL AND symbol = 'eth'
        LIMIT 1
    """
    return session.execute(q).fetchone()


def _create_tx(*, to_address, amount, transaction_id, sky_commission, session):
    net_commission = session.execute(
        'SELECT net_commission FROM crypto_settings WHERE symbol = :sym',
        {'sym': 'eth'}
    ).scalar()
    gas_price = ETH.get_gas_price(net_commission)
    net_commission = ETH.get_net_commission(gas_price, units=True)

    commission = sky_commission
    tx_hash = ETH.create_tx_out(to_address, amount, gas_price=gas_price)

    total_commission = Decimal(str(commission)) - net_commission
    q = f"UPDATE transactions SET tx_hash = '{tx_hash}', commission = {total_commission} WHERE id = {transaction_id}"
    session.execute(q)


def _set_tx_delivery_status(transaction_id, session):
    q = f'UPDATE transactions SET is_confirmed = TRUE, processed_at = NOW() WHERE id = {transaction_id}'
    session.execute(q)


def _create_notification(transaction_id, user_id, session):
    q = f"""
            INSERT INTO notification (user_id, symbol, type, transaction_id) 
            VALUES ({user_id}, 'eth', '{TRANSACTION_TYPE}', {transaction_id})
        """
    session.execute(q)


def _process_tx(transaction_id, user_id, amount, nickname, session, tx_hash, sky_commission, tx_type):
    _set_tx_delivery_status(transaction_id, session=session)
    _create_notification(transaction_id, user_id, session)
    amount_change_frozen = sky_commission + amount
    logger.info(amount_change_frozen)
    change_frozen(user_id=user_id, msg=f'Withdraw /u{nickname}', symbol='eth', session=session,
                  amount=-amount_change_frozen)
    op_type = OperationTypes.plain if tx_type == 1 else OperationTypes.public_api
    action = Action.transaction if tx_type == 1 else Action.api_withdrawal
    create_operation(
        session, user_id, tx_hash, 'eth',
        None, -amount_change_frozen, action=action,
        operation_type=op_type
    )


def send_withdraw_tx():
    if not dh.get_withdraw_status('eth'):
        return
    with session_scope() as session:
        if not _is_withdrawing_now(session):
            t = _get_tx_to_withdraw(session)
            if t:
                transaction_id, user_id, amount, to_address, sky_commission = t
                _create_tx(
                    to_address=to_address, amount=amount,
                    transaction_id=transaction_id,
                    sky_commission=sky_commission, session=session
                )


def check_tx():
    with session_scope() as session:
        if _is_withdrawing_now(session):
            transaction_id, tx_hash, user_id, amount, nickname, sky_commission, tx_type = _get_withdrawing_tx(session)
            if tx_hash:
                print(f'tx withdraw check {tx_hash}')
            if tx_hash and ETH.is_transaction_delievered(tx_hash):
                _process_tx(transaction_id=transaction_id, user_id=user_id,
                            amount=amount, nickname=nickname, session=session,
                            sky_commission=sky_commission, tx_hash=tx_hash, tx_type=tx_type)
