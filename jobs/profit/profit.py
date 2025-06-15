from utils.db_sessions import session_scope
from crypto.manager import manager
from utils.logger import logger


def get_node_balance(symbol):
    if symbol == 'btc':
        return manager.currencies['btc'].get_node_balance(0)
    else:
        return manager.from_subunit(symbol, manager.get_balance(symbol, None))


def get_users_balance(session, symbol):
    return manager.from_subunit(
        symbol,
        session.execute(
            'SELECT SUM(balance) + SUM(frozen) FROM wallet WHERE symbol = :sym', {'sym': symbol}
        ).scalar()
    )


def write_profit(session, symbol, wallet_balance, users_balance, profit):
    session.execute(
        """
            INSERT INTO profit (symbol, wallet_balance, users_balance, profit)
            VALUES (:sym, :wb, :ub, :profit)
        """, {'sym': symbol, 'wb': wallet_balance, 'ub': users_balance, 'profit': profit}
    )


def create_notification_if_needed(profit, symbol, session):
    last_profit = session.execute(
        'SELECT profit FROM profit WHERE symbol = :sym ORDER BY created_at DESC LIMIT 1',
        {'sym': symbol}
    ).scalar()
    if last_profit is not None:
        income = profit - last_profit
        if last_profit != profit and round(income, 8) != 0:
            session.execute('INSERT INTO earnings (symbol, income) VALUES (:sym, :inc)', {'sym': symbol, 'inc': income})


def update_profit():
    with session_scope() as session:
        for symbol in manager.currencies.keys():
            wallet_balance = get_node_balance(symbol)
            users_balance = get_users_balance(session, symbol)
            profit = wallet_balance - users_balance
            create_notification_if_needed(profit, symbol, session)
            write_profit(session, symbol, wallet_balance, users_balance, profit)
        session.execute("DELETE FROM profit WHERE created_at < now() - INTERVAL '30 days'")
