from data_handler import dh
from system.constants import DISPUTE_TIME, STATES
from system.funds_changer import unfreeze
from utils.db_sessions import session_scope
from utils.logger import logger
from utils.notifications_queue import create_closed_dispute_notification


def _get_data(session):
    q = """
        SELECT deal_id, d.identificator, d.symbol, seller_id = initiator
        FROM dispute disp
        JOIN deal d on disp.deal_id = d.id
        WHERE NOT is_closed AND NOW() - INTERVAL ':disp minutes' > disp.created_at AND opponent IS NULL 
            AND d.state = 'paid'
    """
    return session.execute(q, {'disp': DISPUTE_TIME}).fetchall()


def _decline_deal(deal_id, symbol, session):
    ident, amount, seller_id = session.execute(
        """
            SELECT identificator, amount_subunit_frozen, seller_id 
            FROM deal 
            WHERE id = :id
        """, {'id': deal_id}
    ).fetchone()
    unfreeze(amount_subunits=amount, user_id=seller_id, symbol=symbol, msg=f'Dispute closed, deal={ident}', session=session)
    session.execute(
        "UPDATE deal SET state = :state, cancel_reason = 'dispute', end_time = NOW() WHERE id = :id",
        {'state': STATES[-1], 'id': deal_id}
    )


def _process_dispute(deal_id, identificator, symbol, is_initiator_seller, session):
    deal = dh.get_deal_for_update_state(symbol, identificator, session)
    # check that deal is closed in time of dispute timeout
    if deal['state'] in ('closed', 'deleted'):
        return

    if is_initiator_seller:
        _decline_deal(deal_id, symbol, session)
    else:
        dh._process_deal(symbol, deal, is_dispute=True, session=session)

    session.execute("UPDATE dispute SET is_closed = TRUE WHERE deal_id = :did", {'did': deal_id})

    for side in ('buyer_id', 'seller_id'):
        create_closed_dispute_notification(deal[side], symbol, deal_id, session)


def update_disputes():
    with session_scope() as session:
        data = _get_data(session)

    for did, identificator, symbol, is_initiator_seller in data:
        try:
            with session_scope() as session:
                _process_dispute(did, identificator, symbol, is_initiator_seller, session)
        except Exception as e:
            logger.exception(e)
