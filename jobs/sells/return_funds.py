from decimal import Decimal

from crypto.manager import manager
from data_handler import dh
from system.constants import Action, OperationTypes
from system.funds_changer import change_balance
from utils.db_sessions import session_scope
from utils.utils import get_sales_to_deprecate, update_sell, create_operation, update_operation, get_merchant


def _is_active_deal_exist(sale_id, session) -> bool:
    return session.execute(
        """
            SELECT EXISTS(
                SELECT 1
                FROM deal
                WHERE sell_id = :id AND state NOT IN ('closed', 'deleted')
            )
        """, {'id': sale_id}
    ).scalar()


def _get_user_id_by_email(email, session) -> int:
    return session.execute(
        'SELECT id FROM "user" WHERE email = :email',
        {'email': email}
    ).scalar()


def return_funds():
    sales = get_sales_to_deprecate(user_id=-1)
    for sale in sales:
        with session_scope() as session:
            is_deal_exists = _is_active_deal_exist(sale['id'], session)
            if not is_deal_exists:
                user_id = _get_user_id_by_email(sale['email'], session)
                balance = dh.get_balance(user_id, session)
                if balance > 0:
                    msg = f'Processing temp seller balance, {sale["id"]}'
                    change_balance(user_id, msg, amount_subunits=-balance, session=session, symbol=sale['symbol'])
                    if sale['status'] in (0, 1, 3):
                        change_balance(
                            sale['merchant_id'], msg=msg, amount_subunits=balance,
                            session=session, symbol=sale['symbol']
                        )
                        update_operation(
                            session, sale['merchant_id'], sale['id'],
                            data={'commission': 0, 'amount': 0, 'amount_currency': 0}
                        )
                        update_sell(
                            user_id=-1, sell_id=sale['id'],
                            data={
                                'is_finally_processed': True,
                                'status': 3,
                                'token': None,
                                'callback_url': get_merchant(sale['merchant_id'], session).get('callback_url_sale')
                             }
                        )
