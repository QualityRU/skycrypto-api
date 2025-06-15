import random
import string
import calendar
from datetime import datetime, timezone, date
from os import environ

import jwt
import pytz
import requests
from pdfid import pdfid

from system.settings import db
from system.constants import (
    NICKNAME_DIGITS, NICKNAME_LETTERS, PROMOCODE_LENGTH, LOT_ID_LENGTH, DEAL_ID_LENGTH, TOKEN_LENGTH, FILENAME_LENGTH,
    REF_CODE_LENGTH, CAMPAIGN_ID_LENGTH, OperationTypes, ADMIN_ROLE, PUBLIC_API_HOST)
from utils.db_sessions import session_scope


def get_nickname(prefix):
    final_nick = ''.join(random.choices(string.digits, k=NICKNAME_DIGITS))
    final_nick += ''.join(random.choices(string.ascii_letters, k=NICKNAME_LETTERS))
    return prefix + final_nick


def get_promocode():
    return ''.join(random.choices(string.ascii_letters, k=PROMOCODE_LENGTH))


def get_deal_id():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=DEAL_ID_LENGTH))


def get_lot_id():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=LOT_ID_LENGTH))


def get_token():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=TOKEN_LENGTH))


def generate_filename():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=FILENAME_LENGTH))


def generate_ref_code():
    return ''.join(random.choices(string.ascii_uppercase, k=REF_CODE_LENGTH))


def generate_campaign_id():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=CAMPAIGN_ID_LENGTH))


def validate_amounts(meth):
    def wrap(*args, **kwargs):
        amount_subunits = kwargs.get('amount_subunits')
        amount = kwargs.get('amount')
        if (not amount_subunits and not amount) or (amount_subunits and amount):
            raise ValueError('amount must be passed correctly')
        return meth(*args, **kwargs)
    return wrap


def generate_nickname(prefix='', session=None):
    if session:
        return generate_nickname_session(prefix, session)
    else:
        with session_scope() as session:
            return generate_nickname_session(prefix, session)


def generate_nickname_session(prefix, session):
    def _is_exist(nick):
        return session.execute(
            'SELECT EXISTS(SELECT 1 FROM "user" WHERE nickname = :nick)',
            {'nick': nick}
        ).scalar()
    exists = True
    while exists:
        nickname = get_nickname(prefix)
        exists = _is_exist(nickname)
    return nickname


def generate_promocode():
    def _is_exist(_code):
        return db.execute(f"SELECT EXISTS(SELECT 1 FROM promocodes WHERE code = '{_code}')").fetchone()[0]
    exists = True
    while exists:
        code = get_promocode()
        exists = _is_exist(code)
    return code


def generate_lot_id():
    def _is_exist(_id):
        return db.execute(f"SELECT EXISTS(SELECT 1 FROM lot WHERE identificator = '{_id}')").fetchone()[0]
    exists = True
    while exists:
        code = get_lot_id()
        exists = _is_exist(code)
    return code


def generate_deal_id():
    def _is_exist(_id):
        return db.execute(f"SELECT EXISTS(SELECT 1 FROM deal WHERE identificator = '{_id}')").fetchone()[0]
    exists = True
    while exists:
        code = get_deal_id()
        exists = _is_exist(code)
    return code


def create_operation(
        session, user_id, operation_id, symbol, currency,
        amount, action, operation_type=OperationTypes.plain,
        commission=None, amount_currency=None, label=None,
        trader_commission=None, commission_currency=None
):
    session.execute(
        """
            INSERT INTO operations (
                id, user_id, type, amount,
                symbol, currency, action, commission,
                amount_currency, label,
                trader_commission, commission_currency
            )
            VALUES (:opid, :uid, :type, :amount, :symbol, :currency, :action, :commission, :amount_currency, :label, 
                :trader_commission, :commission_currency)
        """, {
            'opid': operation_id, 'uid': user_id, 'type': operation_type,
            'amount': amount, 'symbol': symbol, 'currency': currency, 'action': action,
            'amount_currency': amount_currency, 'commission': commission,
            'label': label, 'trader_commission': trader_commission,
            'commission_currency': commission_currency
        }
    )


