from utils.db_sessions import session_scope


def test_test(user, wallet, broker, broker_currency, lot, deal):
    print(deal)
    with session_scope() as session:
        pass
