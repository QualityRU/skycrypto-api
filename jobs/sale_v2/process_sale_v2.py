from decimal import Decimal

from werkzeug.exceptions import BadRequest

from data_handler import dh
from system.constants import DealTypes
from utils.db_sessions import session_scope
from utils.logger import logger
from utils.notifications_queue import create_deal_notification
from utils.utils import get_sale_v2_to_process, update_sale_v2, cancel_sale_v2


def super_buy_search(broker_id, symbol, sale_v2_id, session):
    res = session.execute(
        """
            SELECT l.identificator
            FROM lot l
            JOIN "user" u ON l.user_id = u.id
            JOIN wallet w ON u.id = w.user_id and w.symbol = :sym
            JOIN broker b ON b.id = l.broker_id
            WHERE u.is_verify AND broker_id = :broker_id AND type = 'buy' AND last_action > NOW() - INTERVAL '3 hours'
                AND l.symbol = :sym AND l.is_active AND w.is_active and l.currency = 'rub'
                AND NOT l.is_deleted AND allow_sale_v2 AND u.id not in (SELECT buyer_id FROM deal d WHERE sale_v2_id = :sale_v2_id)
                AND b.sale_v2 AND u.super_verify_only
            ORDER BY random()
            LIMIT 1
        """, {'sym': symbol, 'broker_id': broker_id, 'sale_v2_id': sale_v2_id}
    ).scalar()
    return res


def online_search_by_interval(broker_id, symbol, sale_v2_id, interval, session):
    res = session.execute(
        """
            SELECT l.identificator
            FROM lot l
            JOIN "user" u ON l.user_id = u.id
            JOIN wallet w ON u.id = w.user_id and w.symbol = :sym
            JOIN broker b ON b.id = l.broker_id
            WHERE u.is_verify AND broker_id = :broker_id AND type = 'buy' AND last_action > NOW() - INTERVAL :interval
                AND l.symbol = :sym AND l.is_active AND w.is_active and l.currency = 'rub'
                AND NOT l.is_deleted AND u.id not in (SELECT buyer_id FROM deal d WHERE sale_v2_id = :sale_v2_id)
                AND b.sale_v2 AND u.allow_sale_v2
            ORDER BY random()
            LIMIT 1
        """, {'sym': symbol, 'broker_id': broker_id, 'sale_v2_id': sale_v2_id, 'interval': interval}
    ).scalar()
    return res


def search_api_sale_v2_lot(broker_id, symbol, sale_v2_id, session):
    res = super_buy_search(broker_id, symbol, sale_v2_id, session)
    if not res:
        res = online_search_by_interval(broker_id, symbol, sale_v2_id, '2 hours', session)
        if not res:
            res = online_search_by_interval(broker_id, symbol, sale_v2_id, '24 hours', session)

    return res


def process_sale_v2():
    sale_v2_to_process = get_sale_v2_to_process()
    for sale_v2 in sale_v2_to_process:
        with session_scope() as session:
            lot_id = search_api_sale_v2_lot(sale_v2['broker_id'], sale_v2['symbol'], sale_v2['id'], session)
            if lot_id:
                lot = dh.get_lot(lot_id, session)
                rate = round(dh.get_rate(sale_v2['symbol'], 'rub', session) * Decimal('0.99'), 2)
                try:
                    deal = dh.create_new_deal(
                        sale_v2['symbol'], sale_v2['merchant_id'],
                        lot['identificator'], requisite=sale_v2['requisites'],
                        amount_currency=sale_v2['amount'],
                        amount=round(sale_v2['amount'] / rate, 6),
                        rate=rate,
                        session=session,
                        deal_type=DealTypes.sky_sale_v2,
                        sale_v2_id=sale_v2['id'],
                        create_notification=False,
                        expand_id=True
                    )
                except BadRequest as e:
                    if 'insufficient funds' in e.description:
                        cancel_sale_v2(
                            user_id=sale_v2['merchant_id'], sale_v2_id=sale_v2['id'],
                            session=session, reason='insufficient funds'
                        )
                        continue
                except Exception as e:
                    logger.exception(e)
                    continue
                update_sale_v2(user_id=sale_v2['merchant_id'], sale_v2_id=sale_v2['id'], data={'status': 1, 'deal': deal['identificator']})
                create_deal_notification(lot['user_id'], deal['id'], session, n_type='deal')