def update_operation(session, user_id, op_id, data):
    updates = [f'{k} = {v}' for k, v in data.items()]
    updates_string = ', '.join(updates)
    session.execute(
        f"UPDATE operations SET {updates_string} WHERE user_id = :uid AND id = :oid",
        {'uid': user_id, 'oid': op_id}
    )


def get_jwt_admin_token(user_id, salt):
    return jwt.encode({
        'user_id': user_id,
        'role_id': ADMIN_ROLE
    }, salt, algorithm='HS256').decode('utf-8')


def _get_purchase(user_id, purchase_id):
    headers = {'Authorization': f'Bearer {get_jwt_admin_token(user_id, environ["PUBLIC_APP_KEY"])}'}
    res = requests.get(PUBLIC_API_HOST + f'/purchases/{purchase_id}', headers=headers)
    res.raise_for_status()
    purchase = res.json()
    return purchase


def get_purchase(user_id, purchase_id):
    #  Split the function into 2 parts so that it can be patched when running tests
    return _get_purchase(user_id, purchase_id)


def update_purchase(user_id, purchase_id, data):
    headers = {'Authorization': f'Bearer {get_jwt_admin_token(user_id, environ["PUBLIC_APP_KEY"])}'}
    res = requests.patch(
        PUBLIC_API_HOST + f'/purchases/{purchase_id}',
        headers=headers,
        json=data
    )
    res.raise_for_status()


def get_payments_to_deprecate():
    headers = {'Authorization': f'Bearer {get_jwt_admin_token(0, environ["PUBLIC_APP_KEY"])}'}
    res = requests.get(
        PUBLIC_API_HOST + '/purchases-to-deprecate',
        headers=headers
    )
    res.raise_for_status()
    return res.json()


def get_payments_v2_to_deprecate():
    headers = {'Authorization': f'Bearer {get_jwt_admin_token(0, environ["PUBLIC_APP_KEY"])}'}
    res = requests.get(
        PUBLIC_API_HOST + '/payments_v2-to-deprecate',
        headers=headers
    )
    res.raise_for_status()
    return res.json()


def update_merchants(data):
    headers = {'Authorization': f'Bearer {get_jwt_admin_token(0, environ["PUBLIC_APP_KEY"])}'}
    res = requests.post(
        PUBLIC_API_HOST + '/update-merchants',
        headers=headers,
        json=data
    )
    res.raise_for_status()


def update_rates(data, symbol, currency, lot_type):
    headers = {'Authorization': f'Bearer {get_jwt_admin_token(0, environ["PUBLIC_APP_KEY"])}'}
    res = requests.post(
        PUBLIC_API_HOST + f'/update-rates/{symbol}?currency={currency}&lot_type={lot_type}',
        headers=headers,
        json=data
    )
    res.raise_for_status()


def update_actual_rates(data, symbol, currency):
    headers = {'Authorization': f'Bearer {get_jwt_admin_token(0, environ["PUBLIC_APP_KEY"])}'}
    res = requests.post(
        PUBLIC_API_HOST + f'/update-actual-rates/{symbol}?currency={currency}',
        headers=headers,
        json=data
    )
    res.raise_for_status()


def update_brokers_v2(data):
    headers = {'Authorization': f'Bearer {get_jwt_admin_token(0, environ["PUBLIC_APP_KEY"])}'}
    res = requests.post(
        PUBLIC_API_HOST + f'/brokers-update',
        headers=headers,
        json=data
    )
    res.raise_for_status()


def begin_purchase(user_id, purchase_id):
    update_purchase(user_id, purchase_id, data={'status': 1})


def get_merchant(merchant_id, session):
    res = session.execute(
        """
            SELECT user_id as id, name, website, image_url, commission, callback_url, callback_url_sale, required_mask, callback_safe, callback_url_cpay
            FROM merchant
            WHERE user_id = :id
        """, {"id": merchant_id}
    ).fetchone()
    if res:
        return dict(res)


