from decimal import Decimal

from crypto.btc import BTC
from system.constants import TRANSACTION_TYPE, Action
from system.funds_changer import change_balance
from utils.db_sessions import session_scope
from utils.logger import logger
from utils.utils import create_operation, _apply_shadow_ban_if_needed


def _create_deposit(user_id, wallet_id, amount, txid, address, *, session):
    q = """
        INSERT INTO transactions (wallet_id, type, to_address, amount_units, is_confirmed, tx_hash, processed_at)
        VALUES (:wid, 'in', :address, :amount, TRUE, :txid, NOW())
        RETURNING id
    """
    q_notification = """
            INSERT INTO notification (user_id, symbol, type, transaction_id) 
            VALUES (:uid, 'btc', :ttype, :tid)
        """

    transaction_id = session.execute(q, {'wid': wallet_id, 'amount': amount, 'txid': txid, 'address': address}).fetchone()[0]
    session.execute(q_notification, {'uid': user_id, 'ttype': TRANSACTION_TYPE, 'tid': transaction_id})
    change_balance(user_id=user_id, msg=f'Deposit BTC', symbol='btc', session=session, amount=amount)
    create_operation(session, user_id, 'SKY', 'btc', None, amount, action=Action.transaction)
    _apply_shadow_ban_if_needed(user_id, session)


def deposit():
    with session_scope() as session:
        last_tx_count = session.execute("SELECT value FROM settings WHERE key = 'btc_scan_last_tx_count' LIMIT 1").scalar()
        if last_tx_count is None:
            last_tx_count = 50
        min_tx_amount = session.execute("SELECT min_tx_amount FROM crypto_settings WHERE symbol = 'btc' LIMIT 1").scalar()
    all_deposit_transactions = filter(lambda item: item['category'] == 'receive', BTC.get_all_transactions(int(last_tx_count)))
    for tx in all_deposit_transactions:
        if tx['confirmations'] > 0 and Decimal(tx['amount']) >= Decimal(str(min_tx_amount)):
            with session_scope() as session:
                is_exists = session.execute(
                    """
                        SELECT EXISTS(
                            SELECT 1 
                            FROM transactions 
                            WHERE tx_hash = :txid AND 
                                type = 'in' AND 
                                (to_address = :address OR to_address = 'SKY')
                        )
                    """,
                    {'txid': tx['txid'], 'address': tx['address']}
                ).scalar()
                if not is_exists:
                    logger.info(f'new tx in with hash {tx["txid"]}, amount = {tx["amount"]}')
                    res = session.execute(
                        "SELECT user_id, id FROM wallet WHERE symbol = 'btc' AND private_key = :addr",
                        {'addr': tx['address']}
                    ).fetchone()
                    if res:
                        user_id, wallet_id = res
                        _create_deposit(user_id, wallet_id, tx['amount'], tx['txid'], tx['address'], session=session)
                        session.execute(
                            "UPDATE wallet SET total_received = total_received + :amount WHERE id = :wid",
                            {'amount': tx['amount'], 'wid': wallet_id}
                        )
