import time
from decimal import Decimal

from data_handler import dh
from system.constants import DealTypes
from utils.db_sessions import session_scope
from utils.logger import logger
from utils.utils import get_payments_v2_to_process, \
    update_payment_v2


def get_amounts(payment_v2, rate):
    if payment_v2['is_currency_amount']:
        amount = Decimal(payment_v2['amount']) / Decimal(rate)
        amount_currency = round(Decimal(str(payment_v2['amount'])), 2)
    else:
        amount = Decimal(str(payment_v2['amount']))
        amount_currency = round(Decimal(payment_v2['amount']) * Decimal(rate), 2)
    return amount, amount_currency


def search_api_payment_v2_lot(payment_v2, amount, amount_currency, exclude_lots, currency, session):
    target_amount = round(amount * Decimal('1.26'), 8)

    res = session.execute(
        f"""
            SELECT l.identificator
            FROM lot l 
            JOIN "user" u ON l.user_id = u.id
            JOIN wallet w on u.id = w.user_id and w.symbol = :sym
            WHERE u.is_verify AND broker_id = :broker_id AND type = 'sell' AND last_action > NOW() - INTERVAL '3 hours' 
                AND l.symbol = :sym AND balance >= :min_bal AND l.is_active AND w.is_active and l.currency = :cur
                AND NOT l.is_deleted AND allow_sell AND u.id not in (SELECT DISTINCT seller_id FROM deal d WHERE payment_v2_id = :payment_v2_id)
                AND :amount_currency < limit_to AND l.identificator not in :excl AND u.allow_payment_v2
            ORDER BY rate DESC
            LIMIT 1
        """, {
            'sym': payment_v2['symbol'],
            'broker_id': payment_v2['broker_id'],
            'payment_v2_id': payment_v2['id'],
            'amount_currency': amount_currency,
            'min_bal': target_amount,
            'excl': exclude_lots if exclude_lots else ('1',),
            'cur': currency
        }
    ).scalar()

    return res


def _create_deal(payment_v2, amount_currency, amount, lot, rate, session):
    deal = dh.create_new_deal(
        payment_v2['symbol'], payment_v2['merchant_id'],
        lot['identificator'],
        amount_currency=amount_currency,
        amount=amount,
        rate=rate,
        session=session,
        deal_type=DealTypes.sky_pay_v2,
        payment_v2_id=payment_v2['id'],
        requisite=None
    )
    update_payment_v2(
        user_id=payment_v2['merchant_id'],
        payment_v2_id=payment_v2['id'],
        data={'status': 1, 'deal': deal['identificator']}
    )


def process_payments_v2():
    payments_v2_to_process = get_payments_v2_to_process()
    for payment_v2 in payments_v2_to_process:
        with session_scope() as session:
            rate = dh.get_rate(payment_v2['symbol'], payment_v2['currency'], session)
            rate = round(rate * Decimal('1.08'), 4)
            amount, amount_currency = get_amounts(payment_v2, rate)
            try_number = 0
            success = False
            exclude_lots = []
            while not success and try_number < 5:
                try:
                    lot_id = search_api_payment_v2_lot(payment_v2, amount, amount_currency, tuple(exclude_lots), payment_v2['currency'], session)
                    if lot_id:
                        lot = dh.get_lot(lot_id, session)
                        _create_deal(payment_v2, amount_currency, amount, lot, rate, session)
                        success = True
                    else:
                        break
                except Exception as e:
                    logger.exception(e)
                    time.sleep(1)
                    try_number += 1
                    exclude_lots.append(lot_id)