def _complete_purchase(user_id, purchase_id, tx_hash, received_crypto, rate):
    with session_scope() as session:
        merchant = get_merchant(user_id, session)
    add_data = {}
    if tx_hash:
        add_data['tx_hash'] = tx_hash
    update_purchase(user_id, purchase_id, data={
        'status': 2,
        'processed_at': str(datetime.now(timezone.utc)),
        'token': None,
        'received_crypto': received_crypto,
        'callback_url': merchant['callback_url'],
        'safe': merchant['callback_safe'],
        'rate': rate,
        **add_data}
    )


def complete_purchase(user_id, purchase_id, tx_hash, received_crypto, rate):
    #  Split the function into 2 parts so that it can be patched when running tests
    return _complete_purchase(user_id, purchase_id, tx_hash, received_crypto, rate)


def _complete_payment_v2(user_id, purchase_id, received_crypto):
    with session_scope() as session:
        merchant = get_merchant(user_id, session)

    update_payment_v2(
        user_id,
        purchase_id,
        data={
            'status': 2,
            'processed_at': str(datetime.now(timezone.utc)),
            'received_crypto': received_crypto,
            'callback_url': merchant['callback_url'],
            'safe': merchant['callback_safe']
        }
    )


def complete_payment_v2(user_id, purchase_id, received_crypto):
    #  Split the function into 2 parts so that it can be patched when running tests
    return _complete_payment_v2(user_id, purchase_id, received_crypto)


def decline_purchase(user_id, purchase_id):
    with session_scope() as session:
        merchant = get_merchant(user_id, session)
    update_purchase(user_id, purchase_id, data={'status': 3, 'token': None, 'callback_url': merchant['callback_url']})


def decline_payment_v2(user_id, purchase_id):
    with session_scope() as session:
        merchant = get_merchant(user_id, session)
    update_payment_v2(user_id, purchase_id, data={'status': 3, 'callback_url': merchant['callback_url']})


def call_v2_to_items_process(item_type, postfix='process'):
    if item_type not in ('sale-v2', 'payments-v2', 'withdrawals-v2', 'cpayments'):
        raise ValueError
    headers = {'Authorization': f'Bearer {get_jwt_admin_token(-1, environ["PUBLIC_APP_KEY"])}'}
    res = requests.get(PUBLIC_API_HOST + f'/{item_type}-to-{postfix}', headers=headers)
    res.raise_for_status()
    return res.json()

def get_sale_v2_to_process():
    return call_v2_to_items_process('sale-v2')


def get_payments_v2_to_process():
    return call_v2_to_items_process('payments-v2')


def get_payments_v2_to_complete():
    return call_v2_to_items_process('payments-v2', postfix='complete')


def get_withdrawals_v2_to_process():
    return call_v2_to_items_process('withdrawals-v2')


def get_cpayments_to_process():
    return call_v2_to_items_process('cpayments')


def get_not_approved_sells(user_id):
    headers = {'Authorization': f'Bearer {get_jwt_admin_token(user_id, environ["PUBLIC_APP_KEY"])}'}
    res = requests.get(PUBLIC_API_HOST + f'/sells-on-approve', headers=headers)
    res.raise_for_status()
    return res.json()


def get_sales_to_deprecate(user_id):
    headers = {'Authorization': f'Bearer {get_jwt_admin_token(user_id, environ["PUBLIC_APP_KEY"])}'}
    res = requests.get(PUBLIC_API_HOST + f'/sells-on-deprecate', headers=headers)
    res.raise_for_status()
    return res.json()


def deprecate_inactive_sales(user_id):
    headers = {'Authorization': f'Bearer {get_jwt_admin_token(user_id, environ["PUBLIC_APP_KEY"])}'}
    res = requests.post(PUBLIC_API_HOST + f'/deprecate-inactive-sales', headers=headers)
    res.raise_for_status()
    return res.json()


def deprecate_inactive_sales_v2(user_id):
    headers = {'Authorization': f'Bearer {get_jwt_admin_token(user_id, environ["PUBLIC_APP_KEY"])}'}
    res = requests.post(PUBLIC_API_HOST + f'/deprecate-inactive-sales-v2', headers=headers)
    res.raise_for_status()
    return res.json()


