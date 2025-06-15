from datetime import timezone, datetime, timedelta
from distutils.util import strtobool
from functools import wraps

import jwt
from flask import request, jsonify
from werkzeug.exceptions import BadRequest

from data_handler import dh
from system.settings import app
from utils.db_sessions import session_scope
from utils.utils import check_javascript_in_pdf


def get_user_id_from_tg(telegram_id, session=None):
    data = TELEGRAM_ID_ID_DICT.get(telegram_id)
    if data is None or data[1] + timedelta(minutes=1) < datetime.now(timezone.utc):
        user_id = dh.get_user_id(telegram_id, session)
        if user_id is not None:
            TELEGRAM_ID_ID_DICT[telegram_id] = (user_id, datetime.now(timezone.utc))
    else:
        user_id = data[0]

    return user_id


def requires_telegram_id(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        telegram_id = request.args.get('telegram_id')
        if telegram_id is None:
            return jsonify({'error': 'telegram_id is not specified'}), 400
        user_id = get_user_id_from_tg(telegram_id)
        if user_id is None:
            if not dh.is_user_exists(telegram_id):
                return jsonify({'error': 'User not exists'}), 400
        dh.update_last_action_time(user_id=user_id, telegram_id=telegram_id)
        return f(*args, telegram_id=telegram_id, **kwargs)

    return decorated


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Token', None)
        if not token:
            return jsonify({'error': 'Unauthorized'}), 403

        try:
            payload = jwt.decode(token, app.secret_key, algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 403
        except jwt.DecodeError:
            return jsonify({'error': 'Wrong token'}), 403
        symbol = payload['symbol']

        return f(*args, **kwargs, symbol=symbol)

    return decorated


TELEGRAM_ID_ID_DICT = {}


def get_user_id(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        telegram_id = kwargs.pop('telegram_id')
        user_id = get_user_id_from_tg(telegram_id, kwargs['session'])
        return f(*args, user_id=user_id, **kwargs)

    return decorated


def json_response(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        with session_scope() as session:
            return jsonify(f(*args, session=session, **kwargs))

    return decorated


def requires_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('token')
        if token is None:
            return jsonify({'error': 'token is not specified'}), 403
        if token != app.secret_key:
            return jsonify({'error': 'token invalid'}), 403
        return f(*args, **kwargs)

    return decorated


def only_admin(rights):
    def wrapper(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user_id = kwargs.pop('user_id')
            if not dh.is_user_have_rights(user_id, rights):
                return jsonify({'error': 'not permitted'}), 400
            return f(*args, **kwargs)
        return decorated
    return wrapper


@app.route('/settings', methods=['GET'])
@requires_auth
@json_response
def get_settings(symbol, session):
    return dh.get_settings(symbol, session)


@app.route('/currencies', methods=['GET'])
@requires_auth
@json_response
def get_currencies(symbol, session):
    return dh.get_currencies(session)


@app.route('/brokers', methods=['GET'])
@requires_auth
@json_response
def get_brokers(symbol, session):
    currency = request.args.get('currency')
    return dh.get_brokers(session, currency)


@app.route('/user', methods=['GET'])
@requires_auth
@requires_telegram_id
@json_response
@get_user_id
def get_user(symbol, user_id, session):
    return dh.get_user(user_id, session)


@app.route('/user-info/<string:nickname>', methods=['GET'])
@requires_auth
@json_response
def get_user_info(symbol, nickname, session):
    return dh.get_user_info(symbol, nickname, session)


@app.route('/user/<int:user_id>', methods=['GET'])
@requires_auth
@json_response
def get_user_by_id(symbol, user_id, session):
    return dh.get_user(user_id, session, expand_rating=True)


@app.route('/wallet/<int:user_id>', methods=['GET'])
@requires_auth
@json_response
def get_wallet(symbol, user_id, session):
    return dh.get_wallet(symbol, user_id, session)


@app.route('/deposit-rub', methods=['POST'])
@requires_auth
@json_response
def deposit_criptamat(symbol, session):
    user_id = request.json.get('user_id')
    return dh.deposit_criptamat(symbol, user_id, session)


@app.route('/address-validation/<string:address>', methods=['GET'])
@requires_auth
@json_response
def validate_address(symbol, address, session):
    return dh.is_address_valid(symbol, address)


@app.route('/bind-status/<int:user_id>', methods=['GET'])
@requires_auth
@json_response
def get_bind_status(symbol, user_id, session):
    return dh.get_bind_status(user_id, session)


@app.route('/transit/<int:user_id>', methods=['GET'])
@requires_auth
@json_response
def get_transit(symbol, user_id, session):
    return dh.get_transit(symbol, user_id, session)


@app.route('/promocode/<string:code>', methods=['GET'])
@requires_auth
@json_response
def get_promocode(symbol, code, session):
    return dh.get_promocode(symbol, code, session)


@app.route('/send-transaction', methods=['POST'])
@requires_auth
@json_response
def send_transaction(symbol, session):
    user_id = request.json.get('user_id')
    address = request.json.get('address')
    amount = request.json.get('amount')
    with_proxy = request.json.get('with_proxy', False)
    token = request.json.get('token')
    if None in (user_id, address, amount):
        raise BadRequest
    return dh.send_transaction_out(symbol, user_id, address, amount, with_proxy, token, session)


@app.route('/promocode-activation', methods=['POST'])
@requires_auth
@json_response
def activate_promocode(symbol, session):
    code = request.json.get('code')
    user_id = request.json.get('user_id')
    answ = dh.promocode_activation(symbol, user_id, code, session)
    if answ is None:
        raise BadRequest
    return answ


@app.route('/new-promocode', methods=['POST'])
@requires_auth
@json_response
def create_promocode(symbol, session):
    activations = request.json.get('activations')
    user_id = request.json.get('user_id')
    amount = request.json.get('amount')
    return dh.create_promocode(symbol, user_id, activations=activations, amount=amount, session=session)


@app.route('/promocode', methods=['DELETE'])
@requires_auth
@json_response
def delete_promocode(symbol, session):
    user_id = request.json.get('user_id')
    promocode_id = request.json.get('promocode_id')
    return dh.delete_promocode(symbol, user_id, promocode_id, session)


@app.route('/user-exists', methods=['GET'])
@requires_auth
@json_response
def user_exists_tg(symbol, session):
    telegram_id = request.args.get('telegram_id')
    return dh.get_user_existing(telegram_id, session)


@app.route('/commission', methods=['GET'])
@requires_auth
@json_response
def get_commission_withdraw(symbol, session):
    amount = float(request.args.get('amount'))
    return dh.get_commission(symbol, amount, session)


@app.route('/user-exists/<string:nickname>', methods=['GET'])
@requires_auth
@json_response
def user_exists(symbol, nickname, session):
    return dh.get_user_existing_by_nickname(symbol, nickname, session)


@app.route('/new-user', methods=['POST'])
@requires_auth
@json_response
def create_user(symbol, session):
    telegram_id = request.args.get('telegram_id')
    campaign = request.json.get('campaign')
    ref_code = request.json.get('ref_code')
    return dh.create_user(telegram_id, campaign=campaign, ref_code=ref_code, symbol=symbol, session=session)


@app.route('/user-stat/<int:user_id>', methods=['GET'])
@requires_auth
@json_response
def get_user_stat(symbol, user_id, session):
    return dh.get_user_stat(symbol, user_id, session)


@app.route('/active-deals/<int:user_id>', methods=['GET'])
@requires_auth
@json_response
def get_active_deals(symbol, user_id, session):
    return dh.get_active_deals(symbol, user_id, session)


@app.route('/active-deals-count/<int:user_id>', methods=['GET'])
@requires_auth
@json_response
def get_active_deals_count(symbol, user_id, session):
    return dh.get_active_deals_count(symbol, user_id, session)


@app.route('/lots/<string:t>', methods=['GET'])
@requires_auth
@json_response
def get_lots(symbol, t, session):
    user_id = request.args.get('user_id')

    if not hasattr(dh, t):
        raise BadRequest
    if not user_id:
        raise BadRequest

    meth = getattr(dh, t)
    return meth(symbol, user_id, session)


@app.route('/broker-lots/<string:t>', methods=['GET'])
@requires_auth
@json_response
def get_broker_lots(symbol, t, session):
    user_id = request.args.get('user_id')
    broker = request.args.get('broker')
    t = f'broker_lots_{t}'
    if not hasattr(dh, t) or not user_id:
        raise BadRequest
    meth = getattr(dh, t)
    return meth(symbol, user_id, broker, session)


@app.route('/user-lots/<int:user_id>', methods=['GET'])
@requires_auth
@json_response
def get_user_lots(symbol, user_id, session):
    return dh.get_user_lots(symbol, user_id, session)


@app.route('/affiliate/<int:user_id>', methods=['GET'])
@requires_auth
@json_response
def get_affiliate(symbol, user_id, session):
    return dh.get_affiliate(symbol, user_id, session)


@app.route('/active-promocodes-count/<int:user_id>', methods=['GET'])
@requires_auth
@json_response
def get_active_promocodes_count(symbol, user_id, session):
    return dh.get_active_promocodes_count(symbol, user_id, session)


@app.route('/active-promocodes/<int:user_id>', methods=['GET'])
@requires_auth
@json_response
def get_active_promocodes(symbol, user_id, session):
    return dh.get_active_promocodes(symbol, user_id, session)


@app.route('/promocode_activation', methods=['GET'])
@requires_auth
@json_response
def promocode_activation(symbol, session):
    user_id = request.json.get('user_id')
    code = request.json.get('code')
    if None in (user_id, code):
        raise BadRequest
    answ = dh.promocode_activation(symbol, user_id, code, session)
    if not answ:
        raise BadRequest
    return answ


@app.route('/rate', methods=['GET'])
@requires_auth
@json_response
def get_rate(symbol, session):
    currency = request.args.get('currency')
    return dh.get_rate(symbol, currency, session)


@app.route('/create-wallet-if-not-exists', methods=['POST'])
@requires_auth
@json_response
def create_wallet_if_not_exists(symbol, session):
    user_id = request.json.get('user_id')
    if user_id is None:
        raise BadRequest
    return dh.create_wallet_if_not_exists(symbol, user_id, session)


@app.route('/message', methods=['POST'])
@requires_auth
@requires_telegram_id
@json_response
@get_user_id
def new_message(symbol, user_id, session):
    text = request.json.get('text')
    message_id = request.json.get('message_id')
    is_bot = request.json.get('bot')
    if text is None or message_id is None or is_bot is None or user_id is None:
        raise BadRequest
    dh.add_message(user_id, symbol, text, message_id, is_bot)
    return {'success': 'message created'}


@app.route('/error', methods=['POST'])
@requires_auth
@json_response
def new_error(symbol, session):
    text = request.json.get('text')
    telegram_id = request.json.get('telegram_id')
    if text is None:
        raise BadRequest
    dh.add_error(telegram_id, symbol, text, session)
    return {'success': 'message created'}


@app.route('/user', methods=['PATCH'])
@requires_auth
@json_response
def update_user(symbol, session):
    currency = request.json.get('currency')
    is_deleted = request.json.get('is_deleted')
    user_id = request.json.get('user_id')

    allow_sell = request.json.get('allow_sell')
    allow_sale_v2 = request.json.get('allow_sale_v2')

    is_verify = request.json.get('is_verify')
    super_verify_only = request.json.get('super_verify_only')
    
    sky_pay = request.json.get('sky_pay')
    allow_payment_v2 = request.json.get('allow_payment_v2')

    is_baned = request.json.get('is_baned')
    shadow_ban = request.json.get('shadow_ban')
    apply_shadow_ban = request.json.get('apply_shadow_ban')
    lang = request.json.get('lang')
    if user_id is None:
        raise BadRequest
    if currency:
        dh.update_currency(user_id, currency, session)
    if is_deleted is not None:
        dh.update_delete_status(symbol, user_id, is_deleted, session)
    if is_verify is not None:
        dh.update_verify_status(symbol, user_id, is_verify, session)
    if super_verify_only is not None:
        dh.update_super_verify_only_status(symbol, user_id, super_verify_only, session)
    if sky_pay is not None:
        dh.update_sky_pay_status(symbol, user_id, sky_pay, session)
    if allow_payment_v2 is not None:
        dh.update_allow_payment_v2_status(symbol, user_id, allow_payment_v2, session)
    if allow_sell is not None:
        dh.update_allow_sell_status(symbol, user_id, allow_sell, session)
    if allow_sale_v2 is not None:
        dh.update_allow_sale_v2_status(symbol, user_id, allow_sale_v2, session)
    if is_baned is not None:
        dh.update_ban_status(symbol, user_id, is_baned, session)
    if shadow_ban is not None:
        dh.update_shadow_ban_status(symbol, user_id, shadow_ban, session)
    if apply_shadow_ban is not None:
        dh.update_apply_shadow_ban_status(symbol, user_id, apply_shadow_ban, session)
    if lang is not None:
        dh.update_lang(user_id, lang, session)

    return {'success': 'currency updated'}


@app.route('/trading-status', methods=['PATCH'])
@requires_auth
@json_response
def change_trading_status(symbol, session):
    user_id = request.json.get('user_id')
    if user_id is None:
        raise BadRequest
    return dh.change_trading_status(symbol, user_id, session)


@app.route('/usermessages-ban-status/<int:target_user_id>', methods=['GET'])
@requires_auth
@json_response
def get_usermessages_ban_status(symbol, target_user_id, session):
    user_id = request.args.get('user_id')
    return dh.get_usermessages_ban_status(user_id=user_id, target_user_id=target_user_id, session=session)


@app.route('/usermessages-ban-status', methods=['PATCH'])
@requires_auth
@json_response
def update_usermessages_ban_status(symbol, session):
    user_id = request.json.get('user_id')
    target_user_id = request.json.get('target_user_id')
    status = request.json.get('status')
    return dh.set_usermessages_ban_status(user_id=user_id, target_user_id=target_user_id, status=status, session=session)


@app.route('/new-usermessage', methods=['POST'])
@requires_auth
@json_response
def create_new_usermessage(symbol, session):
    sender_id = request.json.get('sender_id')
    receiver_id = request.json.get('receiver_id')
    message = request.json.get('message')
    media_id = request.json.get('media_id')
    if None in (sender_id, receiver_id, message):
        raise BadRequest
    return dh.create_new_usermessage(symbol, sender_id=sender_id, receiver_id=receiver_id,
                                     message=message, media_id=media_id, session=session)


@app.route('/new-lot', methods=['POST'])
@requires_auth
@json_response
def create_new_lot(symbol, session):
    user_id = request.json.get('user_id')
    coefficient = request.json.get('coefficient')
    rate = request.json.get('rate')
    limit_from = request.json.get('limit_from')
    limit_to = request.json.get('limit_to')
    _type = request.json.get('type')
    broker = request.json.get('broker')
    if None in (user_id, rate, limit_from, limit_to, _type, broker):
        raise BadRequest
    answ = dh.create_new_lot(symbol, user_id=user_id, coefficient=coefficient, rate=rate,
                             limit_from=limit_from, limit_to=limit_to, _type=_type, broker=broker, session=session)
    if answ:
        return answ
    else:
        raise BadRequest


@app.route('/lot/<string:identificator>', methods=['GET'])
@requires_auth
@json_response
def get_lot(symbol, identificator, session):
    return dh.get_lot(identificator, session)


@app.route('/lot', methods=['PATCH'])
@requires_auth
@json_response
def update_lot(symbol, session):
    user_id = request.json.get('user_id')
    identificator = request.json.get('identificator')
    limit_from = request.json.get('limit_from')
    limit_to = request.json.get('limit_to')
    rate = request.json.get('rate')
    coefficient = request.json.get('coefficient')
    details = request.json.get('details')
    activity_status = request.json.get('activity_status')

    return dh.update_lot(user_id, symbol, identificator, limit_from=limit_from, limit_to=limit_to, rate=rate,
                         details=details, activity_status=activity_status, coefficient=coefficient, session=session)


@app.route('/lot', methods=['DELETE'])
@requires_auth
@json_response
def delete_lot(symbol, session):
    user_id = request.json.get('user_id')
    identificator = request.json.get('identificator')

    answ = dh.delete_lot(user_id, symbol, identificator, session)
    if answ is None:
        raise BadRequest
    return answ


@app.route('/last-requisites/<uuid:broker_id>', methods=['GET'])
@requires_auth
@json_response
def get_last_requisites(symbol, broker_id, session):
    user_id = request.args.get('user_id')
    currency = request.args.get('currency')
    if user_id is None or currency is None:
        raise BadRequest
    return dh.get_last_requisites(symbol, user_id, broker_id, currency, session)


@app.route('/new-deal', methods=['POST'])
@requires_auth
@json_response
def create_new_deal(symbol, session):
    user_id = request.json.get('user_id')
    lot_id = request.json.get('lot_id')
    rate = request.json.get('rate')
    requisite = request.json.get('requisite', '')
    amount_currency = request.json.get('amount_currency')
    amount = request.json.get('amount')
    if None in (user_id, rate, lot_id, amount, amount_currency):
        raise BadRequest
    return dh.create_new_deal(symbol, user_id=user_id, lot_id=lot_id, rate=rate,
                              requisite=requisite, amount_currency=amount_currency, amount=amount, session=session)


@app.route('/stop-deal', methods=['POST'])
@requires_auth
@json_response
def stop_deal(symbol, session):
    deal_id = request.json.get('deal_id')
    if deal_id is None:
        raise BadRequest
    dh.stop_deal(symbol, deal_id=deal_id, session=session)
    return {'success': 'deal deleted'}


@app.route('/cancel-deal', methods=['POST'])
@requires_auth
@json_response
def cancel_deal(symbol, session):
    deal_id = request.json.get('deal_id')
    user_id = request.json.get('user_id')
    if deal_id is None and user_id is None:
        raise BadRequest
    return dh.cancel_deal(symbol, deal_id=deal_id, user_id=user_id, session=session)


@app.route('/deal-state', methods=['PATCH'])
@requires_auth
@json_response
def update_deal_state(symbol, session):
    deal_id = request.json.get('deal_id')
    user_id = request.json.get('user_id')
    if deal_id is None or user_id is None:
        raise BadRequest
    return dh.update_deal_state(symbol, deal_id=deal_id, user_id=user_id, session=session)


@app.route('/fd-deal-confirm', methods=['POST'])
@requires_auth
@json_response
def confirm_declined_fd_deal(symbol, session):
    deal_id = request.json.get('deal_id')
    user_id = request.json.get('user_id')
    if deal_id is None or user_id is None:
        raise BadRequest
    return dh.confirm_declined_fd_deal(symbol, deal_id=deal_id, user_id=user_id, session=session)


@app.route('/deal-confirmation-no-agreement', methods=['POST'])
@requires_auth
@json_response
def approve_deal_without_agreement(symbol, session):
    deal_id = request.json.get('deal_id')
    user_id = request.json.get('user_id')
    if deal_id is None or user_id is None:
        raise BadRequest
    return dh.confirm_deal_without_agreement(symbol, deal_id=deal_id, user_id=user_id, session=session)


@app.route('/deal-requisite', methods=['PATCH'])
@requires_auth
@json_response
def update_deal_req(symbol, session):
    deal_id = request.json.get('deal_id')
    user_id = request.json.get('user_id')
    req = request.json.get('requisite')
    if None in (deal_id, user_id, req):
        raise BadRequest
    dh.update_deal_req(symbol, deal_id=deal_id, user_id=user_id, req=req, session=session)
    return {'success': 'deal updated'}


@app.route('/user-rate', methods=['PATCH'])
@requires_auth
@json_response
def update_user_rate(symbol, session):
    from_user = request.json.get('from')
    to_user = request.json.get('to')
    method = request.json.get('method')
    deal_id = request.json.get('deal_id')
    if None in (from_user, to_user, method, deal_id) or method not in ('like', 'dislike'):
        raise BadRequest
    dh.update_user_rate(from_user=from_user, to_user=to_user, method=method, deal_id=deal_id, session=session)
    return {'success': 'user rate updated'}


@app.route('/deal/<string:deal_id>', methods=['GET'])
@requires_auth
@json_response
def get_deal(symbol, deal_id, session):
    expand_email = bool(strtobool(request.args.get('expand_email', '0')))
    with_merchant = bool(strtobool(request.args.get('with_merchant', '0')))
    return dh.get_deal(symbol, deal_id, session=session, expand_email=expand_email, with_merchant=with_merchant)


@app.route('/deal/<string:deal_id>/mask', methods=['GET'])
@requires_auth
@json_response
def get_deal_mask(symbol, deal_id, session):
    return dh.get_deal_mask(symbol, deal_id, session=session)


@app.route('/deal/<string:deal_id>/mask', methods=['POST'])
@requires_auth
@json_response
def set_deal_mask(symbol, deal_id, session):
    mask = request.json.get('mask')
    return dh.set_deal_mask(symbol, deal_id, mask=mask, session=session)


@app.route('/dispute/<string:deal_id>', methods=['GET'])
@requires_auth
@json_response
def get_dispute(symbol, deal_id, session):
    return dh.get_dispute(deal_id, is_internal_id=False, session=session)


@app.route('/new-dispute', methods=['POST'])
@requires_auth
@json_response
def create_dispute(symbol, session):
    deal_id = request.json.get('deal_id')
    user_id = request.json.get('user_id')
    return dh.create_dispute(deal_id, user_id, session)


@app.route('/updates', methods=['GET'])
@requires_auth
@json_response
def get_updates(symbol, session):
    return dh.get_updates(symbol, session)


@app.route('/control-updates', methods=['GET'])
@requires_auth
@json_response
def get_control_updates(symbol, session):
    return dh.get_control_updates(symbol, session)


@app.route('/reports-all/<string:t>', methods=['GET'])
@requires_auth
@json_response
def get_all_reports(symbol, t, session):
    from_date = request.args.get('from')
    to_date = request.args.get('to')
    if from_date:
        from_date = int(float(from_date))
    if to_date:
        to_date = int(float(to_date))
    return dh.get_all_reports(symbol, t, from_date=from_date, to_date=to_date, session=session)


@app.route('/reports/<int:user_id>', methods=['GET'])
@requires_auth
@json_response
def get_reports(symbol, user_id, session):
    return dh.get_reports(symbol, user_id, session)


@app.route('/all_telegram_ids', methods=['GET'])
@requires_auth
@json_response
def get_all_telegram_ids(symbol, session):
    return dh.get_all_telegram_ids(session)


@app.route('/payment-info/<uuid:payment_id>', methods=['GET'])
@requires_auth
@json_response
def get_payment_info(symbol, payment_id, session):
    return dh.get_payment_info(payment_id, session)


@app.route('/payment-v2-info/<uuid:payment_id>', methods=['GET'])
@requires_auth
@json_response
def get_payment_v2_info(symbol, payment_id, session):
    return dh.get_payment_v2_info(payment_id, session)


@app.route('/sale-info/<uuid:sale_id>', methods=['GET'])
@requires_auth
@json_response
def get_sale_info(symbol, sale_id, session):
    return dh.get_sale_info(sale_id, session)


@app.route('/sale_v2-info/<uuid:sale_v2_id>', methods=['GET'])
@requires_auth
@json_response
def get_sale_v2_info(symbol, sale_v2_id, session):
    return dh.get_sale_v2_info(sale_v2_id, session)


@app.route('/cpayment-info/<uuid:cpayment_id>', methods=['GET'])
@requires_auth
@json_response
def get_cpayment_info(symbol, cpayment_id, session):
    return dh.get_cpayment_info(cpayment_id, session)


@app.route('/withdrawal-info/<uuid:withdrawal_id>', methods=['GET'])
@requires_auth
@json_response
def get_withdrawal_info(symbol, withdrawal_id, session):
    return dh.get_withdrawal_info(withdrawal_id, session)


@app.route('/node-transaction/<string:tx_hash>', methods=['GET'])
@requires_auth
@json_response
def get_node_transaction(symbol, tx_hash, session):
    return dh.get_node_transaction(symbol, tx_hash)


@app.route('/reset-imbalance', methods=['POST'])
@requires_auth
@json_response
def reset_imbalance(symbol, session):
    admin_id = request.json.get('admin_id')
    return dh.reset_imbalance(symbol=symbol, admin_id=admin_id, session=session)


@app.route('/balance', methods=['PATCH'])
@requires_auth
@json_response
def change_balance(symbol, session):
    to_user_id = request.json.get('to_user_id')
    admin_id = request.json.get('admin_id')
    amount = request.json.get('amount')
    with_operation = request.json.get('with_operation')
    return dh.add_balance(symbol, to_user_id, admin_id, amount, with_operation, session)


@app.route('/frozen', methods=['PATCH'])
@requires_auth
@json_response
def change_frozen(symbol, session):
    to_user_id = request.json.get('to_user_id')
    admin_id = request.json.get('admin_id')
    amount = request.json.get('amount')
    return dh.add_frozen(symbol, to_user_id, admin_id, amount, session)


@app.route('/balance-fixed', methods=['PATCH'])
@requires_auth
@json_response
def set_balance(symbol, session):
    to_user_id = request.json.get('to_user_id')
    admin_id = request.json.get('admin_id')
    amount = request.json.get('amount')
    return dh.set_balance(symbol, to_user_id, admin_id, amount, session)


@app.route('/frozen-fixed', methods=['PATCH'])
@requires_auth
@json_response
def set_frozen(symbol, session):
    to_user_id = request.json.get('to_user_id')
    admin_id = request.json.get('admin_id')
    amount = request.json.get('amount')
    return dh.set_frozen(symbol, to_user_id, admin_id, amount, session)


@app.route('/campaigns', methods=['POST'])
@requires_auth
@json_response
def new_campaign(symbol, session):
    if not dh.is_user_have_rights(request.json.get('admin_id'), 'low', session):
        raise BadRequest
    name = request.json.get('name')
    return dh.create_new_campaign(name, session)


@app.route('/withdraw-from-payments-node', methods=['POST'])
@requires_auth
@json_response
def withdraw_from_payments_node(symbol, session):
    if not dh.is_user_have_rights(request.json.get('admin_id'), 'high', session):
        raise BadRequest
    if symbol != 'btc':
        raise BadRequest
    address = request.json.get('address')
    amount = request.json.get('amount')
    return dh.withdraw_from_payments_node(symbol, address, amount)


@app.route('/profit', methods=['GET'])
@requires_auth
@json_response
def get_profit(symbol, session):
    return dh.get_profit(symbol, session)


@app.route('/finreport', methods=['GET'])
@requires_auth
@json_response
def get_finreport(symbol, session):
    return dh.get_finreport(symbol, session)


@app.route('/change-withdraw-status', methods=['POST'])
@requires_auth
@json_response
def change_withdraw_status(symbol, session):
    return dh.change_withdraw_status(symbol)


@app.route('/change-fast-deal-status', methods=['POST'])
@requires_auth
@json_response
def change_fast_deal_status(symbol, session):
    return dh.change_fast_deal_status(session)


@app.route('/close-deal-admin', methods=['POST'])
@requires_auth
@json_response
def close_deal_admin(symbol, session):
    deal_id = request.json.get('deal_id')
    winner = request.json.get('winner')
    return dh.close_deal_admin(symbol, deal_id, winner, session)


@app.route('/frozen-all', methods=['GET'])
@requires_auth
@json_response
def get_frozen_all(symbol, session):
    return dh.get_frozen_all(symbol, session)


@app.route('/user/<int:user_id>/media', methods=['POST'])
@requires_auth
@json_response
def upload_media(symbol, user_id, session):
    file = request.files['file']
    content_type = request.args.get('content_type')

    extension = file.filename.split(".")[-1]
    if extension == "pdf" and check_javascript_in_pdf(file):
        raise BadRequest("JavaScript in pdf")
    return dh.upload_media(symbol, user_id, file, session, content_type)


@app.route('/healthcheck', methods=['GET'])
@json_response
def healthcheck(session):
    return {}
