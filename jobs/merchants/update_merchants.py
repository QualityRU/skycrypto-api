from crypto.manager import manager
from utils.db_sessions import session_scope
from utils.utils import update_merchants


def update_v2_merchants():
    with session_scope() as session:
        balances_data = session.execute(
            """
                SELECT u.id, symbol, balance
                FROM merchant
                JOIN "user" u on u.id = merchant.user_id
                JOIN wallet w on u.id = w.user_id
            """
        ).fetchall()
        rates = {
            symbol: rate
            for rate, symbol in
            session.execute("SELECT rate, symbol FROM rates WHERE currency = 'rub'").fetchall()
        }
        final_data = []
        for merch_id, symbol, balance in balances_data:
            if symbol not in manager.currencies.keys():
                continue
            balance = manager.from_subunit(symbol, balance)
            final_data.append(
                {
                    'id': merch_id,
                    'symbol': symbol,
                    'balance': balance,
                    'balance_rub': balance * rates[symbol]
                }
            )
        update_merchants(final_data)