def _get_sell(user_id, sell_id):
    headers = {'Authorization': f'Bearer {get_jwt_admin_token(user_id, environ["PUBLIC_APP_KEY"])}'}
    res = requests.get(PUBLIC_API_HOST + f'/sells/{sell_id}', headers=headers)
    res.raise_for_status()
    return res.json()


def get_sell(user_id, sell_id):
    #  Split the function into 2 parts so that it can be patched when running tests
    return _get_sell(user_id, sell_id)


def get_sale_v2(user_id, sale_v2_id):
    headers = {'Authorization': f'Bearer {get_jwt_admin_token(user_id, environ["PUBLIC_APP_KEY"])}'}
    res = requests.get(PUBLIC_API_HOST + f'/sale_v2/{sale_v2_id}', headers=headers)
    res.raise_for_status()
    return res.json()


def get_cpayment(user_id, cpayment_id):
    headers = {'Authorization': f'Bearer {get_jwt_admin_token(user_id, environ["PUBLIC_APP_KEY"])}'}
    res = requests.get(PUBLIC_API_HOST + f'/cpayments/{cpayment_id}', headers=headers)
    res.raise_for_status()
    return res.json()


def get_withdrawal(user_id, withdrawal_id):
    headers = {'Authorization': f'Bearer {get_jwt_admin_token(user_id, environ["PUBLIC_APP_KEY"])}'}
    res = requests.get(PUBLIC_API_HOST + f'/withdrawals/{withdrawal_id}', headers=headers)
    res.raise_for_status()
    return res.json()


def _get_payment_v2(user_id, payment_v2_id):
    headers = {'Authorization': f'Bearer {get_jwt_admin_token(user_id, environ["PUBLIC_APP_KEY"])}'}
    res = requests.get(PUBLIC_API_HOST + f'/payments_v2/{payment_v2_id}', headers=headers)
    res.raise_for_status()
    return res.json()


def get_payment_v2(user_id, payment_v2_id):
    #  Split the function into 2 parts so that it can be patched when running tests
    return _get_payment_v2(user_id, payment_v2_id)


def update_sell(user_id, sell_id, data):
    headers = {'Authorization': f'Bearer {get_jwt_admin_token(user_id, environ["PUBLIC_APP_KEY"])}'}
    res = requests.patch(
        PUBLIC_API_HOST + f'/sells/{sell_id}',
        headers=headers,
        json=data
    )
    res.raise_for_status()


def begin_sell(user_id, sell_id):
    update_sell(user_id, sell_id, data={'status': 1})


def update_sale_v2(user_id, sale_v2_id, data):
    headers = {'Authorization': f'Bearer {get_jwt_admin_token(user_id, environ["PUBLIC_APP_KEY"])}'}
    res = requests.patch(
        PUBLIC_API_HOST + f'/sale_v2/{sale_v2_id}',
        headers=headers,
        json=data
    )
    res.raise_for_status()


def update_payment_v2(user_id, payment_v2_id, data):
    headers = {'Authorization': f'Bearer {get_jwt_admin_token(user_id, environ["PUBLIC_APP_KEY"])}'}
    res = requests.patch(
        PUBLIC_API_HOST + f'/payments_v2/{payment_v2_id}',
        headers=headers,
        json=data
    )
    res.raise_for_status()


def update_withdrawal_v2(user_id, withdrawal_v2_id, data):
    headers = {'Authorization': f'Bearer {get_jwt_admin_token(user_id, environ["PUBLIC_APP_KEY"])}'}
    res = requests.patch(
        PUBLIC_API_HOST + f'/withdrawals/{withdrawal_v2_id}',
        headers=headers,
        json=data
    )
    res.raise_for_status()


def update_cpayment(user_id, cpayment_id, data):
    headers = {'Authorization': f'Bearer {get_jwt_admin_token(user_id, environ["PUBLIC_APP_KEY"])}'}
    res = requests.patch(
        PUBLIC_API_HOST + f'/cpayments/{cpayment_id}',
        headers=headers,
        json=data
    )
    res.raise_for_status()


