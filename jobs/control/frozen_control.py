
import logging
import os
from decimal import Decimal

from telegram import Bot, ParseMode
from telegram.ext import Defaults

from utils.db_sessions import session_scope
from utils.frozen_control_bot import bot

system_chat_id = os.getenv('FROZEN_CONTROL_CHAT_ID')

logging.basicConfig(level=logging.ERROR,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger()


# noinspection DuplicatedCode
def get_frozen(user_id, symbol, session):
    frozen = session.execute(
        'SELECT frozen FROM wallet WHERE user_id = :uid AND symbol = :symbol LIMIT 1',
        {'uid': user_id, 'symbol': symbol}
    ).scalar()
    return frozen


def get_active_deals(seller_id, symbol, session):
    deals = session.execute(
        """
            SELECT identificator, amount_subunit_frozen
            FROM deal
            WHERE seller_id = :uid AND symbol = :symbol AND state not in ('closed', 'deleted')
        """, {'uid': seller_id, 'symbol': symbol}
    ).fetchall()
    return [dict(item) for item in deals]


def _get_wallet_id(user_id, symbol):
    with session_scope() as session:
        wallet_id = session.execute(
            'SELECT id FROM wallet WHERE user_id = :uid AND symbol = :symbol',
            {'uid': user_id, 'symbol': symbol}
        ).scalar()
    return wallet_id


def get_active_promocodes(creator_id, symbol, session):
    wallet_id = _get_wallet_id(creator_id, symbol)
    promocodes = session.execute(
        """
            SELECT code, coalesce(count(pa.promocode_id), 0) as activations, count, amount
            FROM promocodes p
            LEFT JOIN promocodeactivations pa on p.id = pa.promocode_id
            WHERE p.wallet_id = :wid AND NOT is_deleted
            GROUP BY p.id
            HAVING p.count > count(pa.promocode_id)
        """, {'wid': wallet_id}
    )
    return [dict(item) for item in promocodes]


def get_active_withdrawals(user_id, symbol, session):
    wallet_id = _get_wallet_id(user_id, symbol)
    withdrawals = session.execute(
        """
            SELECT to_address, amount_units, commission, sky_commission
            FROM transactions t
            WHERE NOT is_confirmed AND type = 'out' AND wallet_id = :wid AND NOT t.is_deleted AND tx_hash IS NULL
        """, {'wid': wallet_id}
    ).fetchall()
    return [dict(item) for item in withdrawals]


def to_units(amount, symbol):
    return amount * Decimal(str(10 ** -8 if symbol == 'btc' else 10 ** -18))


def get_frozen_imbalance(nickname, symbol, session, verbose=1):
    user_id = session.execute('SELECT id FROM "user" WHERE nickname = :nick', {'nick': nickname}).scalar()
    if user_id is None:
        raise ValueError(f'No such user "{nickname}"')
    deals = get_active_deals(user_id, symbol, session)
    promocodes = get_active_promocodes(user_id, symbol, session)
    frozen = get_frozen(user_id, symbol, session)
    withdrawals = get_active_withdrawals(user_id, symbol, session)
    try:
        frozen_balance = (
                frozen
                - sum(deal['amount_subunit_frozen'] for deal in deals)
                - sum(p['amount'] * (p['count'] - p['activations']) for p in promocodes)
        )
    except Exception as e:
        logger.exception(e)
        logger.info('Promocodes:')
        for p in promocodes:
            logger.info(f'{p["amount"]} * ({p["count"]} - {p["activations"]})')
        raise
    frozen_balance = to_units(frozen_balance, symbol) - sum(w['amount_units'] + (w['commission'] or w['sky_commission']) for w in withdrawals)
    text = ''
    if frozen_balance != 0:
        text += f'Frozen balance user {nickname}: {frozen_balance}\n'
        text += f'Frozen: {to_units(frozen, symbol)}\n'

        if verbose > 0:
            if deals:
                text += '\nDeals:\n'
                for deal in deals:
                    fr = to_units(deal["amount_subunit_frozen"], symbol)
                    text += f'/d{deal["identificator"]}: {fr}\n'

            if promocodes:
                text += '\nPromocodes:\n'
                for p in promocodes:
                    fr = to_units(p["amount"], symbol) * (p['count'] - p['activations'])
                    text += f'count {p["count"]}, activations {p["activations"]}\n'
                    text += f'{p["code"]}: {fr}\n\n'

            if withdrawals:
                text += 'Withdrawals:\n'
                for w in withdrawals:
                    text += f'amount {w["amount_units"]}, address {w["to_address"]}\n'

        try:
            bot.send_message(chat_id=system_chat_id, text=text)
        except:
            print(text)

        bot.send_message(chat_id=system_chat_id, text=f'/addb {nickname} {frozen_balance}')
        bot.send_message(chat_id=system_chat_id, text=f'/addf {nickname} {-frozen_balance}')


def get_active_users(last_minutes):
    with session_scope() as session:
        nicknames = session.execute(
            f'''
                SELECT nickname
                FROM "user"
                WHERE last_action > NOW() - INTERVAL '{last_minutes} minutes' AND NOT is_temporary
            '''
        ).fetchall()
    return [item[0] for item in nicknames]


def control():
    nicknames = get_active_users(last_minutes=5)
    for user in nicknames:
        with session_scope() as session:
            get_frozen_imbalance(user, 'btc', session=session, verbose=1)
    # bot.send_message(chat_id=system_chat_id, text=f'Проверено {len(nicknames)} юзеров онлайн')

