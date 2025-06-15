from uuid import uuid4

from data_handler import dh
from system.constants import Action, OperationTypes
from system.funds_changer import change_balance
from utils.db_sessions import session_scope
from utils.utils import get_not_approved_sells, approve_sell, decline_sell, generate_nickname, create_operation, \
    get_merchant_commission


def _create_user(session):
    return session.execute(
        """
            INSERT INTO "user" (nickname, email, is_temporary)
            VALUES (:nick, :email, :is_temp)
            RETURNING id, email
        """,
        {
            'nick': generate_nickname('fs', session=session),
            'email': f'{uuid4().hex[:15]}@noemail.fkfl',
            'is_temp': True
        }
    ).fetchone()


def create_wallet(user_id, symbol, session):
    session.execute(
        """
            INSERT INTO wallet (user_id, symbol, private_key) 
            VALUES (:user_id, :symbol, NULL)
        """, {'user_id': user_id, 'symbol': symbol}
    )


def process_sells():
    unapproved_sells = get_not_approved_sells(user_id=-1)
    for sell in unapproved_sells:
        with session_scope() as session:
            wallet = dh.get_wallet(sell['symbol'], sell['merchant_id'], session)
            rate = dh.get_rate(sell['symbol'], sell['currency'], session)
            commission = get_merchant_commission(sell['merchant_id'], session)
            amount_units = sell['amount'] / float(rate)
            commission_units = amount_units * (0.04 + float(commission))
            target_amount = amount_units + commission_units
            if wallet['balance'] < target_amount:
                decline_sell(-1, sell['id'])
            else:
                user_id, email = _create_user(session)
                create_wallet(user_id, sell['symbol'], session)

                msg = f'Approve sale, {sell["id"]}'
                change_balance(sell['merchant_id'], msg, symbol=sell['symbol'], amount=-target_amount, session=session)
                change_balance(user_id, msg, symbol=sell['symbol'], amount=target_amount, session=session)
                create_operation(
                    session, sell['merchant_id'], sell['id'],
                    sell['symbol'], sell['currency'], -target_amount, action=Action.sky_sale,
                    operation_type=OperationTypes.public_api, amount_currency=sell['amount'],
                    commission=commission_units
                )

                approve_sell(user_id, sell['id'], email)
