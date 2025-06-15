from system.constants import ADDITIONAL_DISPUTE_NOTIFICATION_TIME
from utils.db_sessions import session_scope


def _get_data(session):
    q = """
        SELECT deal_id, disp.id, d.symbol, seller_id = initiator, seller_id, buyer_id
        FROM dispute disp
        JOIN deal d on disp.deal_id = d.id
        WHERE NOT is_closed AND NOW() - INTERVAL ':disp minutes' > disp.created_at AND opponent IS NULL 
            AND d.state = 'paid' AND NOT is_second_notification_sent
    """
    return session.execute(q, {'disp': ADDITIONAL_DISPUTE_NOTIFICATION_TIME}).fetchall()


def _process_notification(did, symbol, user_id, session):
    q = "INSERT INTO notification (user_id, symbol, type, deal_id) VALUES (:uid, :sym, 'dispute_notification', :did)"
    session.execute(q, {'uid': user_id, 'sym': symbol, 'did': did})


def process_dispute_updates():
    with session_scope() as session:
        data = _get_data(session)

    for did, disp_id, symbol, is_initiator_seller, seller_id, buyer_id in data:
        with session_scope() as session:
            _process_notification(did, symbol, buyer_id if is_initiator_seller else seller_id, session)
            session.execute(
                "UPDATE dispute SET is_second_notification_sent = TRUE WHERE id = :disp_id",
                {'disp_id': disp_id}
            )
