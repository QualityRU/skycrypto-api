import time
from decimal import Decimal

from crypto.trx import TRX
from crypto.usdt import USDT
from data_handler import dh
from system.constants import TRANSACTION_TYPE, Action
from system.funds_changer import change_balance
from utils.db_sessions import session_scope
from utils.utils import create_operation, _apply_shadow_ban_if_needed


def _get_data(session):
    q = """
        SELECT private_key, w.id, u.id, nickname
        FROM wallet w
        LEFT JOIN "user" u ON w.user_id = u.id
        WHERE NOT is_baned AND 
            NOT is_deleted AND 
            symbol = 'usdt' AND 
            last_action > NOW() - INTERVAL '10 minutes' AND
            NOT is_temporary AND
            private_key is not null
    """
    return session.execute(q).fetchall()


def _create_deposit(wallet_id, pk, session, balance, user_id, nickname):
    target_balance = Decimal('20')
    tron_balance = TRX.get_balance(pk=pk)
    if tron_balance < target_balance:
        amount_to_send = target_balance - tron_balance
        TRX.create_tx_out(TRX.get_address_from_pk(pk), amount_to_send)
    tx_hash = USDT.create_tx_in(pk)
    if tx_hash:
        transaction_id = session.execute(
            f"""
                INSERT INTO transactions (wallet_id, type, to_address, amount_units, tx_hash, is_confirmed, processed_at)
                VALUES ({wallet_id}, 'in', 'SKY', {balance}, '{tx_hash}', TRUE, NOW())
                RETURNING id
            """
        ).scalar()
        session.execute(
            f"""
                INSERT INTO notification (user_id, symbol, type, transaction_id) 
                VALUES ({user_id}, 'usdt', '{TRANSACTION_TYPE}', {transaction_id})
            """
        )
        change_balance(user_id=user_id, msg=f'Deposit /u{nickname}', symbol='usdt', session=session, amount=balance)
        create_operation(session, user_id, 'SKY', 'usdt', None, balance, action=Action.transaction)
        _apply_shadow_ban_if_needed(user_id, session)


def deposit():
    with session_scope() as session:
        data = _get_data(session)
        min_tx = dh.get_settings('usdt', session)['min_tx_amount']
    for pk, wallet_id, user_id, nickname in data:
        balance = USDT.from_subunit(USDT.get_balance(pk=pk))
        time.sleep(1)
        if balance >= min_tx:
            with session_scope() as session:
                _create_deposit(
                    wallet_id=wallet_id, pk=pk,
                    session=session, balance=balance,
                    user_id=user_id, nickname=nickname
                )


