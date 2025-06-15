from crypto.manager import manager
from data_handler import dh
from utils.db_sessions import session_scope
from utils.utils import update_rates, update_actual_rates


def _get_best_rates_buy(symbol, currency, session):
    subunits_in_unit = manager.to_subunit(symbol=symbol, val=1)
    q = """
                SELECT broker_id as broker, MIN(l.rate) as rate
                FROM lot l
                LEFT JOIN "user" u ON l.user_id = u.id
                LEFT JOIN wallet w on u.id = w.user_id
                WHERE l.symbol = :sym AND w.symbol = :sym AND l.is_active AND NOT l.is_deleted AND l.type = 'sell' AND
                    l.currency = :cur AND NOT u.is_baned AND limit_to >= limit_from AND
                    NOT u.is_deleted AND w.is_active AND limit_from/rate*:sub <= w.balance AND 100/rate*:sub <= w.balance AND
                    is_verify AND sky_pay
                GROUP BY l.broker_id
            """
    kw = {'sym': symbol, 'cur': currency, 'sub': subunits_in_unit}
    return session.execute(q, kw).fetchall()


def _get_best_rates_sell(symbol, currency, session):
    subunits_in_unit = manager.to_subunit(symbol=symbol, val=1)
    q = """
                SELECT broker_id as broker, MAX(l.rate) as rate
                FROM lot l
                LEFT JOIN "user" u ON l.user_id = u.id
                LEFT JOIN wallet w on u.id = w.user_id
                WHERE l.symbol = :sym AND w.symbol = :sym AND l.is_active AND NOT l.is_deleted AND l.type = 'buy' AND
                    l.currency = :cur AND NOT u.is_baned AND limit_to >= limit_from AND
                    NOT u.is_deleted AND w.is_active AND is_verify AND sky_pay AND allow_sell
                GROUP BY l.broker_id
            """
    kw = {'sym': symbol, 'cur': currency, 'sub': subunits_in_unit}
    return session.execute(q, kw).fetchall()


def update_v2_rates():
    with session_scope() as session:
        for currency in dh.get_currencies(session):
            currency = currency['id']
            brokers = dh.get_brokers(session, currency=currency)
            broker_id_to_name = {b['id']: b['name'] for b in brokers}
            for method, lot_type in ((_get_best_rates_buy, 'sell'), (_get_best_rates_sell, 'buy')):
                for symbol in manager.currencies.keys():
                    data = method(symbol, currency, session)
                    data_to_send = []
                    for item in data:
                        broker_name = broker_id_to_name.get(str(item['broker']))
                        if broker_name:
                            data_to_send.append({'broker': broker_name, 'rate': item['rate']})
                    update_rates(data=data_to_send, symbol=symbol, currency=currency, lot_type=lot_type)


def update_v2_actual_rates():
    with session_scope() as session:
        rates = session.execute('SELECT symbol, rate, currency FROM rates').fetchall()
        for rate in rates:
            update_actual_rates(data={'rate': rate['rate']}, symbol=rate['symbol'], currency=rate['currency'])
