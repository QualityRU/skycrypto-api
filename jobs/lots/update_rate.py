from collections import defaultdict
from decimal import Decimal

from utils.db_sessions import session_scope
from data_handler import dh


def check_limits():
    q = "SELECT currency, symbol, rate FROM rates"
    with session_scope() as session:
        rates = []
        variations = {}
        for currency, symbol, rate in session.execute(q):
            item = [currency, symbol, rate]
            rate_variation = variations.get(currency)
            if rate_variation is None:
                rate_variation = session.execute("SELECT rate_variation FROM currency WHERE id = :currency", {'currency': currency}).scalar()
                variations[currency] = rate_variation
            item.append(rate_variation)
            rates.append(tuple(item))

    for currency, symbol, rate, max_variation in rates:
        variation = max_variation * rate
        maximum = rate + variation
        minimum = rate - variation
        with session_scope() as session:
            session.execute(
                """
                    UPDATE lot
                    SET rate = :maximum
                    WHERE rate > :maximum 
                        AND currency = :currency 
                        AND symbol = :symbol
                """, {'maximum': maximum, 'currency': currency, 'symbol': symbol}
            )
        with session_scope() as session:
            session.execute(
                """
                    UPDATE lot 
                    SET rate = :minimum 
                    WHERE rate < :minimum
                        AND currency = :currency 
                        AND symbol = :symbol
                """, {'minimum': minimum, 'currency': currency, 'symbol': symbol}
            )


def _get_rates_dict(session):
    res = defaultdict(lambda: defaultdict(int))
    for symbol, currency, rate in session.execute("SELECT symbol, currency, rate FROM rates").fetchall():
        res[symbol][currency] = rate
    return res


def update_lots():
    with session_scope() as session:
        rates = _get_rates_dict(session)
        lots = session.execute('SELECT id, rate, symbol, currency, coefficient FROM lot WHERE coefficient IS NOT NULL AND NOT is_deleted').fetchall()
        q = ""
        for lid, rate, symbol, currency, coeff in lots:
            new_rate = rates[symbol][currency] * coeff
            q += f"UPDATE lot SET rate = {new_rate} WHERE id = {lid};"
        session.execute(q)
    check_limits()
