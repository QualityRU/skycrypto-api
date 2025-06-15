from data_handler import dh
from system.settings import db
from system.constants import TRANSACTION_TYPE, withdraws_activation_statuses, Action, OperationTypes
from decimal import Decimal
from system.funds_changer import change_frozen
from crypto.btc import BTC
from utils.db_sessions import session_scope
from utils.logger import logger
from utils.utils import create_operation


def _get_data(session):
    min_tx_amount = dh.get_settings('btc', session)['min_tx_amount']
    q = """
            SELECT t.id, u.id, amount_units, to_address, sky_commission, tx_type
            FROM transactions t
            LEFT JOIN wallet w ON t.wallet_id = w.id
            LEFT JOIN "user" u ON w.user_id = u.id
            WHERE NOT is_confirmed AND type = 'out' AND symbol = 'btc' AND amount_units >= :min AND
                NOT is_baned AND NOT u.is_deleted AND NOT t.is_deleted AND tx_hash IS NULL
        """
    return session.execute(q, {'min': min_tx_amount}).fetchall()


def _update_transaction(tid, tx_hash, commission, session):
    q = """
        UPDATE transactions
        SET tx_hash = :txhash, commission = :com, is_confirmed = TRUE, processed_at = NOW()
        WHERE id = :tid
    """
    session.execute(q, {'txhash': tx_hash, 'com': commission, 'tid': tid})


def _create_notification(user_id, tid, session):
    q = """
        INSERT INTO notification (user_id, symbol, type, transaction_id)
        VALUES (:uid, 'btc', :tt, :tid)
    """
    session.execute(q, {'uid': user_id, 'tt': TRANSACTION_TYPE, 'tid': tid})


def withdraw():
    if not dh.get_withdraw_status('btc'):
        return
    with session_scope() as session:
        data = _get_data(session)
        target_dict = {}

    for tid, uid, amount, address, _, _ in data:
        amount_by_address = Decimal(target_dict.get(address, 0))
        target_dict[address] = str(amount_by_address + Decimal(str(amount)))

    if not target_dict:
        return

    logger.info(f'Withdraw BTC: {target_dict}')
    tx_hash = BTC.send_many(venue=target_dict)
    commission_net = BTC.get_transaction_fee(tx_hash)

    for i, (transaction_id, user_id, value_units, address, sky_comm, tx_type) in enumerate(data):
        if i == 0 and commission_net is not None:
            com = Decimal(str(sky_comm)) - Decimal(str(commission_net))
        else:
            com = Decimal(str(sky_comm))

        with session_scope() as session:
            _update_transaction(transaction_id, tx_hash, com, session)
            amount_change_frozen = Decimal(str(sky_comm)) + value_units
            try:
                change_frozen(user_id, f'Transaction out {tx_hash}', amount=-amount_change_frozen,
                              symbol='btc', session=session)
            except Exception as e:
                logger.error(e)
            _create_notification(user_id, transaction_id, session)
            op_type = OperationTypes.plain if tx_type == 1 else OperationTypes.public_api
            action = Action.transaction if tx_type == 1 else Action.api_withdrawal
            create_operation(session, user_id, tx_hash, 'btc', None, -amount_change_frozen, action=action,
                             operation_type=op_type)
