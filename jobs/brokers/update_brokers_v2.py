from utils.db_sessions import session_scope
from utils.utils import update_brokers_v2


def get_currencies(broker_id, session):
    currencies = session.execute('SELECT currency FROM broker_currency WHERE broker_id = :bid', {'bid': broker_id}).fetchall()
    return [item['currency'] for item in currencies]


def update_brokers():
    with session_scope() as session:
        data = session.execute('SELECT id, name, is_deleted, sky_pay, sale_v2, is_card FROM broker').fetchall()
        data = [
            dict(
                item,
                id=str(item['id']),
                currencies=get_currencies(broker_id=str(item['id']), session=session)
            ) for item in data
        ]
    update_brokers_v2(data)