def _complete_sell(user_id, sell_id, session):
    merchant = get_merchant(user_id, session=session)
    update_sell(
        user_id, sell_id,
        data={
            'status': 2,
            'processed_at': str(datetime.now(timezone.utc)),
            'token': None,
            'callback_url': merchant.get('callback_url_sale'),
        }
    )


def complete_sell(user_id, sell_id, session):
    #  Split the function into 2 parts so that it can be patched when running tests
    return _complete_sell(user_id, sell_id, session)


def _complete_sale_v2(user_id, sale_v2_id, sent_crypto, session):
    merchant = get_merchant(user_id, session=session)
    update_sale_v2(
        user_id, sale_v2_id,
        data={
            'status': 2,
            'processed_at': str(datetime.now(timezone.utc)),
            'callback_url': merchant.get('callback_url_sale'),
            'sent_crypto': sent_crypto
        }
    )


def complete_sale_v2(user_id, sale_v2_id, sent_crypto, session):
    #  Split the function into 2 parts so that it can be patched when running test
    return _complete_sale_v2(user_id, sale_v2_id, sent_crypto, session)


def cancel_sale_v2(user_id, sale_v2_id, session, reason=None):
    merchant = get_merchant(user_id, session=session)
    update_sale_v2(
        user_id, sale_v2_id,
        data={
            'status': 3,
            'callback_url': merchant.get('callback_url_sale'),
            'cancel_reason': reason
        }
    )


def approve_sell(user_id, sell_id, email):
    update_sell(user_id, sell_id, data={'email': email, 'is_approved': True})


def decline_sell(user_id, sell_id):
    update_sell(user_id, sell_id, data={'is_approved': False})


def create_deal_commission(
        deal_id, symbol, buyer_commission, seller_commission, session,
        buyer_ref_commission=0, seller_ref_commission=0,
        merchant_commission=0
):
    session.execute(
        """
            INSERT INTO deal_commissions (
                deal_id, symbol, buyer_commission,
                seller_commission, referral_commission_buyer,
                referral_commission_seller, merchant_commission
            ) VALUES (
                :deal_id, :symbol, :buyer_commission,
                :seller_commission, :referral_commission_buyer,
                :referral_commission_seller, :merchant_commission
            ) ON CONFLICT DO NOTHING 
        """, {
            'deal_id': deal_id, 'buyer_commission': buyer_commission, 'seller_commission': seller_commission,
            'referral_commission_buyer': buyer_ref_commission, 'referral_commission_seller': seller_ref_commission,
            'merchant_commission': merchant_commission, 'symbol': symbol
        }
    )


def update_deal_commission(deal_id, **data):
    with session_scope() as session:
        session.execute(
            f"""
                UPDATE deal_commissions
                SET {', '.join([f'{field} = :{field}' for field in data.keys()])}
                WHERE deal_id = :deal_id
            """, {'deal_id': deal_id, **data}
        )


def date_iter(year, month):
    for i in range(1, calendar.monthlen(year, month) + 1):
        yield date(year, month, i)


def find_object_by_datetime(objects_list, target_date, fieldname='created_at'):
    return next(filter(lambda x: x[fieldname].date() == target_date, objects_list), None)


def get_merchant_commission(merchant_id, session):
    return session.execute(
        'SELECT commission_sale FROM merchant WHERE user_id = :id',
        {'id': merchant_id}
    ).scalar()


def localize_datetime(dt):
    return dt.replace(tzinfo=pytz.UTC)


def _apply_shadow_ban_if_needed(user_id, session):
    if session.execute(
        'SELECT apply_shadow_ban FROM "user" WHERE id = :uid',
        {'uid': user_id}
    ).scalar():
        session.execute('UPDATE "user" SET shadow_ban = TRUE WHERE id = :uid', {'uid': user_id})


def check_javascript_in_pdf(file):
    options = pdfid.get_fake_options()
    options.scan = True
    options.json = True

    result = pdfid.PDFiDMain([file.filename], options, [file.stream.read()])
    file.stream.seek(0)
    reports = result["reports"][0]
    if reports["/JavaScript"] != 0 or reports["/JS"] != 0 or reports["/OpenAction"] != 0:
        return True
    return False