import time
from datetime import timedelta, datetime

from crypto.eth import ETH
from data_handler import dh
from system.constants import TRANSACTION_TYPE, Action
from system.funds_changer import change_balance
from utils.db_sessions import session_scope
from utils.utils import create_operation, _apply_shadow_ban_if_needed


def _get_data(session):
    q = """
        SELECT private_key, w.id, u.id
        FROM wallet w
        LEFT JOIN "user" u ON w.user_id = u.id
        WHERE NOT is_baned AND 
            NOT is_deleted AND 
            symbol = 'eth' AND 
            last_action > NOW() - INTERVAL '20 minutes' AND
            NOT is_temporary AND
            private_key is not null
    """
    return session.execute(q).fetchall()


def _get_wallet_id_from_user_id(user_id, symbol, session):
    return session.execute(
        """
            SELECT id
            FROM wallet
            WHERE user_id = :uid AND symbol = :sym
        """, {'uid': user_id, 'sym': symbol}
    ).scalar()


def _check_wallet_eth_balance(pk, min_tx):
    return ETH.get_balance(pk=pk) > min_tx


def get_default_net_commission(session):
    net_commission = session.execute(
        'SELECT net_commission FROM crypto_settings WHERE symbol = :sym',
        {'sym': 'eth'}
    ).scalar()
    return net_commission


def _create_deposit_tx_eth(*, wallet_id, pk, session, gas_price):
    tx_hash = ETH.create_tx_in(pk, gas_price=gas_price)
    if _is_tx_in_process(tx_hash, session):
        return
    amount = ETH.get_tx_amount(tx_hash)
    amount = ETH.from_subunit(amount)
    transaction_id = session.execute(
        f"""
            INSERT INTO transactions (wallet_id, type, to_address, amount_units, tx_hash)
            VALUES ({wallet_id}, 'in', 'SKY', {amount}, '{tx_hash}')
            RETURNING id
        """
    ).scalar()
    session.execute(
        f"""
            INSERT INTO notification (user_id, symbol, type, transaction_id) 
            VALUES ((SELECT user_id FROM wallet WHERE id = {wallet_id}), 'eth', '{TRANSACTION_TYPE}', {transaction_id})
        """
    )


def _is_tx_in_process(tx_hash, session):
    return session.execute(
        'SELECT EXISTS(SELECT 1 FROM transactions WHERE tx_hash = :tx_hash)',
        {'tx_hash': tx_hash}
    ).scalar()


def _get_current_txs(session, symbol):
    q = f"""
        SELECT t.id, t.tx_hash, amount_units, u.id, u.nickname, t.created_at
        FROM transactions t
        INNER JOIN wallet w ON t.wallet_id = w.id
        INNER JOIN "user" u ON w.user_id = u.id
        WHERE NOT u.is_deleted AND NOT u.is_baned AND NOT t.is_confirmed AND symbol = :symbol AND tx_hash IS NOT NULL
            AND type = 'in'
    """
    return session.execute(q, {'symbol': symbol}).fetchall()


def _set_tx_delivery_status(tx_id, session):
    q = f'UPDATE transactions SET is_confirmed = True, processed_at = NOW() WHERE id = {tx_id}'
    session.execute(q)


def _process_tx(tx_id, user_id, amount, nickname, session, symbol):
    _set_tx_delivery_status(tx_id, session=session)
    change_balance(user_id=user_id, msg=f'Deposit /u{nickname}', symbol=symbol, session=session, amount=amount)
    create_operation(session, user_id, 'SKY', symbol, None, amount, action=Action.transaction)
    _apply_shadow_ban_if_needed(user_id, session)


def deposit():
    with session_scope() as session:
        data = _get_data(session)
        min_tx_eth = dh.get_settings('eth', session)['min_tx_amount']
    for pk, wallet_id, user_id in data:
        time.sleep(0.5)
        balance_eth = ETH.from_subunit(ETH.get_balance(pk=pk))
        if balance_eth >= min_tx_eth:
            with session_scope() as session:
                gas_price = ETH.get_gas_price(get_default_net_commission(session))
                _create_deposit_tx_eth(wallet_id=wallet_id, pk=pk, session=session, gas_price=gas_price)


def check_tx():
    for symbol in ('eth',):
        with session_scope() as session:
            data = _get_current_txs(session, symbol)
        for tx_id, tx_hash, amount_units, user_id, nickname, created_at in data:
            if tx_hash and created_at + timedelta(days=1) > datetime.utcnow() and ETH.is_transaction_delievered(tx_hash):
                with session_scope() as session:
                    _process_tx(
                        tx_id=tx_id, user_id=user_id,
                        amount=amount_units, nickname=nickname,
                        session=session, symbol=symbol
                    )
