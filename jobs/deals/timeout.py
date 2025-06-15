from system.constants import STATES
from system.funds_changer import unfreeze
from utils.db_sessions import session_scope
from utils.logger import logger
from utils.notifications_queue import create_timeout_notification
from utils.utils import update_sale_v2, update_purchase, update_payment_v2


PAYMENT_V2_DEAL_TIME = 15


def _get_deals(session):
    base_deal_time = int(session.execute("SELECT value FROM settings WHERE key = 'base_deal_time' LIMIT 1").scalar())
    advanced_deal_time = int(session.execute("SELECT value FROM settings WHERE key = 'advanced_deal_time' LIMIT 1").scalar())
    q = f"""
        SELECT id, identificator, seller_id, buyer_id, amount_subunit_frozen, symbol, state, lot_id, requisite, payment_id,
            sale_v2_id, payment_v2_id
        FROM deal
        WHERE created_at > now() - interval '1 week' AND state < 'closed' AND
            CASE WHEN state = 'proposed' THEN created_at + INTERVAL '{base_deal_time} minutes' < now()
                WHEN (state = 'confirmed' AND type = 5) THEN created_at + INTERVAL '{PAYMENT_V2_DEAL_TIME} minutes' < now()
                 WHEN state = 'confirmed' THEN coalesce(confirmed_at, created_at) + INTERVAL '{advanced_deal_time} minutes' < now()
                 ELSE FALSE
            END
        FOR UPDATE SKIP LOCKED 
    """
    return session.execute(q).fetchall()


def _delete_deal(session, deal_id, identificator, seller_id, buyer_id, amount_frozen, symbol, state, lot_id, requisite, payment_id, sale_v2_id, payment_v2_id):
    did = session.execute(
        """
            UPDATE deal
            SET state = 'deleted', cancel_reason = 'timeout', end_time = NOW()
            WHERE id = :did AND state != 'deleted'
            RETURNING id
        """, {'did': deal_id}
    ).scalar()
    if did is None:
        return
    msg = f'Deal {identificator} timeout'
    if payment_id:
        msg += f', {payment_id}'
        update_purchase(user_id=-1, purchase_id=payment_id, data={'status': 0})
    if sale_v2_id:
        update_sale_v2(user_id=-1, sale_v2_id=sale_v2_id, data={'status': 0, 'deal': None})
    if payment_v2_id:
        update_payment_v2(user_id=-1, payment_v2_id=payment_v2_id, data={'status': 0, 'deal': None})
    unfreeze(
        user_id=seller_id, msg=msg, symbol=symbol,
        amount_subunits=amount_frozen, session=session
    )

    for user_id in (seller_id, buyer_id):
        if user_id == seller_id and sale_v2_id:
            continue
        create_timeout_notification(user_id, symbol, deal_id, identificator, session)

    if state == STATES[0]:
        session.execute(
            'UPDATE wallet SET is_active = FALSE WHERE user_id = (SELECT user_id FROM lot WHERE id = :lid) AND symbol = :sym',
            {'sym': symbol, 'lid': lot_id}
        )


def update_deals():
    with session_scope() as session:
        deals = _get_deals(session)
        for deal_id, identificator, seller_id, buyer_id, amount_frozen, symbol, state, lot_id, requisite, payment_id, sale_v2_id, payment_v2_id in deals:
            try:
                _delete_deal(
                    session, deal_id, identificator,
                    seller_id, buyer_id, amount_frozen,
                    symbol, state, lot_id, requisite,
                    payment_id, sale_v2_id, payment_v2_id
                )
            except Exception as e:
                logger.exception(e)
