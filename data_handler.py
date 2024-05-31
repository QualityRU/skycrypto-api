import re
import math
from datetime import datetime, timedelta
from datetime import timezone
from decimal import Decimal
from distutils.util import strtobool
from os import environ

import pytz
import requests
from werkzeug.exceptions import BadRequest, Forbidden, Conflict

from crypto.manager import manager
from crypto.trx import TRX
from system.constants import (
    ONLINE_MINUTES, PROFITS_CHAT, MESSAGES_CHAT, RATING_SMILES, MINUS_RATING_SMILE, CONTROL_CHATS,
    LOT_TYPE_BUY, LOT_TYPE_SELL, STATES, DISPUTE_TIME, MIN_PROMOCODE_AMOUNT,
    EARNINGS_CHAT, DealTypes, Action, OperationTypes, DEAL_CONTROL_CHAT, WITHDRAWAL_DEFAULT_LIMITS)
from system.funds_changer import change_frozen, change_balance, freeze, unfreeze
from system.settings import TEST
from utils.binance_client import binance_client
from utils.db_sessions import session_scope
from utils.emails import receipt
from utils.logger import logger
from utils.notifications_queue import create_deal_notification, create_closed_dispute_notification, \
    create_message_notification
from utils.s3 import upload_file_to_s3, insert_dynamo
from utils.utils import (
    generate_nickname, generate_promocode, generate_lot_id,
    generate_deal_id, generate_ref_code, generate_campaign_id,
    create_operation, get_purchase, complete_purchase, complete_payment_v2, complete_sell, get_sell,
    create_deal_commission,
    update_deal_commission, date_iter, find_object_by_datetime, update_sale_v2, complete_sale_v2,
    get_merchant_commission, get_merchant, get_sale_v2, get_cpayment, get_withdrawal, localize_datetime,
    update_purchase, update_payment_v2, get_payment_v2
)
from utils.validators import is_amount_precision_right_for_symbol

LAST_USER_ACTION_TIME = {}


class DataHandler:
    def __init__(self):
        self.crypto_manager = manager

    def _validate_currency(self, currency, session):
        currencies = [item['id'] for item in self.get_currencies(session)]
        if currency not in currencies:
            raise BadRequest('Bad currency')

    def get_rate(self, symbol, currency, session):
        self._validate_currency(currency, session)
        q = """
            SELECT rate
            FROM rates
            WHERE symbol = :sym AND currency = :cur
            LIMIT 1
        """
        return session.execute(q, {'sym': symbol, 'cur': currency}).scalar()

    def is_user_exists(self, telegram_id, session=None):
        if session:
            return session.execute(f'SELECT EXISTS(SELECT 1 from "user" where telegram_id = {telegram_id})').scalar()
        else:
            with session_scope() as session:
                return session.execute(
                    f'SELECT EXISTS(SELECT 1 from "user" where telegram_id = {telegram_id})'
                ).scalar()

    def is_wallet_exists(self, symbol, user_id, session):
        q = f"SELECT EXISTS(SELECT 1 from wallet where user_id = {user_id} AND symbol = '{symbol}')"
        return session.execute(q).scalar()

    def get_message_for_update(self, message_id, session):
        q = f"""
            SELECT sender.id, message, receiver.id, media_id
            FROM usermessage um
            LEFT JOIN "user" sender ON um.sender_id = sender.id
            LEFT JOIN "user" receiver ON um.receiver_id = receiver.id
            WHERE um.id = {message_id}
        """
        sender_id, message, receiver_id, media_id = session.execute(q).fetchone()
        if media_id:
            url = session.execute("SELECT url FROM media WHERE id = :mid", {'mid': media_id}).scalar()
        else:
            url = None
        return {'sender_id': sender_id, 'message': message, 'receiver_id': receiver_id, 'media_url': url}

    def get_new_referral_for_update(self, user_id, session):
        q = """
            SELECT nickname
            FROM "user" u
            JOIN wallet w on u.id = w.user_id
            WHERE referred_from_id = :uid
            ORDER BY u.id DESC
            LIMIT 1
        """
        ref = session.execute(q, {'uid': user_id}).fetchone()[0]
        return {'user_id': user_id, 'referral': ref}

    def get_promocode_for_update(self, user_id, promocodeactivation_id, symbol, session):
        q = """
            SELECT amount, (SELECT nickname FROM "user" WHERE id = w.user_id), code
            FROM promocodeactivations pa
            JOIN promocodes p ON pa.promocode_id = p.id
            JOIN wallet w ON w.id = pa.wallet_id 
            WHERE pa.id = :paid
        """
        amount, activator, code = session.execute(q, {'paid': promocodeactivation_id}).fetchone()
        res = {'user_id': user_id, 'amount': manager.from_subunit(symbol, amount), 'activator': activator, 'code': code}
        return res

    def get_transaction_for_update(self, transaction_id, session):
        q = f"""
            SELECT user_id, type, amount_units, tx_hash, symbol
            FROM transactions t
            LEFT JOIN wallet w ON t.wallet_id = w.id
            WHERE t.id = {transaction_id}
        """
        user_id, t, amount_units, tx_hash, symbol = session.execute(q).fetchone()
        res = {'user_id': user_id, 'amount': amount_units, 'type': t}
        if t == 'out':
            res['link'] = self.crypto_manager.get_link(symbol, tx_hash)
        return res

    def get_deal_timeout_for_update(self, deal_id, session, user_id):
        q = f"""
            SELECT identificator
            FROM deal d
            WHERE d.id = {deal_id}
        """
        identificator = session.execute(q).fetchone()[0]
        res = {'deal_id': identificator, 'user_id': user_id}
        return res

    def get_deal_referral_for_update(self, deal_id, session, user_id, symbol):
        q = f"""
            SELECT identificator, referral_commission_buyer_subunits, buyer_id
            FROM deal d
            WHERE d.id = :did
            LIMIT 1
        """
        identificator, ref_comm, referral_id = session.execute(q, {'did': deal_id}).fetchone()
        res = {
            'identificator': identificator,
            'user_id': user_id,
            'referral_id': referral_id,
            'amount': self.crypto_manager.from_subunit(symbol, ref_comm)
        }
        return res

    def get_deal_for_update(self, deal_id, session, user_id):
        q = f"""
            SELECT seller_id, buyer_id, identificator
            FROM deal
            WHERE id = :did
            LIMIT 1
        """
        seller_id, buyer_id, identificator = session.execute(q, {'did': deal_id}).fetchone()
        res = {
            'user_id': user_id,
            'opponent': seller_id if seller_id != user_id else buyer_id,
            'deal_id': identificator
        }
        return res

    def get_dispute_for_update(self, deal_id, session, user_id, admin=False):
        q = f"""
            SELECT identificator
            FROM deal
            WHERE id = :did
            LIMIT 1
        """
        identificator = session.execute(q, {'did': deal_id}).scalar()
        res = {
            'user_id': user_id,
            'deal_id': identificator,
            'dispute_time': DISPUTE_TIME,
            'admin': admin
        }
        return res

    def get_closed_dispute_for_update(self, deal_id, session, user_id, admin=False):
        q = f"""
            SELECT deal.identificator, (SELECT type FROM lot WHERE id = lot_id), deal.state
            FROM deal
            WHERE deal.id = :did
            LIMIT 1
        """
        identificator, lot_type, state = session.execute(q, {'did': deal_id}).fetchone()
        if state == STATES[-1]:
            winner = 'seller'
        else:
            winner = 'buyer'

        res = {
            'user_id': user_id,
            'winner': winner,
            'deal_id': identificator,
            'admin': admin
        }
        return res

    def get_accounts_join_for_update(self, accounts_join_id, session):
        token, web, tg = session.execute(
            """
                SELECT token, account_web, account_tg
                FROM accounts_join
                WHERE id = :id
            """, {'id': accounts_join_id}
        ).fetchone()
        res = {
            'tg_account': tg,
            'web_account': web,
            'token': token
        }
        return res

    def _get_control_messages(self, symbol, session):
        q = """
            SELECT it.id, nickname, message, it.created_at, balance, frozen, instance, change_balance, change_frozen
            FROM insidetransaction it
            JOIN "user" ON it.user_id = "user".id
            WHERE it.created_at > now() - interval '1 day' AND NOT controled AND symbol = :sym
            ORDER BY id
        """
        res = session.execute(q, {'sym': symbol})
        answ = []
        ids_controled = []
        for itid, nick, message, created_at, balance, frozen, instance, changed_balance, changed_frozen in res.fetchall():
            ids_controled.append(itid)
            d = {
                'user': nick,
                'change_balance': changed_balance,
                'change_frozen': changed_frozen,
                'balance': balance,
                'frozen': frozen,
                'message': message,
                'symbol': symbol,
                'instance': instance,
                'created_at': str(created_at)
            }
            answ.append(d)
        if ids_controled:
            session.execute("UPDATE insidetransaction SET controled = TRUE WHERE id IN :ids", {'ids': tuple(ids_controled)})
        return answ

    def _get_earnings(self, symbol, session):
        res = session.execute(
            "SELECT id, income FROM earnings WHERE created_at > now() - interval '6 hours' AND symbol = :sym AND NOT controlled",
            {'sym': symbol}
        ).fetchone()
        if res is None:
            return []
        eid, income = res
        session.execute('UPDATE earnings SET controlled = TRUE WHERE id = :eid', {'eid': eid})
        return [{'income': income}]

    def _get_secondary_node_updates(self, session):
        res = session.execute(
            'SELECT id, tx_hash, amount FROM secondarydeposits WHERE NOT controlled',
        ).fetchone()
        if res is None:
            return []
        eid, tx_hash, amount = res
        session.execute('UPDATE secondarydeposits SET controlled = TRUE WHERE id = :eid', {'eid': eid})
        return [{'amount': amount, 'link': manager.currencies['btc'].get_link(tx_hash)}]

    # def _get_auto_wthd_updates(self, session):
    #     res = session.execute(
    #         'SELECT id, tx_hash, amount, symbol FROM wthd WHERE NOT controlled',
    #     ).fetchone()
    #     if res is None:
    #         return []
    #     eid, tx_hash, amount, symbol = res
    #     session.execute('UPDATE wthd SET controlled = TRUE WHERE id = :eid', {'eid': eid})
    #     return [{'amount': amount, 'link': manager.currencies[symbol].get_link(tx_hash), 'symbol': symbol}]

    def _get_control_usermessages(self, symbol, session):
        if symbol == 'btc':
            messages_symbols = ['btc', 'web']
        else:
            messages_symbols = [symbol]

        q = """
            SELECT id, message, (SELECT nickname FROM "user" WHERE id = sender_id), 
                (SELECT nickname FROM "user" WHERE id = receiver_id), media_id
            FROM usermessage 
            WHERE created_at > now() - interval '2 hours' AND NOT controled AND symbol = :sym
            ORDER BY id
        """

        answ = []
        ids_controled = []

        for sym in messages_symbols:
            res = session.execute(q, {'sym': sym})
            for umid, message, sender, receiver, media_id in res.fetchall():
                ids_controled.append(umid)
                if media_id:
                    url = session.execute('SELECT url FROM media WHERE id = :mid', {'mid': media_id}).fetchone()[0]
                else:
                    url = None
                d = {
                    'sender': sender,
                    'receiver': receiver,
                    'url':  url,
                    'message': message
                }
                answ.append(d)

        if ids_controled:
            session.execute(
                "UPDATE usermessage SET controled = TRUE WHERE id IN :ids", {'ids': tuple(ids_controled)}
            )

        return answ

    def get_updates(self, symbol, session):
        q = f"""
            SELECT user_id, n.id, type, deal_id, transaction_id, message_id, join_id, promocodeactivation_id
            FROM notification n
            WHERE NOT telegram_notified AND symbol = '{symbol}'
        """
        res = {
            'messages': [],
            'transactions': [],
            'accounts_join': [],
            'new-referral': [],
            'promocodes': [],
            'deals': {
                'timeouts': [],
                'referrals': [],
                'deals': [],
                'disputes': [],
                'closed_disputes': [],
                'dispute_notifications': [],
                'cancel': []
            },
            'secondary_node': []
        }
        updates = session.execute(q).fetchall()
        for user_id, notification_id, t, deal_id, transaction_id, message_id, accounts_join_id, promocodeactivation_id in updates:
            if t == 'message':
                res['messages'].append(self.get_message_for_update(message_id, session))
            elif t == 'new-referral':
                res['new-referral'].append(self.get_new_referral_for_update(user_id, session))
            elif t == 'promocode':
                res['promocodes'].append(self.get_promocode_for_update(user_id, promocodeactivation_id, symbol, session))
            elif t == 'transaction':
                res['transactions'].append(self.get_transaction_for_update(transaction_id, session))
            elif t == 'deal':
                res['deals']['deals'].append(self.get_deal_for_update(deal_id, session, user_id))
            elif t == 'dispute':
                res['deals']['disputes'].append(self.get_dispute_for_update(deal_id, session, user_id))
            elif t == 'closed_dispute':
                res['deals']['closed_disputes'].append(self.get_closed_dispute_for_update(deal_id, session, user_id))
            elif t == 'closed_dispute_admin':
                res['deals']['closed_disputes'].append(self.get_closed_dispute_for_update(deal_id, session, user_id, admin=True))
            elif t == 'dispute_notification':
                res['deals']['dispute_notifications'].append(self.get_dispute_for_update(deal_id, session, user_id))
            elif t == 'income_referral':
                res['deals']['referrals'].append(self.get_deal_referral_for_update(deal_id, session, user_id, symbol))
            elif t == 'timeout':
                res['deals']['timeouts'].append(self.get_deal_timeout_for_update(deal_id, session, user_id))
            elif t == 'cancel_deal':
                res['deals']['cancel'].append(self.get_deal_timeout_for_update(deal_id, session, user_id))
            elif t == 'accounts_join':
                res['accounts_join'].append(self.get_accounts_join_for_update(accounts_join_id, session))
            else:
                raise ValueError('Wrong type')
            session.execute(f'UPDATE notification SET telegram_notified = TRUE WHERE id = {notification_id}')
        res['earnings'] = self._get_earnings(symbol, session)
        res['secondary_node'] = self._get_secondary_node_updates(session)
        # res['autowithdrawal'] = self._get_auto_wthd_updates(session)
        res['usermessages'] = self._get_control_usermessages(symbol, session)
        return res

    def get_control_updates(self, symbol, session):
        return self._get_control_messages(symbol, session)

    def get_all_telegram_ids(self, session):
        q = """
            SELECT telegram_id
            from "user"
            WHERE telegram_id IS NOT NULL
            ORDER BY last_action DESC
        """
        res = session.execute(q)
        return [item[0] for item in res]

    def reset_imbalance(self, symbol, admin_id, session):
        if not self.is_user_have_rights(admin_id, 'high', session):
            raise Forbidden('Admins only')
        session.execute(
            """
                UPDATE exchanges
                SET processed_at = NOW()
                WHERE processed_at is null and (from_symbol = :sym or to_symbol = :sym) 
            """, {'sym': symbol}
        )
        return {'success': 'reset imbalance success'}

    def add_balance(self, symbol, to_user_id, admin_id, amount, with_operation, session):
        if not self.is_user_have_rights(admin_id, 'high', session):
            raise Forbidden('Admins only')
        change_balance(user_id=to_user_id, msg='Change balance from admin',
                       amount=amount, symbol=symbol, session=session)
        if with_operation:
            create_operation(session, to_user_id, 'admin', symbol, None, amount, Action.transaction)
        return {'success': 'frozen changed'}

    def add_frozen(self, symbol, to_user_id, admin_id, amount, session):
        if not self.is_user_have_rights(admin_id, 'low', session):
            raise Forbidden('Admins only')
        change_frozen(user_id=to_user_id, msg='Change frozen from admin',
                      amount=amount, symbol=symbol, session=session)
        return {'success': 'frozen changed'}

    def set_balance(self, symbol, to_user_id, admin_id, amount, session):
        if not self.is_user_have_rights(admin_id, 'high', session):
            raise Forbidden('Admins only')
        amount = manager.to_subunit(symbol, amount)
        session.execute(
            'UPDATE wallet SET balance = :value WHERE user_id = :uid AND symbol = :symbol',
            {'value': amount, 'uid': to_user_id, 'symbol': symbol}
        )
        return {'success': 'balance updated'}

    def set_frozen(self, symbol, to_user_id, admin_id, amount, session):
        if not self.is_user_have_rights(admin_id, 'low', session):
            raise Forbidden('Admins only')
        amount = manager.to_subunit(symbol, amount)
        session.execute(
            'UPDATE wallet SET frozen = :value WHERE user_id = :uid AND symbol = :symbol',
            {'value': amount, 'uid': to_user_id, 'symbol': symbol}
        )
        return {'success': 'frozen updated'}

    def _get_active_deposit_addresses(self, session):
        return [
                res[0] for res in session.execute(
                    """
                        SELECT private_key
                        FROM wallet
                        JOIN "user" u on wallet.user_id = u.id
                        WHERE symbol = 'btc' AND last_action > NOW() - INTERVAL '1 day'
                    """).fetchall()
            ]

    def _get_last_withdrawals_addresses(self, session):
        return [
                res[0] for res in session.execute(
                    """
                        SELECT to_address
                        FROM transactions t
                        JOIN wallet w ON t.wallet_id = w.id
                        WHERE symbol = 'btc' AND created_at > NOW() - INTERVAL '1 day' AND type = 'out'
                    """).fetchall()
            ]

    def _get_deposit_sum(self, transactions, addresses):
        return sum(
                [
                    t['amount'] for t in transactions
                    if t['confirmations'] == 0 and t['category'] == 'receive' and t['address'] in addresses
                ]
            )

    def _get_withdrawal_sum(self, transactions, addresses):
        return sum(
                [
                    abs(t['amount']) for t in transactions
                    if t['confirmations'] == 0 and t['category'] == 'send' and t['address'] in addresses
                ]
            )

    def _get_returns_sum(self, transactions, dep_addresses, with_addresses):
        return sum(
                [
                    t['amount'] for t in transactions
                    if (
                        t['confirmations'] == 0 and
                        t['category'] == 'receive' and
                        t['address'] not in dep_addresses + with_addresses
                    )
                ]
            )

    def _get_wallet_funds(self, symbol, session):
        if symbol == 'btc':
            dep_addresses = self._get_active_deposit_addresses(session)
            with_addresses = self._get_last_withdrawals_addresses(session)
            transactions = manager.currencies['btc'].get_all_transactions()
            sum_deposit = self._get_deposit_sum(transactions, dep_addresses)
            sum_withdraw = self._get_withdrawal_sum(transactions, with_addresses)
            confirmed_balance = manager.currencies['btc'].get_node_balance(1)
            unconfirmed_balance = manager.currencies['btc'].get_node_balance(0)
            resp = {
                'confirmed': confirmed_balance,
                'unconfirmed': unconfirmed_balance,
                'funds': unconfirmed_balance,
                'deposits': sum_deposit,
                'withdraws': sum_withdraw
            }
        else:
            resp = manager.from_subunit(symbol, manager.get_balance(symbol, None))

        return resp

    def _get_imbalance(self, symbol, session):
        imbalance_from = session.execute(
            'SELECT coalesce(sum(amount_sent), 0) FROM exchanges WHERE processed_at is NULL and from_symbol = :sym',
            {'sym': symbol}
        ).scalar()
        imbalance_to, commission = session.execute(
            'SELECT coalesce(sum(amount_received), 0), coalesce(sum(commission), 0) FROM exchanges WHERE processed_at is NULL and to_symbol = :sym',
            {'sym': symbol}
        ).fetchone()

        return imbalance_from - imbalance_to - commission

    def get_profit(self, symbol, session):
        imbalance = self._get_imbalance(symbol, session)
        answ = {
            'users': session.execute('SELECT COUNT(*) FROM "user"').scalar(),
            'wallet_funds': self._get_wallet_funds(symbol, session),
            'db_funds': manager.from_subunit(
                symbol,
                session.execute(
                    'SELECT SUM(balance) + SUM(frozen) FROM wallet WHERE symbol = :sym', {'sym': symbol}
                ).scalar()
            ),
            'profit': 0,
            'imbalance': imbalance,
            'binance': Decimal(binance_client.get_balance(symbol))
        }
        if symbol == 'btc':
            btc_module = manager.currencies['btc']
            answ['wallet_funds']['secondary'] = btc_module.get_secondary_balance() + btc_module.get_secondary_deposits()
            answ['wallet_funds']['cpayments'] = btc_module.get_cpayment_node_balance() + btc_module.get_cpayment_node_deposits()
            answ['profit'] = answ['wallet_funds']['funds'] + answ['wallet_funds']['secondary'] + answ['wallet_funds']['cpayments'] - answ['db_funds'] + answ['binance'] - imbalance
        else:
            answ['profit'] = answ['wallet_funds'] - answ['db_funds'] + answ['binance'] - imbalance

        if symbol == 'usdt':
            answ['trx_balance'] = TRX.get_balance()

        return answ

    def _get_deals_income(self, interval_days, symbol, session):
        income = session.execute(
            """
                SELECT COALESCE(SUM(buyer_commission) + SUM(seller_commission) - SUM(referral_commission_buyer) - SUM(referral_commission_seller), 0)
                FROM deal_commissions
                WHERE symbol = :symbol AND created_at > NOW() - INTERVAL '1 day' * :interval_days
            """, {'symbol': symbol, 'interval_days': interval_days}
        ).scalar()
        return income

    def _get_merchants_income(self, interval_days, symbol, session):
        income = session.execute(
            """
                SELECT COALESCE(SUM(merchant_commission), 0)
                FROM deal_commissions
                WHERE symbol = :symbol AND created_at > NOW() - INTERVAL '1 day' * :interval_days
            """, {'symbol': symbol, 'interval_days': interval_days}
        ).scalar()
        return income

    def _get_transactions_income(self, interval_days, symbol, session):
        income = session.execute(
            """
                SELECT COALESCE(SUM(commission), 0)
                FROM transactions
                JOIN wallet w on transactions.wallet_id = w.id
                WHERE symbol = :symbol AND is_confirmed AND 
                    processed_at > NOW() - INTERVAL '1 day' * :interval_days AND type = 'out'
            """, {'symbol': symbol, 'interval_days': interval_days}
        ).scalar()
        return income

    def get_finreport(self, symbol, session):
        interval_days = {'day': 1, 'week': 7, 'month': 30, 'year': 365}
        answ = {}
        for name, interval in interval_days.items():
            answ[f'transactions_{name}'] = self._get_transactions_income(interval, symbol, session)
            answ[f'deals_{name}'] = self._get_deals_income(interval, symbol, session)
            answ[f'merchants_{name}'] = self._get_merchants_income(interval, symbol, session)
        return answ

    def change_withdraw_status(self, symbol):
        with session_scope() as session:
            res = session.execute(
                """
                    UPDATE crypto_settings 
                    SET withdraw_active = NOT withdraw_active
                    WHERE symbol = :symbol
                    RETURNING withdraw_active
                """, {'symbol': symbol}
            ).scalar()
        return {'status': res}

    def get_withdraw_status(self, symbol):
        with session_scope() as session:
            res = session.execute(
                """
                    SELECT withdraw_active
                    FROM crypto_settings 
                    WHERE symbol = :symbol
                """, {'symbol': symbol}
            ).scalar()
        return res

    def get_setting(self, name, session, return_type=str):
        res = session.execute("SELECT value FROM settings WHERE key = :name", {'name': name}).scalar()
        return return_type(res)

    def change_fast_deal_status(self, session):
        current_status = self.get_setting('fast_deal_active', session, return_type=lambda x: bool(strtobool(x)))
        session.execute(
            'UPDATE settings SET value = :val WHERE key = :key',
            {'key': 'fast_deal_active', 'val': str(not current_status).lower()}
        )
        return {'status': self.get_setting('fast_deal_active', session, return_type=lambda x: bool(strtobool(x)))}

    def get_frozen_all(self, symbol, session):
        res = session.execute(
            """
                SELECT nickname, frozen
                FROM wallet
                JOIN "user" ON wallet.user_id = "user".id
                WHERE frozen > 0 AND symbol = :sym
            """, {'sym': symbol}
        ).fetchall()
        answer = []
        for nickname, frozen in res:
            answer.append({'user': nickname, 'frozen': manager.from_subunit(symbol, frozen)})
        return answer

    def create_wallet_if_not_exists(self, symbol, user_id, session):
        if not self.is_wallet_exists(symbol, user_id, session):
            pk = self.crypto_manager.get_new_pk(symbol)
            session.execute(f"INSERT INTO wallet (user_id, symbol, private_key) VALUES ({user_id}, '{symbol}', '{pk}')")
            return {'success': 'wallet created'}
        return {'success': 'wallet was already created'}

    def get_user_id(self, telegram_id, session=None):
        if session:
            return session.execute(f'SELECT id from "user" where telegram_id = {telegram_id}').scalar()
        else:
            with session_scope() as session:
                return session.execute(f'SELECT id from "user" where telegram_id = {telegram_id}').scalar()

    def is_user_have_rights(self, user_id, rights, session):
        return session.execute(
            f"""
                SELECT EXISTS(SELECT 1 FROM "user" WHERE id = {user_id} AND rights >= '{rights}')
            """
        ).scalar()

    def _get_admins(self, session):
        q = 'SELECT telegram_id FROM "user" WHERE is_admin'
        return [res[0] for res in session.execute(q).fetchall()]

    def _get_currencies(self, session):
        curs = [dict(item) for item in session.execute("SELECT id, rate_variation FROM currency").fetchall()]
        return curs

    def get_settings(self, symbol, session):
        res = session.execute(
            """
                SELECT symbol, coin_name, tx_out_commission, min_tx_amount, max_withdraw
                FROM crypto_settings
                WHERE symbol = :sym
            """, {'sym': symbol}
        ).fetchone()
        if not res:
            raise BadRequest('wrong symbol')
        symbol, coin_name, tx_out_commission, min_tx_amount, max_withdraw = res
        settings = {
            'symbol': symbol,
            'coin_name': coin_name,
            'commission': tx_out_commission,
            'min_tx_amount': min_tx_amount,
            'profits_chat': PROFITS_CHAT,
            'earnings_chat': EARNINGS_CHAT,
            'control_chat': CONTROL_CHATS[symbol],
            'messages_chat': MESSAGES_CHAT,
            'deal_control_chat': DEAL_CONTROL_CHAT,
            'admins': self._get_admins(session),
            'dispute_time': DISPUTE_TIME,
            'max_withdraw': max_withdraw,
            'base_deal_time': int(session.execute("SELECT value FROM settings WHERE key = 'base_deal_time' LIMIT 1").scalar()),
            'advanced_deal_time': int(session.execute("SELECT value FROM settings WHERE key = 'advanced_deal_time' LIMIT 1").scalar()),
            'currencies': self._get_currencies(session)
        }
        return settings

    def get_user_existing(self, telegram_id, session):
        return {'exists': self.is_user_exists(telegram_id, session)}

    def get_commission(self, symbol, amount, session):
        if symbol == 'btc':
            commission = self._get_btc_commission(amount, session)
            dynamic_commissions = self._get_btc_commissions_from_database(session)
        elif symbol == 'usdt':
            commission = self._get_usdt_commission(amount, session)
            dynamic_commissions = self._get_usdt_commissions_from_database(session)
        else:
            commission = self.get_settings(symbol, session)['commission']
            dynamic_commissions = None

        return {'commission': commission, 'dynamic_commissions': dynamic_commissions}

    def get_user_existing_by_nickname(self, symbol, nickname, session):
        q = """
            SELECT EXISTS(
                SELECT 1
                FROM "user"
                JOIN wallet w on "user".id = w.user_id
                WHERE nickname = :nick AND symbol = :sym
            )
        """
        return {'exists': session.execute(q, {'nick': nickname, 'sym': symbol}).scalar()}

    def add_message(self, user_id, symbol, text, message_id, is_bot):
        # text = text.replace("'", "''").replace('%', '%%')
        insert_dynamo(
            {
                'user_id': user_id,
                'message_id': message_id,
                'symbol': symbol,
                'text': text,
                'is_bot': is_bot
            }
        )

    def add_error(self, telegram_id, symbol, text, session):
        text = text.replace("'", "''").replace('%', '%%')
        q = f"""
            INSERT INTO error (user_id, symbol, text) 
            VALUES ((SELECT id FROM "user" WHERE telegram_id = {telegram_id}), '{symbol}', '{text}')
        """
        if self.is_user_exists(telegram_id, session):
            session.execute(q)

    def update_currency(self, user_id, currency, session):
        self._validate_currency(currency, session)
        session.execute('UPDATE "user" SET currency = :cur WHERE id = :uid', {'uid': user_id, 'cur': currency})

    def update_delete_status(self, symbol, user_id, is_deleted, session):
        q = 'UPDATE "user" SET is_deleted = :is_del WHERE id = :uid'
        session.execute(q, {'is_del': is_deleted, 'uid': user_id})
        if is_deleted:
            session.execute(
                f"UPDATE lot SET is_active = FALSE WHERE user_id = :uid AND symbol = :sym",
                {'uid': user_id, 'sym': symbol}
            )

    def update_verify_status(self, symbol, user_id, is_verify, session):
        q = 'UPDATE "user" SET is_verify = :is_ver WHERE id = :uid'
        session.execute(q, {'is_ver': is_verify, 'uid': user_id})

    def update_super_verify_only_status(self, symbol, user_id, super_verify_only, session):
        q = 'UPDATE "user" SET super_verify_only = :super_verify_only WHERE id = :uid'
        session.execute(q, {'super_verify_only': super_verify_only, 'uid': user_id})

    def update_allow_super_buy_status(self, symbol, user_id, allow_super_buy, session):
        q = 'UPDATE "user" SET allow_super_buy = :allow_super_buy WHERE id = :uid'
        session.execute(q, {'allow_super_buy': allow_super_buy, 'uid': user_id})

    def update_sky_pay_status(self, symbol, user_id, sky_pay, session):
        q = 'UPDATE "user" SET sky_pay = :sky_pay WHERE id = :uid'
        session.execute(q, {'sky_pay': sky_pay, 'uid': user_id})

    def update_allow_sell_status(self, symbol, user_id, allow_sell, session):
        q = 'UPDATE "user" SET allow_sell = :allow_sell WHERE id = :uid'
        session.execute(q, {'allow_sell': allow_sell, 'uid': user_id})

    def update_allow_sale_v2_status(self, symbol, user_id, allow_sale_v2, session):
        q = 'UPDATE "user" SET allow_sale_v2 = :allow_sale_v2 WHERE id = :uid'
        session.execute(q, {'allow_sale_v2': allow_sale_v2, 'uid': user_id})

    def update_ban_status(self, symbol, user_id, is_baned, session):
        session.execute(
            'UPDATE "user" SET is_baned = :is_baned WHERE id = :uid',
            {'is_baned': is_baned, 'uid': user_id}
        )
        if is_baned:
            session.execute('UPDATE wallet SET is_active = FALSE WHERE user_id = :uid', {'uid': user_id})

    def update_shadow_ban_status(self, symbol, user_id, shadow_ban, session):
        session.execute(
            'UPDATE "user" SET shadow_ban = :shadow_ban WHERE id = :uid',
            {'shadow_ban': shadow_ban, 'uid': user_id}
        )

    def update_apply_shadow_ban_status(self, symbol, user_id, apply_shadow_ban, session):
        session.execute(
            'UPDATE "user" SET apply_shadow_ban = :apply_shadow_ban WHERE id = :uid',
            {'apply_shadow_ban': apply_shadow_ban, 'uid': user_id}
        )

    def update_lang(self, user_id, lang, session):
        session.execute(
            'UPDATE "user" SET lang = :lang WHERE id = :uid',
            {'lang': lang, 'uid': user_id}
        )

    def change_trading_status(self, symbol, user_id, session):
        q = "UPDATE wallet SET is_active = NOT is_active WHERE symbol = :sym AND user_id = :uid RETURNING is_active"
        is_acitve = session.execute(q, {'uid': user_id, 'sym': symbol}).scalar()
        return {'is_active': is_acitve}

    def _validate_ban_on_user(self, user_id, receiver_id, session):
        is_baned = self.get_usermessages_ban_status(user_id, receiver_id, session)['is_baned']
        if is_baned:
            raise BadRequest('Target user baned current user')

    def get_usermessages_ban_status(self, user_id, target_user_id, session):
        status = session.execute(
            'SELECT EXISTS(SELECT 1 FROM usermessageban WHERE user_id = :recid AND baned_id = :uid)',
            {'recid': target_user_id, 'uid': user_id}
        ).scalar()
        return {'is_baned': status}

    def set_usermessages_ban_status(self, user_id, target_user_id, status, session):
        current_status = self.get_usermessages_ban_status(target_user_id, user_id, session)['is_baned']
        if current_status != status:
            data = {'uid': user_id, 'buid': target_user_id}
            if status:
                session.execute('insert into usermessageban (user_id, baned_id) VALUES (:uid, :buid)', data)
            else:
                session.execute('DELETE FROM usermessageban WHERE user_id = :uid AND baned_id = :buid', data)
        return {'is_baned': status}

    def create_new_usermessage(self, symbol, sender_id, receiver_id, message, media_id, session):
        self._validate_ban_on_user(sender_id, receiver_id, session)
        sender_nickname = self.get_user(sender_id, session)['nickname']
        if sender_nickname not in ('SUPPORT', 'SKYPAY'):
            all_links = re.findall(r'(https?://\S+)', message)
            for link in all_links:
                message = message.replace(link, '')
        if message or media_id:
            q = """
                INSERT INTO usermessage (sender_id, receiver_id, message, symbol, media_id)
                VALUES (:sid, :rid, :msg, :sym, :mid)
                RETURNING id
            """
            message_id = session.execute(
                q, {'sid': sender_id, 'rid': receiver_id,
                    'msg': message, 'sym': symbol,
                    'mid': media_id if media_id else None}
            ).scalar()
            create_message_notification(receiver_id, sender_id, message, message_id, media_id, symbol, session)
        return {'success': ''}

    def can_create_lot(self, user, limit_from, limit_to, _type):
        if _type not in (LOT_TYPE_BUY, LOT_TYPE_SELL):
            return False
        if user['is_baned'] or user['is_deleted']:
            return False
        if limit_from > limit_to or limit_from <= 0 or limit_to <= 0:
            return False
        return True

    def get_lot(self, identificator, session):
        q = """
            SELECT id, identificator, limit_from, limit_to, details, broker_id, rate,
                   coefficient, is_active, is_deleted, currency, type, user_id, symbol
            FROM lot
            WHERE identificator = :id
            LIMIT 1
        """
        res = session.execute(q, {'id': identificator}).fetchone()
        if not res:
            raise BadRequest

        (lot_id, identificator, limit_from, limit_to, details, broker_id, rate, coefficient, is_active,
            is_deleted, currency, t, user_id, symbol) = res
        return {'id': lot_id, 'identificator': identificator, 'limit_from': limit_from, 'limit_to': limit_to, 'details': details,
                'broker': self._get_broker_name_by_id(broker_id, session), 'rate': rate, 'coefficient': coefficient, 'is_active': is_active,
                'is_deleted': is_deleted, 'currency': currency, 'type': t, 'user_id': user_id, 'symbol': symbol}

    def is_lot_exists(self, user_id, symbol, identificator, session):
        q = """
            SELECT EXISTS(
                SELECT 1 FROM lot
                WHERE identificator = :ident AND symbol = :sym AND user_id = :uid
            )
        """
        return session.execute(q, {'ident': identificator, 'sym': symbol, 'uid': user_id}).scalar()

    def _update_limits(self, identificator, limit_from, limit_to, session):
        q = f"""
            UPDATE lot SET limit_to = {limit_to}, limit_from = {limit_from}
            WHERE identificator = '{identificator}'
        """
        session.execute(q)

    def _update_rate(self, lot, rate, session):
        q = f"""
            UPDATE lot SET rate = :rate, coefficient = NULL
            WHERE id = :id
        """
        session.execute(q, {'rate': rate, 'id': lot['id']})
        session.execute(
            """
                INSERT INTO change_lot_rate_history (from_rate, to_rate, from_coefficient, to_coefficient, lot_id) 
                VALUES (:from_rate, :to_rate, :from_coefficient, :to_coefficient, :lid)
            """, {
                'from_rate': lot['rate'],
                'to_rate': rate,
                'from_coefficient': lot['coefficient'],
                'to_coefficient': None,
                'lid': lot['id']
            }
        )

    def _update_coefficient(self, lot, coefficient, rate, session):
        q = f"""
            UPDATE lot SET coefficient = :coeff, rate = :rate
            WHERE id = :id
        """
        session.execute(q, {'coeff': coefficient, 'id': lot['id'], 'rate': rate})
        session.execute(
            """
                INSERT INTO change_lot_rate_history (from_rate, to_rate, from_coefficient, to_coefficient, lot_id) 
                VALUES (:from_rate, :to_rate, :from_coefficient, :to_coefficient, :lid)
            """, {
                'from_rate': lot['rate'],
                'to_rate': rate,
                'from_coefficient': lot['coefficient'],
                'to_coefficient': coefficient,
                'lid': lot['id']
            }
        )

    def _update_details(self, identificator, details, session):
        q = f"""
            UPDATE lot SET details = :det
            WHERE identificator = :id
        """
        session.execute(q, {'det': details, 'id': identificator})

    def _update_activity_status(self, identificator, activity_status, session):
        q = f"""
            UPDATE lot SET is_active = :act
            WHERE identificator = :id
        """
        session.execute(q, {'act': activity_status, 'id': identificator})

    def update_lot(self, user_id, symbol, identificator, limit_from, coefficient,
                   limit_to, rate, details, activity_status, session):
        if not self.is_lot_exists(user_id=user_id, symbol=symbol, identificator=identificator, session=session):
            raise BadRequest

        lot = self.get_lot(identificator, session)

        if limit_from is not None and limit_to is not None and limit_to >= limit_from > 0:
            self._update_limits(identificator, limit_from, limit_to, session)

        if coefficient is not None and rate is not None and rate > 0:
            self._update_coefficient(lot, coefficient, rate, session)
        elif rate is not None and rate > 0:
            self._update_rate(lot, rate, session)

        if details is not None:
            self._update_details(identificator, details, session)

        if activity_status is not None:
            self._update_activity_status(identificator, activity_status, session)

        return {'success': 'lot updated'}

    def delete_lot(self, user_id, symbol, identificator, session):
        if self.is_lot_exists(user_id=user_id, symbol=symbol, identificator=identificator, session=session):
            q = f"""
                UPDATE lot SET is_deleted = TRUE
                WHERE identificator = '{identificator}'
            """
            session.execute(q)
            return {'success': 'lot deleted'}

    def create_new_lot(self, symbol, user_id, coefficient, rate, limit_from, limit_to, _type, broker, session):
        user = self.get_user(user_id, session)
        if self.can_create_lot(user, limit_from, limit_to, _type):
            identificator = generate_lot_id()

            data = {
                'ident': identificator, 'lim_from': limit_from,
                'lim_to': limit_to, 'broker': broker, 'rate': rate,
                'uid': user_id, 'cur': user['currency'], 'type': _type, 'sym': symbol,
                'coefficient': coefficient
            }
            q = """
                INSERT INTO lot (identificator, limit_from, limit_to, broker_id, rate, user_id,
                                currency, type, coefficient, symbol)
                VALUES (:ident, :lim_from, :lim_to, :broker, :rate, :uid, :cur, :type, :coefficient, :sym)
                """
            session.execute(q, data)
            return self.get_lot(identificator, session)

    def get_user(self, user_id, session, expand_email=False, expand_rating=False):
        res = session.execute(
            f"""
            SELECT id, telegram_id, nickname, lang, is_baned, is_deleted, is_verify,
                   sky_pay, allow_super_buy, currency, ref_kw, email, allow_sell, allow_sale_v2,
                    email, rating, shadow_ban, apply_shadow_ban, super_verify_only
            FROM "user" 
            WHERE id = :uid
            LIMIT 1
            """, {'uid': user_id}
        )
        res = res.fetchone()
        if not res:
            raise BadRequest('no such user')
        id_, telegram_id, nickname, lang, is_baned, is_deleted, is_verify, sky_pay, allow_super_buy, currency, ref_kw, email, \
                allow_sell, allow_sale_v2, email, rating, shadow_ban, apply_shadow_ban, super_verify_only = res
        is_admin = self.is_user_have_rights(user_id, 'low', session)
        data = {
            'id': id_, 'telegram_id': telegram_id, 'nickname': nickname, 'lang': lang, 'currency': currency,
            'is_baned': is_baned, 'is_deleted': is_deleted, 'is_verify': is_verify, 'is_admin': is_admin,
            'ref_code': ref_kw or nickname, 'email': email, 'allow_sell': allow_sell, 'allow_sale_v2': allow_sale_v2, 'sky_pay': sky_pay,
            'allow_super_buy': allow_super_buy, 'shadow_ban': shadow_ban, 'apply_shadow_ban': apply_shadow_ban,
            'super_verify_only': super_verify_only
        }
        if expand_email:
            data['email'] = email
        if expand_rating:
            data['rating'] = rating
        return data

    def get_user_info(self, symbol, nickname, session):
        q = f"""
            SELECT id, telegram_id, nickname, lang, is_baned, is_deleted, is_verify, super_verify_only, currency,
                allow_sell, allow_sale_v2, sky_pay, allow_super_buy, shadow_ban, apply_shadow_ban
            FROM "user"
            WHERE nickname = :nickname
            LIMIT 1
        """
        res = session.execute(q, {'nickname': nickname}).fetchone()
        data = dict(res)
        stat = self.get_user_stat(symbol, data['id'], session)
        wallet = self.get_wallet(symbol, data['id'], session)
        data = {**wallet, **data, **stat}
        return data

    def get_user_stat(self, symbol, user_id, session):
        q = """
            SELECT w.id, is_verify, nickname, created_at, rating, total_likes, total_dislikes
            FROM wallet w
            LEFT JOIN "user" u ON w.user_id = u.id
            WHERE u.id = :uid AND w.symbol = :sym
            LIMIT 1
        """

        wallet_id, is_verify, nick, created_at, rating, likes, dislikes = session.execute(
            q,
            {'uid': user_id, 'sym': symbol}
        ).fetchone()

        q = """
            SELECT type, sum(amount_units) FROM transactions WHERE wallet_id = :wid GROUP BY type
        """

        deposited = 0
        withdrawn = 0
        for t, total_value in session.execute(q, {'wid': wallet_id}).fetchall():
            if t == 'in':
                deposited = total_value
            elif t == 'out':
                withdrawn = total_value

        q = """
            SELECT count(*), coalesce(sum(amount_subunit), 0), coalesce(sum(amount_currency), 0)
            FROM deal
            WHERE (buyer_id = :uid OR seller_id = :uid) AND state = 'closed' AND symbol = :sym
        """

        deals, value, total_value_currency = session.execute(q, {'uid': user_id, 'sym': symbol}).fetchone()
        value = self.crypto_manager.from_subunit(symbol, value)

        days_registered = (datetime.utcnow().date() - created_at).days

        rating_logo = self.get_rating_sm(rating)

        answ = {
            'deposited': deposited, 'withdrawn': withdrawn, 'rating': rating, 'rating_logo': rating_logo,
            'deals': deals, 'revenue': value, 'days_registered': days_registered, 'likes': likes, 'dislikes': dislikes
        }

        return answ

    def get_rating_sm(self, points):
        if points < 0:
            return MINUS_RATING_SMILE
        else:
            index = round(points / 10)
            return RATING_SMILES[index]

    def _get_broker_name_by_id(self, broker_id, session):
        broker_name = session.execute('SELECT name FROM broker WHERE id = :bid', {'bid': broker_id}).scalar()
        return broker_name

    def get_active_deals_count(self, symbol, user_id, session):
        q = f"""
            SELECT COUNT(*)
            FROM deal d
            WHERE symbol = :sym AND (buyer_id = :uid OR seller_id = :uid) AND state not in ('deleted', 'closed')
        """
        active_deals_count = session.execute(q, {'sym': symbol, 'uid': user_id}).scalar()
        return {'count': active_deals_count}

    def get_active_deals(self, symbol, user_id, session):
        q = f"""
            SELECT d.identificator, (SELECT broker_id FROM lot WHERE id = lot_id), currency, amount_currency,
                (SELECT EXISTS(SELECT 1 FROM dispute WHERE deal_id = d.id)), state
            FROM deal d
            WHERE symbol = :sym AND (buyer_id = :uid OR seller_id = :uid) AND state not in ('deleted', 'closed')
        """
        active_deals = session.execute(q, {'sym': symbol, 'uid': user_id}).fetchall()
        answ = []
        for identificator, broker_id, currency, amount_currency, dispute_exists, state in active_deals:
            d = {'identificator': identificator, 'broker': self._get_broker_name_by_id(broker_id, session),
                 'currency': currency, 'amount_currency': amount_currency, 'dispute_exists': dispute_exists,
                 'state': state}
            answ.append(d)
        return answ

    def get_user_lots(self, symbol, user_id, session):
        q = """
            SELECT l.id, identificator, type, rate, currency, name, l.is_active, coefficient
            FROM lot l 
            JOIN "broker" b on l.broker_id = b.id 
            WHERE user_id = :uid AND symbol = :sym AND NOT l.is_deleted
        """
        data = session.execute(q, {'uid': user_id, 'sym': symbol}).fetchall()
        answ = []
        for _id, identificator, t, rate, currency, broker, is_active, coefficient in data:
            d = {'identificator': identificator, 'type': t, 'rate': rate, 'currency': currency,
                 'is_active': is_active, 'id': _id, 'broker': broker, 'coefficient': coefficient}
            answ.append(d)
        return answ

    def buy(self, symbol, user_id, session):
        user = self.get_user(user_id, session)
        subunits_in_unit = self.crypto_manager.to_subunit(symbol=symbol, val=1)
        q = """
            SELECT broker_id, MIN(l.rate), COUNT(l.id) 
            FROM lot l
            LEFT JOIN "user" u ON l.user_id = u.id
            LEFT JOIN wallet w on u.id = w.user_id
            WHERE l.symbol = :sym AND w.symbol = :sym AND l.is_active AND NOT l.is_deleted AND l.type = 'sell' AND 
                l.currency = :cur AND NOT u.is_baned AND limit_to >= limit_from AND
                NOT u.is_deleted AND w.is_active AND limit_from/rate*:sub <= w.balance AND 100/rate*:sub <= w.balance AND
                NOT stealth AND is_verify
            GROUP BY l.broker_id
            ORDER BY COUNT(l.id) DESC;
        """
        kw = {'sym': symbol, 'cur': user['currency'], 'sub': subunits_in_unit}
        data = session.execute(q, kw).fetchall()
        answ = []
        for broker_id, rate, cnt in data:
            answ.append(
                {'broker': {'id': broker_id, 'name': self._get_broker_name_by_id(broker_id, session)},
                 'rate': rate,
                 'cnt': cnt
                 }
            )
        return answ

    def sell(self, symbol, user_id, session):
        user = self.get_user(user_id, session)
        q = f"""
            SELECT broker_id, MAX(l.rate), COUNT(l.id) 
            FROM lot l
            LEFT JOIN "user" u ON l.user_id = u.id
            LEFT JOIN wallet w on u.id = w.user_id and w.symbol = l.symbol
            WHERE l.symbol = :sym AND w.symbol = :sym AND l.is_active AND NOT l.is_deleted
                AND l.type = 'buy' AND l.currency = :cur AND NOT u.is_baned
                AND limit_to >= limit_from AND NOT u.is_deleted AND w.is_active AND NOT stealth AND is_verify
            GROUP BY broker_id
            ORDER BY COUNT(l.id) DESC;
        """
        kw = {'sym': symbol, 'cur': user['currency']}
        data = session.execute(q, kw).fetchall()
        answ = []
        for broker_id, rate, cnt in data:
            answ.append(
                {
                    'broker': {
                        'id': broker_id,
                        'name': self._get_broker_name_by_id(broker_id, session)
                    },
                    'rate': rate,
                    'cnt': cnt
                }
            )
        return answ

    def _is_online(self, t):
        return datetime.utcnow() - t < timedelta(minutes=ONLINE_MINUTES)

    def _get_maximum_limit(self, symbol, limit_to, rate, seller_balance):
        seller_balance = self.crypto_manager.from_subunit(symbol, seller_balance)
        max_to_sell = seller_balance * rate
        if max_to_sell < limit_to:
            return int(max_to_sell)
        else:
            return limit_to

    def broker_lots_buy(self, symbol, user_id, broker, session):
        user = self.get_user(user_id, session)
        q = """
            SELECT identificator, limit_from, limit_to, l.currency, balance, rate, is_verify, u.id, last_action
            FROM lot l
            LEFT JOIN "user" u ON l.user_id = u.id
            LEFT JOIN wallet w on u.id = w.user_id and w.symbol = l.symbol
            WHERE l.symbol = :sym AND l.is_active AND NOT l.is_deleted AND l.type = 'sell' AND l.broker_id = :broker
                AND l.currency = :cur AND NOT u.is_baned AND NOT u.is_deleted AND w.is_active AND NOT stealth AND is_verify
            ORDER BY rate
        """
        data = session.execute(q, {'sym': symbol, 'broker': broker, 'cur': user['currency']}).fetchall()
        answ = []
        for identificator, limit_from, limit_to, currency, balance, rate, is_verify, uid, last_action in data:
            limit_to = self._get_maximum_limit(symbol, limit_to, rate, seller_balance=balance)
            if limit_to < limit_from or limit_to <= 100:
                continue
            d = {'limit_from': limit_from, 'limit_to': limit_to, 'rate': rate, 'is_verify': is_verify,
                 'owner': user['id'] == uid, 'is_online': self._is_online(last_action), 'identificator': identificator,
                 'currency': currency}
            answ.append(d)
        return answ

    def broker_lots_sell(self, symbol, user_id, broker, session):
        user = self.get_user(user_id, session)
        q = """
            SELECT identificator, limit_from, limit_to, l.currency, balance, rate, is_verify, u.id, last_action, type
            FROM lot l
            LEFT JOIN "user" u ON l.user_id = u.id
            LEFT JOIN wallet w on u.id = w.user_id and w.symbol = l.symbol
            WHERE l.symbol = :sym AND l.is_active AND NOT l.is_deleted AND l.type = 'buy' AND l.broker_id = :broker
                AND l.currency = :cur AND NOT u.is_baned AND NOT u.is_deleted AND w.is_active AND limit_to >= limit_from
                AND NOT stealth AND is_verify
            ORDER BY rate DESC
        """
        data = session.execute(q, {'sym': symbol, 'broker': broker, 'cur': user['currency']}).fetchall()
        answ = []
        for identificator, limit_from, limit_to, currency, balance, rate, is_verify, uid, last_action, ltype in data:
            if ltype == 'sell':
                total_balance_currency = manager.from_subunit(symbol, balance) * rate
                if total_balance_currency < limit_from:
                    continue
            d = {'limit_from': limit_from, 'limit_to': limit_to, 'rate': rate, 'is_verify': is_verify,
                 'owner': user['id'] == uid, 'is_online': self._is_online(last_action), 'identificator': identificator,
                 'currency': currency}
            answ.append(d)
        return answ

    def _get_earned_from_ref(self, symbol, user_id, session):
        q = """
            SELECT earned_from_ref
            FROM wallet
            WHERE user_id = :uid AND symbol = :symbol
        """
        total_commission = session.execute(q, {'uid': user_id, 'symbol': symbol}).fetchone()[0]
        total_commission = self.crypto_manager.from_subunit(symbol, total_commission)
        return total_commission

    def _get_ref_kw(self, user_id, session):
        nick, ref_kw = session.execute('SELECT nickname, ref_kw FROM "user" WHERE id = :id', {'id': user_id}).fetchone()
        ref_kw = ref_kw.strip()
        if not ref_kw:
            session.execute('UPDATE "user" SET ref_kw = :nick WHERE id = :user_id', {'nick': nick, 'user_id': user_id})
            return nick
        return ref_kw

    def get_affiliate(self, symbol, user_id, session):
        q = f"""
            SELECT count(*)
            FROM wallet 
            WHERE symbol = '{symbol}' AND referred_from_id = {user_id}
        """
        invited_count = session.execute(q).fetchone()[0]
        earned_from_ref = self._get_earned_from_ref(symbol, user_id, session)
        user = self.get_user(user_id, session)
        currency = user['currency']
        earned_from_ref_currency = self.get_rate(symbol, currency, session) * earned_from_ref
        answ = {
            'earned_from_ref': earned_from_ref,
            'earned_from_ref_currency': earned_from_ref_currency,
            'invited_count': invited_count,
            'ref_code': self._get_ref_kw(user_id, session)
        }
        return answ

    def get_active_promocodes_count(self, symbol, user_id, session):
        return {'count': len(self.get_active_promocodes(symbol, user_id, session))}

    def get_active_promocodes(self, symbol, user_id, session):
        q = f"""
            SELECT p.id, p.code, p.amount, count(pa.promocode_id), count
            FROM promocodes p
            LEFT JOIN promocodeactivations pa ON p.id = pa.promocode_id
            LEFT JOIN wallet w ON p.wallet_id = w.id
            WHERE w.user_id = {user_id} AND w.symbol = '{symbol}' AND NOT p.is_deleted
            GROUP BY p.id
            HAVING p.count > count(pa.promocode_id);
        """
        promocodes = session.execute(q).fetchall()
        answ = []
        for _id, code, amount, activations, count in promocodes:
            amount = self.crypto_manager.from_subunit(symbol, amount)
            answ.append({'code': code, 'amount': amount, 'activations': activations, 'count': count, 'id': _id})
        return answ

    def can_activate_promocode(self, symbol, code, user_id, session):
        q = f"""SELECT EXISTS
            (
                SELECT 1
                FROM promocodes p
                LEFT JOIN wallet w ON p.wallet_id = w.id
                LEFT JOIN promocodeactivations p2 ON p.id = p2.promocode_id
                WHERE code = :code AND NOT is_deleted AND symbol = :sym AND w.user_id <> :uid
                GROUP BY p.id
                HAVING COUNT(p2.promocode_id) < p.count
            )
        """
        can_principal_activate = session.execute(q, {'code': code, 'sym': symbol, 'uid': user_id}).scalar()
        if can_principal_activate:
            q = f"""
                SELECT NOT EXISTS(
                    SELECT 1
                    FROM promocodeactivations pa
                    LEFT JOIN promocodes p ON pa.promocode_id = p.id
                    LEFT JOIN wallet w ON pa.wallet_id = w.id
                    WHERE p.code = :code AND w.user_id = :uid
                )
            """
            return session.execute(q, {'code': code, 'uid': user_id}).scalar()
        else:
            return False

    def _does_have_one_deal(self, symbol, user_id, session):
        q = f"""
            SELECT EXISTS( 
                SELECT 1
                FROM deal d 
                WHERE symbol = :sym AND :uid IN (buyer_id, seller_id)
            )
        """
        return session.execute(q, {'sym': symbol, 'uid': user_id}).fetchone()[0]

    def promocode_activation(self, symbol, user_id, code, session):
        if not self.can_activate_promocode(symbol, code, user_id, session):
            return

        q = f"""
                SELECT user_id, amount, p.id, w.id
                FROM promocodes p
                LEFT JOIN wallet w ON p.wallet_id = w.id
                WHERE code = :code
                LIMIT 1
            """
        owner_id, amount, promocode_id, owner_wallet_id = session.execute(q, {'code': code}).fetchone()
        q = """
            INSERT INTO promocodeactivations (wallet_id, promocode_id) 
            VALUES ((SELECT id FROM wallet WHERE symbol = :sym AND user_id = :uid), :pid)
            RETURNING id
        """
        change_frozen(owner_id, msg=f'Promocode {promocode_id} activation', symbol=symbol, amount_subunits=-amount,
                      session=session)
        change_balance(user_id, msg=f'Promocode {promocode_id} activation', symbol=symbol, amount_subunits=amount,
                       session=session)
        amount_units = manager.from_subunit(symbol, amount)
        create_operation(session, owner_id, code, symbol, None, -amount_units, action=Action.promocode)
        create_operation(session, user_id, code, symbol, None, amount_units, action=Action.promocode)
        paid = session.execute(q, {'sym': symbol, 'uid': user_id, 'pid': promocode_id}).scalar()
        session.execute(
            """
                INSERT INTO notification (user_id, symbol, type, promocodeactivation_id)
                VALUES (:uid, :sym, 'promocode', :paid)
            """, {'uid': owner_id, 'sym': symbol, 'paid': paid}
        )
        if not self._does_have_one_deal(symbol, user_id, session):
            q = """
                UPDATE wallet
                SET referred_from_id = :owner_id
                WHERE user_id = :uid AND symbol = :sym
            """
            session.execute(q, {'owner_id': owner_id, 'uid': user_id, 'sym': symbol})

        amount = self.crypto_manager.from_subunit(symbol, amount)
        return {'amount': amount, 'symbol': symbol, 'code': code, 'owner_id': owner_id}

    def get_promocode(self, symbol, code, session):
        activations, amount, count = session.execute(
            """
                SELECT count(p2.promocode_id), p.amount, p.count
                FROM promocodes p
                LEFT JOIN promocodeactivations p2 ON p.id = p2.promocode_id
                LEFT JOIN wallet w ON p.wallet_id = w.id
                WHERE w.symbol = :sym and code = :code
                GROUP BY p2.promocode_id, p.amount, p.count;
            """, {'sym': symbol, 'code': code}
        ).fetchone()
        if activations is not None:
            amount = self.crypto_manager.from_subunit(symbol, amount)
            return {'amount': amount, 'activations': activations, 'count': count, 'code': code}

    def get_promocodes_count_last_day(self, user_id, session):
        return session.execute(
            """
                SELECT COALESCE(COUNT(*), 0)
                FROM promocodes p
                JOIN wallet w on p.wallet_id = w.id
                WHERE created_at > NOW() - INTERVAL '1 day' AND user_id = :uid
            """, {'uid': user_id}
        ).scalar()

    def create_promocode(self, symbol, user_id, *, activations, amount, session):
        self._validate_shadow_ban(user_id, session)
        user = self.get_user(user_id, session)
        wallet = self.get_wallet(symbol, user_id, session)
        amount = Decimal(str(amount))
        need_amount = Decimal(activations) * amount
        if amount < MIN_PROMOCODE_AMOUNT[symbol]:
            raise BadRequest('wrong amount')
        day_promocodes_count = self.get_promocodes_count_last_day(user_id, session)
        if day_promocodes_count > 15:
            raise BadRequest('promocode limit')
        if user['is_baned']:
            raise BadRequest("You are banned")
        if wallet['balance'] < need_amount:
            raise BadRequest("You don't have enough money")
        if activations <= 0 or amount <= 0:
            raise BadRequest("wrong data")
        code = generate_promocode()
        amount = self.crypto_manager.to_subunit(symbol, amount)
        q = f"""
            INSERT INTO promocodes (wallet_id, code, amount, count)
            VALUES (:wid, :code, :amount, :ac)
            RETURNING id
        """
        promocode_id = session.execute(q, {'wid': wallet['id'], 'code': code, 'amount': amount, 'ac': activations}).scalar()
        to_freeze = Decimal(amount) * Decimal(activations)
        freeze(user['id'], msg=f'Promocode {promocode_id} creation', symbol=symbol, amount_subunits=to_freeze,
               session=session)
        return self.get_promocode(symbol, code, session)

    def delete_promocode(self, symbol, user_id, promocode_id, session):
        q = """
            SELECT p.amount * (p.count - count(pa.promocode_id))
            FROM promocodes p
            LEFT JOIN promocodeactivations pa ON pa.promocode_id = p.id
            JOIN wallet w ON p.wallet_id = w.id
            WHERE p.id = :pid AND w.symbol = :sym AND NOT p.is_deleted AND w.user_id = :uid
            GROUP BY pa.promocode_id, p.amount, p.count
        """
        amount_refund = session.execute(q, {'pid': promocode_id, 'sym': symbol, 'uid': user_id}).scalar()
        if not amount_refund:
            raise BadRequest
        q = "UPDATE promocodes SET is_deleted = TRUE WHERE id = :pid"
        unfreeze(user_id, msg=f'Promocode {promocode_id} deletion', symbol=symbol, amount_subunits=amount_refund,
                 session=session)
        session.execute(q, {'pid': promocode_id})
        return {'success': 'promocode deleted'}

    def get_last_tx_address(self, symbol, user_id, session):
        q = f"""
            SELECT to_address
            FROM transactions
            LEFT JOIN wallet w ON transactions.wallet_id = w.id
            WHERE w.symbol = :sym AND user_id = :uid AND is_confirmed AND type = 'out'
            ORDER BY created_at DESC 
            LIMIT 1
        """
        return session.execute(q, {'sym': symbol, 'uid': user_id}).scalar()

    def regenerate_wallet_if_needed(self, wallet_id, session):
        new_wallet = manager.get_new_pk('btc')
        return session.execute('UPDATE wallet SET private_key = :pk, regenerate_wallet = FALSE WHERE id = :id RETURNING private_key', {'pk': new_wallet, 'id': wallet_id}).scalar()


    def get_wallet(self, symbol, user_id, session):
        q = f"""
            SELECT id, balance, frozen, is_active, private_key, w_limit, symbol, regenerate_wallet
            FROM wallet 
            WHERE user_id = :uid AND symbol = :sym
            LIMIT 1
        """

        res = session.execute(q, {'uid': user_id, 'sym': symbol}).fetchone()
        if res is None:
            self.create_wallet_if_not_exists(symbol, user_id, session)
            res = session.execute(q, {'uid': user_id, 'sym': symbol}).fetchone()
        _id, balance, frozen, is_active, pk, withdrawal_limit, symbol, regenerate_wallet = res
        if symbol == 'btc' and regenerate_wallet:
            self.regenerate_wallet_if_needed(_id, session)
        balance = self.crypto_manager.from_subunit(symbol, balance)
        currency = self.get_user(user_id, session)['currency']
        balance_currency = self.get_rate(symbol, currency, session) * balance
        frozen = self.crypto_manager.from_subunit(symbol, frozen)
        address = self.crypto_manager.get_address_from_pk(symbol, pk) if pk else None
        last_address = self.get_last_tx_address(symbol, user_id, session)
        return {
            'balance': balance, 'balance_currency': balance_currency,
            'last_address': last_address, 'frozen': frozen, 'address': address,
            'id': _id, 'is_active': is_active,
            'withdrawal_limit': withdrawal_limit or WITHDRAWAL_DEFAULT_LIMITS[symbol],
            'symbol': symbol
        }

    def deposit_criptamat(self, symbol, user_id, session):
        if symbol != 'usdt':
            raise BadRequest
        pk = session.execute(
            "SELECT private_key FROM wallet WHERE user_id = :uid AND symbol = 'usdt'",
            {'uid': user_id}
        ).scalar()
        address = self.crypto_manager.get_address_from_pk(symbol, pk)
        data = {
            "key": "ca7fda4b-2021-4f5c-af75-b84032a8dab3",
            "url": "",
            "mail": "",
            "bidAmount": 15000,
            "wallet": address,
            "currency": "USDT"
        }
        response = requests.post('https://api.criptamat.ru/bid', json=data)
        return response.json()

    def _get_wallet_id(self, session, user_id, symbol):
        return session.execute(
            'SELECT id FROM wallet WHERE user_id = :uid AND symbol = :sym',
            {'uid': user_id, 'sym': symbol}
        ).scalar()

    def get_bind_status(self, user_id, session):
        is_connected = session.execute(
            """
                SELECT EXISTS(
                    SELECT 1 
                    FROM accounts_join
                    WHERE :uid IN (account_tg, account_web) AND confirmed
                )
            """, {'uid': user_id}
        ).scalar()
        return {'status': is_connected}

    def get_transit(self, symbol, user_id, session):
        q = """
            SELECT private_key 
            FROM wallet 
            WHERE user_id = :uid AND symbol = :sym 
            LIMIT 1
        """
        pk = session.execute(q, {'uid': user_id, 'sym': symbol}).scalar()
        address = self.crypto_manager.get_address_from_pk(symbol, pk)
        balance = self.crypto_manager.from_subunit(symbol, self.crypto_manager.get_balance(symbol, pk))
        return {'balance': balance, 'address': address, 'pk': pk}

    def get_nickname_by_id(self, uid, session):
        nickname = session.execute('SELECT nickname FROM "user" WHERE id = :uid LIMIT 1', {'uid': uid}).scalar()
        if nickname is None:
            raise BadRequest
        return nickname

    def get_payment_info(self, payment_id, session):
        payment = get_purchase(user_id=0, purchase_id=payment_id)
        merchant_nickname = self.get_nickname_by_id(payment['merchant_id'], session)
        deals_query = session.execute(
            """
                SELECT identificator, email as buyer_email
                FROM deal d
                JOIN "user" u on u.id = d.buyer_id 
                WHERE payment_id = :pid
            """, {'pid': payment['payment_id']}
        ).fetchall()
        deals = [
            {'identificator': item['identificator'], 'buyer_email': item['buyer_email']} for item in deals_query
        ]
        return {
            'merchant': merchant_nickname, 'deals': deals,
            'amount': payment['amount'], 'symbol': payment['symbol'],
            'currency': payment['currency'], 'status': payment['status'],
            'id': payment['payment_id'], 'is_currency_amount': payment['is_currency_amount'],
            'address': payment['address']
            }

    def get_payment_v2_info(self, payment_id, session):
        payment = get_payment_v2(user_id=0, payment_v2_id=payment_id)
        merchant_nickname = self.get_nickname_by_id(payment['merchant_id'], session)
        deals_query = session.execute(
            """
                SELECT identificator, email as buyer_email
                FROM deal d
                JOIN "user" u on u.id = d.buyer_id
                WHERE payment_v2_id = :pid
            """, {'pid': payment['id']}
        ).fetchall()
        deals = [
            {'identificator': item['identificator'], 'buyer_email': item['buyer_email']} for item in deals_query
        ]
        return {
            'merchant': merchant_nickname, 'deals': deals,
            'amount': payment['amount'], 'symbol': payment['symbol'],
            'currency': payment['currency'], 'status': payment['status'],
            'id': payment['id'], 'is_currency_amount': payment['is_currency_amount'],
            'address': ''
        }

    def get_sale_info(self, sale_id, session):
        sale = get_sell(user_id=0, sell_id=sale_id)
        merchant_nickname = self.get_nickname_by_id(sale['merchant_id'], session)
        deals_query = session.execute(
            """
                SELECT identificator, email as seller_email
                FROM deal d
                JOIN "user" u on u.id = d.seller_id 
                WHERE sell_id = :sid
            """, {'sid': sale['id']}
        ).fetchall()
        deals = [
            {'identificator': item['identificator'], 'seller_email': item['seller_email']} for item in deals_query
        ]
        return {
            'merchant': merchant_nickname, 'deals': deals,
            'amount': sale['amount'], 'symbol': sale['symbol'],
            'currency': sale['currency'], 'status': sale['status'],
            'id': sale['id']
        }

    def get_sale_v2_info(self, sale_v2_id, session):
        sale_v2 = get_sale_v2(user_id=0, sale_v2_id=sale_v2_id)
        merchant_nickname = self.get_nickname_by_id(sale_v2['merchant_id'], session)
        deals_query = session.execute(
            """
                SELECT identificator, email as seller_email
                FROM deal d
                JOIN "user" u on u.id = d.seller_id 
                WHERE sale_v2_id = :sid
            """, {'sid': sale_v2['id']}
        ).fetchall()
        deals = [
            {'identificator': item['identificator'], 'seller_email': item['seller_email']} for item in deals_query
        ]
        return {
            'merchant': merchant_nickname, 'deals': deals,
            'amount': sale_v2['amount'], 'symbol': sale_v2['symbol'],
            'currency': 'RUB', 'status': sale_v2['status'],
            'id': sale_v2['id']
        }

    def get_cpayment_info(self, cpayment_id, session):
        cpayment = get_cpayment(user_id=0, cpayment_id=cpayment_id)
        merchant_nickname = self.get_nickname_by_id(cpayment['merchant_id'], session)
        return {
            'merchant': merchant_nickname,
            'amount': cpayment['amount'], 'symbol': cpayment['symbol'],
            'currency': cpayment['currency'], 'status': cpayment['status'],
            'id': cpayment['id']
        }

    def get_withdrawal_info(self, withdrawal_id, session):
        withdrawal = get_withdrawal(user_id=0, withdrawal_id=withdrawal_id)
        merchant_nickname = self.get_nickname_by_id(withdrawal['merchant_id'], session)
        return {
            'merchant': merchant_nickname,
            'amount': withdrawal['amount'], 'symbol': withdrawal['symbol'],
            'status': withdrawal['status'], 'address': withdrawal['address'],
            'id': withdrawal['id']
        }

    def get_node_transaction(self, symbol, tx_hash):
        return manager.get_transaction(symbol, tx_hash)

    def get_user_id_by_code(self, code, session):
        data = session.execute(f"SELECT id, ref_kw from \"user\" where ref_kw LIKE '{code}%%'").fetchall()
        for uid, ref in data:
            if ref.strip() == code:
                return uid

    def _handle_campaign(self, session, user_id, campaign):
        if campaign:
            is_exists = session.execute(
                'SELECT EXISTS(SELECT 1 FROM campaign WHERE id = :cid)',
                {'cid': campaign}
            ).scalar()
            if is_exists:
                session.execute(
                    'INSERT INTO user_campaign (user_id, campaign_id) VALUES (:uid, :camp)',
                    {'uid': user_id, 'camp': campaign}
                )

    def get_crypto_settings(self, session, symbol):
        res = session.execute(
            """
                SELECT symbol, tx_out_commission, min_tx_amount, withdraw_active, net_commission, buyer_commission, seller_commission
                FROM crypto_settings
                WHERE symbol = :symbol
            """, {'symbol': symbol}
        ).fetchone()
        return dict(res)

    def create_user(self, telegram_id, campaign, ref_code, symbol, session):
        if not self.is_user_exists(telegram_id, session):
            referred_id = self.get_user_id_by_code(ref_code, session) if ref_code else None
            nickname = generate_nickname()
            ref_code = generate_ref_code()
            user_id = session.execute(
                'INSERT INTO "user" (telegram_id, nickname, ref_kw) VALUES (:tid, :nick, :ref) RETURNING id',
                {'tid': telegram_id, 'nick': nickname, 'ref': ref_code}
            ).scalar()
            for i, sym in enumerate(self.crypto_manager.currencies.keys()):
                pk = self.crypto_manager.get_new_pk(sym)
                if referred_id:
                    q = f"""
                        INSERT INTO wallet (user_id, symbol, private_key, referred_from_id)
                        VALUES ({user_id}, '{sym}', '{pk}', {referred_id})
                    """
                    if i == 0:
                        session.execute(
                            "INSERT INTO notification (user_id, symbol, type) VALUES (:uid, :sym, :type)",
                            {'uid': referred_id, 'sym': symbol, 'type': 'new-referral'}
                        )
                else:
                    q = f"INSERT INTO wallet (user_id, symbol, private_key) VALUES ({user_id}, '{sym}', '{pk}')"
                session.execute(q)

            self._handle_campaign(session, user_id, campaign)

        return self.get_user(user_id, session)

    def is_address_valid(self, symbol, address):
        return {'is_valid': self.crypto_manager.is_address_valid(symbol, address)}

    def send_direct_tx(self, session, user, amount_with_commission, amount, address, token, wallet, settings):
        change_balance(
            user['id'], 'External withdraw', symbol='btc',
            amount=-amount_with_commission, session=session
        )
        tx_hash = manager.currencies['btc'].create_tx_out(address, amount)
        create_operation(session, user['id'], tx_hash, 'btc', None, amount_with_commission, Action.transaction)
        try:
            if not TEST:
                requests.get('http://192.236.194.233:3333/new-p', headers={'token': token, 'txid': tx_hash})
            commission_net = manager.currencies['btc'].get_transaction_fee_secondary(tx_hash)
            logger.info(f'New direct tx: {amount} BTC -> {address}; Fee: {commission_net} BTC')
            q = """
                INSERT INTO transactions (
                    wallet_id, type, to_address, amount_units, processed_at,
                    tx_hash, commission, is_confirmed
                )
                VALUES (:wid, 'out', :address, :amount, NOW(), :tx_hash, :comm, TRUE)
            """
            session.execute(
                q, {
                    'wid': wallet['id'],
                    'address': address,
                    'amount': amount,
                    'tx_hash': tx_hash,
                    'comm': Decimal(str(settings['commission'])) - Decimal(str(commission_net))
                }
            )
        except Exception as e:
            logger.error(e)
        return {'tx_hash': tx_hash}

    def _create_transaction(self, session, wallet_id, address, amount_units):
        q = """
            INSERT INTO transactions (wallet_id, type, to_address, amount_units)
            VALUES (:wid, 'out', :address, :amount)
        """
        session.execute(q, {'wid': wallet_id, 'address': address, 'amount': amount_units})

    def _get_current_withdrawing_amount(self, wallet_id, session):
        current_amount = session.execute(
            """
                SELECT COALESCE(SUM(amount_units), 0)
                FROM transactions
                WHERE wallet_id = :wid AND type = 'out' AND NOT is_confirmed AND NOT is_deleted AND created_at > NOW() - INTERVAL '1 year'
            """, {'wid': wallet_id}
        ).scalar()
        return current_amount

    def _get_btc_commissions_from_database(self, session):
        all_commissions = session.execute("SELECT key, value FROM settings WHERE key like 'BTC_COMM%'").fetchall()
        commissions = []
        for threshold, commission in all_commissions:
            threshold = float(threshold.split('BTC_COMM_')[1])
            commission = Decimal(commission)
            commissions.append((threshold, commission))
        return sorted(commissions, key=lambda data: data[0], reverse=True)

    def _get_usdt_commissions_from_database(self, session):
        all_commissions = session.execute("SELECT key, value FROM settings WHERE key like 'USDT_COMM%'").fetchall()
        commissions = []
        for threshold, commission in all_commissions:
            threshold = float(threshold.split('USDT_COMM_')[1])
            commission = Decimal(commission)
            commissions.append((threshold, commission))
        return sorted(commissions, key=lambda data: data[0], reverse=True)

    def _get_btc_commission(self, amount, session):
        for threshold, commission in self._get_btc_commissions_from_database(session):
            if amount >= Decimal(str(threshold)):
                return commission

    def _get_usdt_commission(self, amount, session):
        for threshold, commission in self._get_usdt_commissions_from_database(session):
            if amount >= Decimal(str(threshold)):
                return commission

    def _get_commissions_symbol(self, amount, symbol, session):
        if symbol == 'btc':
            base_comm = self._get_btc_commission(amount, session)
            if amount > Decimal('1'):
                coefficient = Decimal(str(math.ceil(amount)))
                return base_comm * coefficient
            else:
                return base_comm
        elif symbol == 'usdt':
            base_comm = self._get_usdt_commission(amount, session)
            if amount > Decimal('10000'):
                coefficient = Decimal(str(math.ceil(float(amount)/float(10000))))
                return base_comm * coefficient
            else:
                return base_comm
        else:
            base_comm = session.execute(
                "SELECT tx_out_commission FROM crypto_settings WHERE symbol = :sym", {"sym": symbol}
            ).scalar()
            if symbol == 'usdt' and amount > Decimal('10000'):
                coefficient = Decimal(str(math.ceil(float(amount)/float(10000))))
                return base_comm * coefficient
            else:
                return base_comm

    def _get_last_withdraw_creation_time(self, wallet_id, session):
        last_creation_time = session.execute(
            """
                SELECT MAX(created_at)
                FROM transactions
                WHERE wallet_id = :wid AND type = 'out' AND NOT is_deleted
            """, {'wid': wallet_id}
        ).scalar()
        return last_creation_time

    def validate_availability_to_withdraw(self, user_id, user, wallet, amount, symbol, address, settings, session):
        if not is_amount_precision_right_for_symbol(symbol, amount):
            raise BadRequest('Wrong amount')

        if amount > wallet['withdrawal_limit']:
            raise BadRequest("Amount is more than limit")

        if user['is_baned']:
            raise BadRequest('user is baned')

        if not self.is_address_valid(symbol, address)['is_valid']:
            raise BadRequest('Address not valid')

        if amount < Decimal(str(settings['min_tx_amount'])):
            raise BadRequest('Wrong amount')

        if symbol == 'btc':
            current_withdraw_amount = self._get_current_withdrawing_amount(wallet['id'], session)

            if current_withdraw_amount:
                raise Conflict('Limit reached')
        else:
            last_withdraw_time = self._get_last_withdraw_creation_time(wallet['id'], session)

            if last_withdraw_time is not None and last_withdraw_time > datetime.utcnow() - timedelta(minutes=10):
                raise Conflict('Limit reached')

    def send_transaction_out(self, symbol, user_id, address, amount, with_proxy, token, session):
        self._validate_shadow_ban(user_id, session)
        user = self.get_user(user_id, session)
        wallet = self.get_wallet(symbol, user_id, session)
        amount = Decimal(str(amount))

        settings = self.get_settings(symbol, session)
        self.validate_availability_to_withdraw(user_id, user, wallet, amount, symbol, address, settings, session)
        commission = self._get_commissions_symbol(amount, symbol, session)

        amount_with_commission = amount + commission

        if wallet['balance'] < amount_with_commission:
            raise BadRequest('not enough funds')

        if with_proxy and symbol == 'btc':
            return
        else:
            q = f"""
                INSERT INTO transactions (wallet_id, type, to_address, amount_units, sky_commission, commission)
                VALUES (:wid, 'out', :address, :amount, :commission, :commission)
            """
            session.execute(q, {'wid': wallet['id'], 'address': address, 'amount': amount, 'commission': commission})
            freeze(user['id'], f'Withdraw to {address}', symbol=symbol, amount=amount_with_commission, session=session)
        return {'success': 'transaction created'}

    def get_last_requisites(self, symbol, user_id, broker_id, currency, session):
        q = """
            SELECT requisite
            FROM (
                SELECT requisite, MAX(d.created_at) created_at
                FROM deal d
                LEFT JOIN lot l ON d.lot_id = l.id
                WHERE d.symbol = :sym AND seller_id = :uid AND broker_id = :bid AND d.currency = :cur
                GROUP BY requisite
            ) t
            ORDER BY created_at DESC
        """
        args = {'sym': symbol, 'uid': user_id, 'bid': broker_id, 'cur': currency}
        data = session.execute(q, args).fetchall()
        return [answ[0] for answ in data if answ[0]]

    def _get_commission(self, t, session):
        return session.execute(f"SELECT commission FROM commissions WHERE type = '{t}'").scalar()

    def get_brokers(self, session, currency=None):
        if currency is None:
            data = session.execute(
                "SELECT id, name FROM broker WHERE NOT is_deleted"
            ).fetchall()
        else:
            data = session.execute(
                """
                    SELECT b.id, b.name
                    FROM broker b
                    JOIN broker_currency bc on b.id = bc.broker_id
                    WHERE NOT b.is_deleted AND currency = :cur
                """, {'cur': currency}
            ).fetchall()
        return [{'id': str(b['id']), 'name': b['name']} for b in data]

    def get_currencies(self, session):
        data = session.execute(
            "SELECT id FROM currency WHERE is_active"
        ).fetchall()
        return [dict(item) for item in data]

    def _is_user_verify(self, user_id):
        with session_scope() as session:
            is_verify = session.execute('SELECT is_verify FROM "user" WHERE id = :uid', {'uid': user_id}).scalar()
        return is_verify

    def _validate_user_spam(self, user_id, lot_id):
        if not self._is_user_verify(user_id):
            with session_scope() as session:
                this_minute_deals_with_current_lot = session.execute(
                    """
                        SELECT count(*)
                        FROM deal d
                        WHERE (buyer_id = :uid OR seller_id = :uid) AND lot_id = :lid AND created_at > now() - INTERVAL '1 minute'
                    """, {'uid': user_id, 'lid': lot_id}
                ).scalar()
            if this_minute_deals_with_current_lot > 0:
                raise BadRequest('limit of this lot exceeded')

    def _validate_shadow_ban(self, user_id, session):
        shadow_ban = session.execute('SELECT shadow_ban FROM "user" WHERE id = :uid', {'uid': user_id}).scalar()
        if shadow_ban:
            raise BadRequest('user is baned')

    def create_new_deal(
            self, symbol, user_id, lot_id,
            rate, requisite, amount_currency,
            amount, session, sale_v2_id=None,
            payment_v2_id=None, deal_type=DealTypes.plain,
            create_notification=True, expand_id=False
    ):
        self._validate_shadow_ban(user_id, session)
        amount_subunit = self.crypto_manager.to_subunit(symbol, amount)
        settings = self.get_crypto_settings(session, symbol)
        commission_seller = amount_subunit * settings['seller_commission']
        commission_buyer = amount_subunit * settings['buyer_commission']
        amount_subunit_freeze = amount_subunit + commission_seller

        lot = self.get_lot(lot_id, session)

        self._validate_user_spam(user_id, lot['id'])

        if lot['symbol'] != symbol:
            raise BadRequest
        if lot['type'] == LOT_TYPE_BUY:
            seller = self.get_user(user_id, session)
            buyer = self.get_user(lot['user_id'], session)
        else:
            seller = self.get_user(lot['user_id'], session)
            buyer = self.get_user(user_id, session)

        self._validate_ban_on_user(user_id, lot['user_id'], session)

        seller_wallet = self.get_wallet(symbol, seller['id'], session)

        if amount_subunit_freeze > self.crypto_manager.to_subunit(symbol, seller_wallet['balance']):
            raise BadRequest('insufficient funds')

        deal_id = generate_deal_id()
        if not requisite:
            requisite = ''
        freeze(seller['id'], msg=f'Deal {deal_id} creation', symbol=symbol, amount_subunits=amount_subunit_freeze,
               session=session)
        q = f"""
            INSERT INTO deal (
                identificator, amount_currency, amount_subunit, amount_subunit_frozen, buyer_id, seller_id, 
                lot_id, rate, requisite, seller_commission_subunits, buyer_commission_subunits, symbol, currency,
                sale_v2_id, payment_v2_id, type
            ) VALUES (
                :did, :amount_cur, :amount_sub, :am_to_freeze, :bid,
                :sid, (SELECT id FROM lot WHERE identificator = :lid), :rate, :requisite,
                :commission_seller, :commission_buyer, :symbol, :cur, :sale_v2_id, :payment_v2_id,
                 :deal_type
            ) RETURNING id
        """
        did = session.execute(
            q,
            {
                'requisite': requisite, 'sale_v2_id': sale_v2_id,
                'payment_v2_id': payment_v2_id, 'deal_type': deal_type,
                'did': deal_id, 'amount_cur': amount_currency, 'amount_sub': amount_subunit,
                'am_to_freeze': amount_subunit_freeze, 'bid': buyer['id'], 'sid': seller['id'], 'lid': lot_id,
                'rate': rate, 'commission_seller': commission_seller, 'commission_buyer': commission_buyer,
                'symbol': symbol, 'cur': lot["currency"]
            }
        ).scalar()
        if create_notification:
            create_deal_notification(lot['user_id'], did, session, n_type='deal')
        return self.get_deal(symbol, deal_id, session=session, expand_id=expand_id)

    def _serialize_deal(self, res, many, expand_id, session, expand_email=False, with_merchant=False):
        if not many:
            res = [res]
        answ = []
        for local_res in res:
            (
                did, identificator, amount_currency, amount_subunit, created_at, end_time, rate, requisite, state,
                buyer_id, seller_id, lot_id, currency, buyer_commission_subunits, seller_commission_subunits,
                referral_commission_buyer_subunits, referral_commission_seller_subunits, symbol, deal_type, address,
                payment_id, sell_id, sale_v2_id, payment_v2_id
            ) = local_res
            d = {
                'identificator': identificator, 'amount_currency': amount_currency, 'end_time': end_time, 'rate': rate,
                'amount': self.crypto_manager.from_subunit(symbol, amount_subunit), 'created': created_at,
                'requisite': requisite, 'state': state,
                'buyer': self.get_user(buyer_id, session, expand_email=expand_email, expand_rating=True),
                'seller': self.get_user(seller_id, session, expand_email=expand_email, expand_rating=True),
                'lot': self.get_lot(lot_id, session), 'currency': currency, 'symbol': symbol,
                'buyer_commission': self.crypto_manager.from_subunit(symbol, buyer_commission_subunits),
                'seller_commission': self.crypto_manager.from_subunit(symbol, seller_commission_subunits),
                'referral_commission_buyer': self.crypto_manager.from_subunit(symbol, referral_commission_buyer_subunits),
                'referral_commission_seller': self.crypto_manager.from_subunit(symbol, referral_commission_seller_subunits),
                'type': deal_type, 'address': address.strip() if address else None, 'payment_id': payment_id,
                'sell_id': sell_id, 'sale_v2_id': sale_v2_id, 'payment_v2_id': payment_v2_id, 'merchant': None
            }
            if expand_id:
                d['id'] = did
            if with_merchant and payment_id:
                merchant_id = get_purchase(user_id=-1, purchase_id=payment_id)['merchant_id']
                d['merchant'] = get_merchant(merchant_id, session)
            answ.append(d)
        return answ if many else answ[0]

    def get_deal(self, symbol, deal_id, expand_id=False, *, session, expand_email=False, with_merchant=False, for_update=False):
        """
        :param expand_id:
        :param symbol:
        :param deal_id: [id]
        :return:
        """
        many = isinstance(deal_id, (tuple, list))
        if many:
            if len(deal_id) == 0:
                return []
            where = 'id IN :did'
            data = {'did': tuple(deal_id)}
        else:
            where = "identificator = :did"
            data = {'did': deal_id}
        q = f"""
            SELECT id, d.identificator, amount_currency, amount_subunit, d.created_at, end_time, d.rate, requisite, state,
                buyer_id, seller_id, (SELECT identificator FROM lot WHERE id = lot_id), currency,
                buyer_commission_subunits, seller_commission_subunits,
                referral_commission_buyer_subunits, referral_commission_seller_subunits, symbol, type, address, 
                payment_id, sell_id, sale_v2_id, payment_v2_id
            FROM deal d
            WHERE {where}
        """
        if for_update:
            q += ' FOR UPDATE SKIP LOCKED'
        res = session.execute(q, data).fetchall() if many else session.execute(q, data).fetchone()
        if res is None:
            raise BadRequest('no such deal')
        return self._serialize_deal(res, many, expand_id, session, expand_email=expand_email, with_merchant=with_merchant)

    def get_deal_mask(self, symbol, deal_id, session):
        payment_id = session.execute(
            'SELECT payment_id FROM deal WHERE identificator = :ident LIMIT 1',
            {'ident': deal_id}
        ).scalar()
        if payment_id:
            mask = get_purchase(user_id=-1, purchase_id=payment_id)['mask']
            return {'mask': mask}
        return {'mask': None}

    def set_deal_mask(self, symbol, deal_id, mask, session):
        payment_id = session.execute(
            'SELECT payment_id FROM deal WHERE identificator = :ident LIMIT 1',
            {'ident': deal_id}
        ).scalar()
        if payment_id:
            update_purchase(user_id=-1, purchase_id=payment_id, data={'mask': mask})
            return {'success': True}
        return {'success': False}

    def get_dispute(self, deal_id, session=None, is_internal_id=True, expand_id=False):
        if not is_internal_id:
            deal_id = self.get_deal('', deal_id, expand_id=True, session=session)['id']
        q = "SELECT id, initiator, opponent, created_at FROM dispute WHERE deal_id = :did"
        disp = session.execute(q, {'did': deal_id}).fetchone()

        if disp is None:
            return {}

        disp_id, initiator_id, opponent_id, created_at = disp
        answ = {
            'initiator': self.get_user(initiator_id, session),
            'opponent': self.get_user(opponent_id, session) if opponent_id else {},
            'created_at': created_at
        }
        if expand_id:
            answ['id'] = disp_id
        return answ

    def create_dispute(self, deal_id, user_id, session):
        is_verify, user_rating = session.execute('SELECT is_verify, rating FROM "user" WHERE id = :uid', {'uid': user_id}).fetchone()
        if not is_verify and user_rating <= 0:
            raise BadRequest
        deal = self.get_deal('', deal_id, expand_id=True, session=session)
        deal_id = deal['id']
        disp = self.get_dispute(deal_id, session, expand_id=True)
        kw = {'uid': user_id, 'did': deal_id, 'disp_id': disp.get('id')}
        if disp:
            if user_id == disp['initiator']['id'] or user_id == disp['opponent'].get('id'):
                raise BadRequest('Dispute already opened')
            session.execute("UPDATE dispute SET opponent = :uid WHERE id = :disp_id", kw)
        else:
            if (
                deal["type"] in (DealTypes.sky_pay, DealTypes.fast, DealTypes.sky_pay_v2)
                and localize_datetime(deal["created"]) + timedelta(minutes=5) > datetime.now(tz=pytz.UTC)
            ):
                raise BadRequest("You can open a dispute only 5 minutes after the deal")

            session.execute("INSERT INTO dispute (deal_id, initiator) VALUES (:did, :uid)", kw)

        buyer_id, seller_id, symbol = session.execute(
            "SELECT buyer_id, seller_id, symbol FROM deal WHERE id = :did",
            {'did': deal_id}
        ).fetchone()

        opponent_id = buyer_id if user_id == seller_id else seller_id
        create_deal_notification(opponent_id, deal_id, session, n_type='dispute')
        return self.get_dispute(deal_id, session)

    def stop_deal(self, symbol, deal_id, session):
        q = f"""
            UPDATE deal SET state = 'deleted', end_time = NOW()
            WHERE identificator = :did
            RETURNING seller_id, amount_subunit_frozen
        """
        seller_id, to_unfreeze = session.execute(q, {'did': deal_id}).fetchone()
        unfreeze(seller_id, f'Stopping deal {deal_id}', symbol=symbol, amount_subunits=to_unfreeze, session=session)

    def _validate_cancel_deal(self, user_id, deal, session):
        if user_id not in (deal['seller']['id'], deal['buyer']['id']):
            raise Forbidden()
        if deal['state'] in STATES[3:]:
            raise BadRequest
        if deal['state'] == STATES[2]:
            dispute = self.get_dispute(deal['identificator'], is_internal_id=False, session=session)
            can_close = all([
                bool(dispute),
                dispute['initiator']['id'] == deal['seller']['id'],
                user_id == deal['buyer']['id']
            ])
            if not can_close:
                raise Forbidden('can not cancel paid deal')
        if deal['state'] == STATES[1]:
            if user_id == deal['seller']['id'] and deal['requisite']:
                raise Forbidden('can not cancel deal with requisite')

    def cancel_deal(self, symbol, deal_id, user_id, session):
        deal = self.get_deal(symbol, deal_id, session=session, for_update=True)
        self._validate_cancel_deal(user_id, deal, session)
        initiator = ['buyer', 'seller'][user_id == deal['seller']['id']]
        q = """
            UPDATE deal SET state = 'deleted', end_time = NOW(), cancel_reason = :initiator
            WHERE identificator = :dident
            RETURNING seller_id, amount_subunit_frozen, id
        """
        seller_id, to_unfreeze, did = session.execute(q, {'dident': deal_id, 'initiator': initiator}).fetchone()
        unfreeze(seller_id, f'Cancel deal {deal_id}', symbol=symbol, amount_subunits=to_unfreeze, session=session)
        session.execute(
            """
                UPDATE dispute
                SET is_closed = TRUE
                WHERE deal_id = :did
            """, {'did': did}
        )
        if deal['type'] not in (DealTypes.sky_sale_v2, DealTypes.sky_pay_v2):
            uid = deal['seller']['id'] if user_id == deal['buyer']['id'] else deal['buyer']['id']
            create_deal_notification(uid, did, session, n_type='cancel_deal')
        if deal['type'] == DealTypes.sky_sale_v2:
            update_sale_v2(user_id=-1, sale_v2_id=deal['sale_v2_id'], data={'status': 0, 'deal': None})
        elif deal['type'] == DealTypes.sky_pay_v2:
            update_payment_v2(user_id=-1, payment_v2_id=deal['payment_v2_id'], data={'status': 0, 'deal': None})
        return {'success': 'deal canceled'}

    def close_deal_admin(self, symbol, deal_id, winner, session):
        deal = self.get_deal_for_update_state(symbol, deal_id, session=session)
        if winner == 'seller':
            amount, seller_id = session.execute(
                """
                    SELECT amount_subunit_frozen, seller_id 
                    FROM deal 
                    WHERE id = :id
                """, {'id': deal['id']}
            ).fetchone()
            unfreeze(amount_subunits=amount, user_id=seller_id, symbol=symbol, msg='Dispute closed', session=session)
            session.execute(
                "UPDATE deal SET state = :state, cancel_reason = 'dispute', end_time = NOW() WHERE id = :id",
                {'state': STATES[-1], 'id': deal['id']}
            )
        elif winner == 'buyer':
            self._process_deal(symbol, deal, is_dispute=True, session=session)
        else:
            raise BadRequest

        session.execute("UPDATE dispute SET is_closed = TRUE WHERE deal_id = :did", {'did': deal['id']})

        for side in ('buyer_id', 'seller_id'):
            uid = deal[side]
            create_closed_dispute_notification(uid, symbol, deal['id'], session, admin=True)

        return {'success': 'deal canceled'}

    def update_deal_req(self, symbol, deal_id, req, user_id, session):
        d = self.get_deal(symbol, deal_id, session=session)
        if user_id not in (d['seller']['id'], d['buyer']['id']):
            raise BadRequest('not a participant')
        q = "UPDATE deal SET requisite = :req WHERE identificator = :id"
        payment_v2 = None
        if d['payment_v2_id'] is not None:
            payment_v2 = get_payment_v2(-1, d['payment_v2_id'])
        if payment_v2:
            update_payment_v2(
                user_id=-1,
                payment_v2_id=payment_v2['id'],
                data={'requisites': req}
            )
        session.execute(q, {'req': req, 'id': deal_id})

    def _process_referral(self, symbol, deal, session):
        buyer_ref = session.execute(
            """
                SELECT referred_from_id
                FROM wallet
                WHERE symbol = :sym AND user_id = :uid
            """, {'sym': symbol, 'uid': deal['buyer_id']}
        ).scalar()
        if buyer_ref:
            ref_commission = deal['buyer_commission'] * self._get_commission('buyer_referral', session)
            self.create_wallet_if_not_exists(symbol, buyer_ref, session)
            nickname = self.get_nickname_by_id(deal['buyer_id'], session)
            if ref_commission:
                create_operation(session, buyer_ref, nickname,
                                 symbol, None, ref_commission, action=Action.referral)
                update_deal_commission(deal['id'], referral_commission_buyer=ref_commission)
                ref_commission = manager.to_subunit(symbol, ref_commission)
                change_balance(buyer_ref, msg=f'Referral deal {deal["identificator"]}', symbol=symbol,
                               amount_subunits=ref_commission, session=session)
                did = session.execute(
                    """
                        UPDATE deal
                        SET referral_commission_buyer_subunits = :sub
                        WHERE identificator = :did
                        RETURNING id
                    """, {'did': deal['identificator'], 'sub': ref_commission}
                ).fetchone()[0]
                session.execute(
                    """
                        UPDATE wallet
                        SET earned_from_ref = earned_from_ref + :subunits
                        WHERE user_id = :uid AND symbol = :symbol
                    """, {'subunits': ref_commission, 'uid': buyer_ref, 'symbol': symbol}
                )
                session.execute(
                    f"""
                        INSERT INTO notification (user_id, symbol, type, deal_id)
                        VALUES (
                            :buyer_ref, :sym, 'income_referral', :did
                        )
                    """, {'buyer_ref': buyer_ref, 'sym': symbol, 'did': did}
                )

    def get_merchant_commission(self, merchant_id, session):
        merchant = session.execute(
            'SELECT commission FROM merchant WHERE user_id = :mid',
            {'mid': merchant_id}
        ).fetchone()
        if merchant:
            return merchant[0]

    def get_balance(self, user_id, session) -> Decimal:
        return session.execute(
            "SELECT balance FROM wallet WHERE user_id = :uid",
            {'uid': user_id}
        ).scalar()

    def get_seller_commission(self, deal_rate, deal_symbol, amount_currency, currency, session):
        current_rate = self.get_rate(deal_symbol, currency, session)
        diff = abs(1 - deal_rate / current_rate)
        return round(amount_currency * diff, 2)

    def get_buyer_commission(self, deal_rate, deal_symbol, amount_currency, currency, session):
        current_rate = self.get_rate(deal_symbol, currency, session)
        diff = round(abs(1 - current_rate / deal_rate), 2)
        return round(amount_currency * diff, 2)

    def get_buyer_crypto_commission(self, amount):
        diff = Decimal('1')/Decimal('0.97')
        commission = round(amount * diff - amount, 6)
        return commission

    def _process_earnings(self, session, deal, amount_frozen):
        to_balance = deal['amount'] - deal['buyer_commission']
        msg = f'Closing deal {deal["identificator"]}'

        symbol = deal['symbol']
        seller_id = deal['seller_id']
        buyer_id = deal['buyer_id']

        print('change frozen')
        change_frozen(user_id=seller_id, msg=msg, symbol=symbol, amount_subunits=-amount_frozen, session=session)
        if deal['type'] != DealTypes.sky_sale_v2:
            create_operation(
                session, seller_id, deal['identificator'], symbol, deal['currency'],
                -manager.from_subunit(symbol, amount_frozen), action=Action.deal,
                amount_currency=deal['amount_currency']
            )

        merchant_commission = 0

        if deal['type'] == DealTypes.plain:
            print('change balance')
            change_balance(user_id=buyer_id, msg=msg, symbol=symbol, amount=to_balance, session=session)
            print('create operation')
            create_operation(
                session, buyer_id, deal['identificator'],
                symbol, deal['currency'], to_balance,
                action=Action.deal, amount_currency=deal['amount_currency']
            )

        elif deal['type'] == DealTypes.fast:
            wallet_id = self._get_wallet_id(session, buyer_id, symbol)
            settings = self.get_settings(symbol, session)
            comm = Decimal(str(settings['commission']))
            change_frozen(user_id=buyer_id, msg=msg, symbol=symbol, amount=to_balance, session=session)
            self._create_transaction(session, wallet_id=wallet_id, address=deal['address'], amount_units=to_balance - comm)

        elif deal['type'] == DealTypes.sky_pay:
            payment = get_purchase(buyer_id, deal['payment_id'])
            msg = f'SKY PAY: {msg}, {deal["payment_id"]}'
            receiver_id = payment['merchant_id']
            service_commission = self.get_merchant_commission(receiver_id, session)
            seller_commission = self.get_seller_commission(deal['rate'], deal['symbol'], deal['amount_currency'], deal['currency'], session)
            comm = self._get_commissions_symbol(to_balance, symbol, session) if payment['address'] or not service_commission else service_commission * to_balance
            merchant_commission = comm

            tx_hash = None

            commission_currency = 0 if payment['address'] or not service_commission else service_commission * Decimal(str(payment['amount']))

            if payment['address']:
                if symbol == 'btc':
                    to_send = round(to_balance - comm, manager.currencies['btc'].DECIMALS)
                    if not environ.get('TEST'):
                        tx_hash = manager.currencies['btc'].create_tx_out(payment['address'], to_send)
                else:
                    wallet_id = self.get_wallet(symbol, buyer_id, session)['id']
                    change_frozen(user_id=buyer_id, msg=msg, symbol=symbol,
                                  amount=to_balance, session=session)
                    self._create_transaction(session, wallet_id=wallet_id, address=payment['address'],
                                             amount_units=to_balance - comm)
            else:
                change_balance(user_id=receiver_id, msg=msg, symbol=symbol, amount=to_balance - comm, session=session)

            create_operation(session, receiver_id, deal['payment_id'], symbol, deal['currency'], to_balance - comm, action=Action.sky_pay,
                             operation_type=OperationTypes.public_api, commission=comm,
                             commission_currency=commission_currency,
                             amount_currency=payment['amount'] if payment['is_currency_amount'] else deal['amount_currency'],
                             label=payment['label'], trader_commission=seller_commission)
            complete_purchase(receiver_id, deal['payment_id'], tx_hash, to_balance - comm, deal['rate'])
            try:
                if 'noemail.fkfl' not in deal['buyer']['email']:
                    broker = self._get_broker_name_by_id(deal['broker_id'], session)
                    self.send_receipt(session, buyer_id, deal, to_balance, payment['label'], receiver_id, broker)
            except Exception as e:
                logger.warning(e)
        elif deal['type'] == DealTypes.sky_pay_v2:
            payment = get_payment_v2(buyer_id, deal['payment_v2_id'])
            msg = f'SKY PAY V2: {msg}, {deal["payment_v2_id"]}'
            receiver_id = payment['merchant_id']
            service_commission = self.get_merchant_commission(receiver_id, session)
            seller_commission = self.get_seller_commission(deal['rate'], deal['symbol'], deal['amount_currency'], deal['currency'], session)
            comm = service_commission * to_balance

            final_to_balance = to_balance - comm
            change_balance(user_id=receiver_id, msg=msg, symbol=symbol, amount=final_to_balance, session=session)

            commission_currency = service_commission * Decimal(str(payment['amount']))

            create_operation(session, receiver_id, deal['payment_v2_id'], symbol, deal['currency'], final_to_balance, action=Action.sky_pay_v2,
                             operation_type=OperationTypes.public_api, commission=comm,
                             commission_currency=commission_currency,
                             amount_currency=payment['amount'] if payment['is_currency_amount'] else deal['amount_currency'],
                             label=payment['label'], trader_commission=seller_commission)
            complete_payment_v2(receiver_id, deal['payment_v2_id'], final_to_balance)

        elif deal['type'] == DealTypes.sky_sale:
            sell = get_sell(buyer_id, deal['sell_id'])
            receiver_id = sell['merchant_id']
            msg = f'SKY SELL: {msg}, {deal["sell_id"]}'
            change_balance(user_id=buyer_id, msg=msg, symbol=symbol, amount=to_balance, session=session)
            create_operation(session, buyer_id, deal['identificator'], symbol, deal['currency'], to_balance, action=Action.deal)
            balance = self.get_balance(seller_id, session=session)
            if balance > 0:
                change_balance(user_id=seller_id, msg=msg, symbol=symbol, amount_subunits=-balance, session=session)
            complete_sell(receiver_id, deal['sell_id'], session)
        elif deal['type'] == DealTypes.sky_sale_v2:
            msg = f'SKY SALE_V2: {msg}, {deal["sale_v2_id"]}'
            change_balance(user_id=buyer_id, msg=msg, symbol=symbol, amount=to_balance, session=session)
            create_operation(session, buyer_id, deal['identificator'], symbol, deal['currency'], to_balance, action=Action.deal)
            complete_sale_v2(user_id=seller_id, sale_v2_id=deal['sale_v2_id'], session=session)
            service_commission = get_merchant_commission(seller_id, session)
            buyer_commission = self.get_buyer_commission(deal['rate'], deal['symbol'], deal['amount_currency'], deal['currency'], session)
            print(f'buyer_commission = {buyer_commission}')
            commission_currency = service_commission * Decimal(str(deal['amount_currency']))
            comm = service_commission * to_balance
            merchant_commission = comm

            try:
                change_balance(user_id=seller_id, msg=msg, symbol=symbol, amount=-comm, session=session)
            except Exception:
                comm = 0
                commission_currency = 0

            full_commission = (
                    comm +
                    self.crypto_manager.from_subunit(
                        deal['symbol'],
                        self.get_buyer_crypto_commission(deal['amount'])
                    ) +
                    deal['seller_commission']
            )

            create_operation(
                session, seller_id, deal['sale_v2_id'], symbol, deal['currency'],
                amount=-to_balance-comm, action=Action.sky_sale_v2, amount_currency=deal['amount_currency'],
                operation_type=OperationTypes.public_api,
                commission=full_commission, commission_currency=commission_currency,
                trader_commission=buyer_commission
            )

        print('creating deal commission')
        create_deal_commission(
            deal_id=deal['id'], merchant_commission=merchant_commission, session=session,
            symbol=deal['symbol'], buyer_commission=deal['buyer_commission'],
            seller_commission=deal['seller_commission']
        )
        print('deal commission created')

    def send_receipt(self, session, user_id, deal, received, label, merchant_id, broker):
        recipient = self.get_user(user_id, session)['email']
        website, url = session.execute(
            "SELECT website, image_url FROM merchant WHERE user_id = :uid",
            {'uid': merchant_id}
        ).fetchone()
        receipt(
            recipient=recipient,
            paid=deal['amount_currency'],
            received=received,
            symbol=deal['symbol'].upper(),
            deal_id=deal['identificator'],
            closed_at=(datetime.now(timezone.utc) + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M"),
            label=label,
            website=website,
            url=url,
            broker=broker
        )

    def _work_deal(self, deal, symbol, session, q):
        amount_frozen, did = session.execute(q, {'did': deal['identificator']}).fetchone()

        print('process earnings')
        self._process_earnings(session, deal, amount_frozen)
        print('create_deal_notification')
        create_deal_notification(deal['buyer_id'], did, session, n_type='deal')
        print('_process_referral')
        self._process_referral(symbol, deal, session)
        print('updating disputes')
        session.execute("UPDATE dispute SET is_closed = TRUE WHERE deal_id = :did", {'did': did})

    def _process_deal(self, symbol, deal, is_dispute=False, *, session, allow_process_different_state=False):
        if not is_dispute and not allow_process_different_state:
            add_params = "AND state = 'paid'"
        else:
            add_params = ''
        q = f"""
            UPDATE deal
            SET state = 'closed', end_time = NOW()
            WHERE identificator = :did {add_params}
            RETURNING amount_subunit_frozen, id
        """
        print("status updated")
        self._work_deal(deal, symbol, session, q)

    def get_deal_for_update_state(self, symbol, deal_id, session):
        q = """
            SELECT id, identificator, seller_id, buyer_id, address, type, symbol, rate,
                    amount_subunit as amount, amount_currency, currency,
                    (SELECT user_id FROM lot WHERE id = lot_id) as lot_user_id,
                    (SELECT broker_id FROM lot WHERE id = lot_id) as broker_id,
                    (SELECT type FROM lot WHERE id = lot_id) as lot_type,
                    requisite, state, payment_id, sell_id, sale_v2_id, payment_v2_id,
                    buyer_commission_subunits as buyer_commission, 
                    seller_commission_subunits as seller_commission
            FROM deal
            WHERE identificator = :did
            LIMIT 1
            FOR UPDATE
        """
        deal = dict(session.execute(q, {'did': deal_id}).fetchone())
        deal['buyer_commission'] = self.crypto_manager.from_subunit(symbol, deal['buyer_commission'])
        deal['seller_commission'] = self.crypto_manager.from_subunit(symbol, deal['seller_commission'])
        deal['amount'] = self.crypto_manager.from_subunit(symbol, deal['amount'])
        if deal['address']:
            deal['address'] = deal['address'].strip()
        return deal

    def update_deal_state(self, symbol, deal_id, user_id, session):
        deal = self.get_deal_for_update_state(symbol, deal_id, session=session)
        if deal['state'] == 'proposed':
            if user_id == deal['lot_user_id']:
                q = f"""
                    UPDATE deal 
                    SET state = 'confirmed', confirmed_at = NOW() 
                    WHERE identificator = '{deal_id}' AND state = 'proposed' 
                    RETURNING id
                """
                did = session.execute(q).scalar()
                if deal['payment_v2_id'] is None:
                    uid = deal['seller_id'] if deal['lot_type'] == LOT_TYPE_BUY else deal['buyer_id']
                    create_deal_notification(uid, did, session, n_type='deal')
                return {'success': 'new deal status = confirmed'}
        elif deal['state'] == 'confirmed':
            if deal['buyer_id'] == user_id and deal['requisite']:
                if deal['sale_v2_id'] is not None:
                    self._process_deal(symbol, deal, session=session, allow_process_different_state=True)
                    return {'success': 'deal processed'}
                q = f"UPDATE deal SET state = 'paid' WHERE identificator = '{deal_id}' AND state = 'confirmed' RETURNING id"
                did = session.execute(q).scalar()
                create_deal_notification(deal['seller_id'], did, session, n_type='deal')
                return {'success': 'new deal status = paid'}
        elif deal['state'] == 'paid':
            if deal['seller_id'] == user_id:
                self._process_deal(symbol, deal, session=session)
                return {'success': 'deal processed'}
        raise BadRequest('wrong status')

    def confirm_declined_fd_deal(self, symbol, deal_id, user_id, session):
        deal = self.get_deal_for_update_state(symbol, deal_id, session=session)
        deals_active_or_closed_exists = session.execute(
            """
                SELECT EXISTS(
                    SELECT 1 FROM deal 
                    WHERE payment_id = :pid AND state <> 'deleted'
                )
            """, {'pid': deal['payment_id']}
        ).scalar()

        if (
            deal['state'] == 'deleted' and
            deal['type'] in (DealTypes.plain, DealTypes.sky_pay) and
            deal['requisite'] and
                (
                    deal['seller_id'] == user_id or
                    self.is_user_have_rights(user_id, rights='low', session=session)
                ) and
            not deals_active_or_closed_exists
        ):
            amount_frozen, seller = session.execute(
                """
                    SELECT amount_subunit_frozen, seller_id
                    FROM deal
                    WHERE id = :did
                """, {'did': deal['id']}
            ).fetchone()
            msg = f'Recreating deal, {deal["identificator"]}'
            if deal.get('payment_id'):
                msg += f', {deal["payment_id"]}'
            freeze(seller, msg=msg, symbol=symbol, amount_subunits=amount_frozen, session=session)
            self._process_deal(symbol, deal, session=session, allow_process_different_state=True)
            return {'success': 'deal processed'}
        raise BadRequest('error while confirm deal')

    def confirm_deal_without_agreement(self, symbol, deal_id, user_id, session):
        deal = self.get_deal_for_update_state(symbol, deal_id, session=session)
        nickname = self.get_nickname_by_id(deal['buyer_id'], session)
        if deal['state'] == 'confirmed' and deal['seller_id'] == user_id and (deal['payment_id'] or deal['payment_v2_id']):
            self._process_deal(symbol, deal, session=session, allow_process_different_state=True)
            return {'success': 'deal processed'}
        else:
            raise BadRequest

    def _is_like_exists(self, to_user, deal_id, session):
        q = f"""
            SELECT EXISTS(SELECT 1 FROM userrate WHERE to_user_id = {to_user} AND deal_id = {deal_id})
        """
        return session.execute(q).fetchone()[0]

    def update_user_rate(self, from_user, to_user, method, deal_id, session):
        deal_id = session.execute(f"SELECT id FROM deal WHERE identificator = '{deal_id}'").fetchone()[0]
        if deal_id is None or self._is_like_exists(to_user, deal_id, session):
            raise BadRequest('rate already exists')
        q = f"""
            INSERT INTO userrate (from_user_id, to_user_id, action, deal_id)
            VALUES ({from_user}, {to_user}, '{method}', {deal_id})
        """
        session.execute(q)

    def _get_user_transactions_report(self, symbol, user_id, session):
        q = f"""
            SELECT type, amount_units, created_at, processed_at, to_address
            FROM transactions
            LEFT JOIN wallet w ON transactions.wallet_id = w.id
            WHERE symbol = '{symbol}' AND user_id = {user_id}
            ORDER BY transactions.id
        """
        data = []
        print('transactions')
        for t, amount, created, processed, address in session.execute(q).fetchall():
            d = {
                'type': t,
                'amount': amount,
                'symbol': symbol.upper(),
                'created': created,
                'processed': processed,
                'receiver': address
            }
            data.append(d)
        return data

    def _get_user_promocodes_report(self, symbol, user_id, session):
        q = f"""
            SELECT p.code, p.amount, count(pa.promocode_id), count, is_deleted, p.created_at
            FROM promocodes p
            LEFT JOIN promocodeactivations pa ON p.id = pa.promocode_id
            LEFT JOIN wallet w ON p.wallet_id = w.id
            WHERE w.user_id = {user_id} AND w.symbol = '{symbol}'
            GROUP BY p.id
            ORDER BY p.id
        """
        data = []
        print('promocodes')
        for code, amount, activations, count, is_deleted, created_at in session.execute(q).fetchall():
            if is_deleted:
                status = 'deleted'
            elif activations < count:
                status = 'active'
            else:
                status = 'done'
            d = {
                'code': code,
                'amount': self.crypto_manager.from_subunit(symbol, amount),
                'count': count,
                'activations': activations,
                'status': status,
                'symbol': symbol.upper(),
                'created': created_at
            }
            data.append(d)
        return data

    def _get_user_activated_promocodes_report(self, symbol, user_id, session):
        q = f"""
            SELECT p.code, p.amount, pa.created_at
            FROM promocodes p
            LEFT JOIN promocodeactivations pa ON p.id = pa.promocode_id
            LEFT JOIN wallet w ON pa.wallet_id = w.id
            WHERE w.user_id = {user_id} AND w.symbol = '{symbol}'
            ORDER BY pa.created_at
        """
        data = []
        print('activations')
        for code, amount, created_at in session.execute(q).fetchall():
            d = {
                'code': code,
                'amount': self.crypto_manager.from_subunit(symbol, amount),
                'symbol': symbol.upper(),
                'created': created_at
            }
            data.append(d)
        return data

    def _get_user_deals_report(self, symbol, user_id, session):
        q = """
            SELECT d.identificator as id, d.amount_currency, d.end_time, d.rate, d.amount_subunit, d.created_at as created, 
                d.confirmed_at, d.requisite, d.state,d.buyer_commission_subunits, d.seller_commission_subunits,
                d.referral_commission_buyer_subunits, d.referral_commission_seller_subunits, d.symbol, 
                l.type, d.address, d.payment_id, d.sell_id, d.sale_v2_id,buyer_user.nickname as buyer,
                seller_user.nickname as seller,l.currency as currency, l.identificator as lot
            FROM deal d
            INNER JOIN "user" buyer_user ON d.buyer_id = buyer_user.id
            INNER JOIN "user" seller_user ON d.seller_id = seller_user.id
            INNER JOIN lot l ON l.id = d.lot_id
            WHERE :uid IN (buyer_id, seller_id) AND d.symbol = :sym
            ORDER BY d.id
        """
        data = []
        res = session.execute(q, {'uid': user_id, 'sym': symbol})

        keys = res.keys()
        raw_deals = res.fetchall()
        deals = [dict(zip(keys, raw_deal)) for raw_deal in raw_deals]

        for deal in deals:
            symbol = deal["symbol"]
            deal["amount"] = manager.from_subunit(symbol, deal["amount_subunit"])
            deal["buyer_commission"] = manager.from_subunit(symbol, deal["buyer_commission_subunits"])
            deal["seller_commission"] = manager.from_subunit(symbol, deal["seller_commission_subunits"])
            deal["referral_commission_buyer"] = manager.from_subunit(
                symbol, deal["referral_commission_buyer_subunits"]
            )
            deal["referral_commission_seller"] = manager.from_subunit(
                symbol, deal["referral_commission_seller_subunits"]
            )

            del deal["amount_subunit"]
            del deal["buyer_commission_subunits"]
            del deal["seller_commission_subunits"]
            del deal["referral_commission_buyer_subunits"]
            del deal["referral_commission_seller_subunits"]

            data.append(deal)
        return data

    def _get_user_lots_report(self, symbol, user_id, session):
        q = f"""
            SELECT identificator, type, broker_id, rate, limit_from, limit_to, 
                currency, is_active, is_deleted, created_at
            FROM lot l
            WHERE user_id = {user_id} AND symbol = '{symbol}'
            ORDER BY l.id
        """
        data = []
        print('lots')
        res = session.execute(q).fetchall()
        for identificator, t, broker_id, rate, limit_from, limit_to, currency, is_active, is_deleted, created_at in res:
            status = 'deleted' if is_deleted else 'active' if is_active else 'inactive'
            d = {
                'id': identificator,
                'type': t,
                'broker': self._get_broker_name_by_id(broker_id, session),
                'rate': rate,
                'limits': f'{limit_from}-{limit_to}',
                'currency': currency.upper(),
                'status': status,
                'created': created_at
            }
            data.append(d)
        return data

    def get_reports(self, symbol, user_id, session):
        data = {
            'promocodes': self._get_user_promocodes_report(symbol, user_id, session),
            'activated_promocodes': self._get_user_activated_promocodes_report(symbol, user_id, session),
            'transactions': self._get_user_transactions_report(symbol, user_id, session),
            'deals': self._get_user_deals_report(symbol, user_id, session),
            'lots': self._get_user_lots_report(symbol, user_id, session)
        }
        return data

    def _get_users_report(self, symbol, session):
        q = f"""
            SELECT telegram_id, lang, created_at, currency, nickname, is_deleted, is_baned, is_verify
            FROM "user"
        """
        data = []
        for (
                telegram_id, lang, created_at, currency, nickname,
                is_deleted, is_baned, is_verify
        ) in session.execute(q).fetchall():
            d = {
                'telegram_id': telegram_id,
                'lang': lang,
                'created': created_at,
                'currency': currency,
                'nickname': nickname,
                'is_deleted': is_deleted,
                'is_baned': is_baned,
                'is_verify': is_verify
            }
            data.append(d)
        return data

    def _get_user_id_nickname_mapping(self, session):
        return dict(session.execute('SELECT id, nickname FROM "user"').fetchall())

    def _get_lot_id_identificator_mapping(self, session):
        return dict(session.execute('SELECT id, identificator FROM lot').fetchall())

    def _get_deals_report(self, symbol, date_condition, session):
        state_names = {
            'proposed': 'предложена',
            'confirmed': 'подтверждена',
            'paid': 'оплачена',
            'closed': 'закрыта',
            'deleted': 'удалена'
        }
        date_condition = date_condition.replace('created_at', 'd.created_at')
        q = f"""
            SELECT d.identificator, lot_id, amount_currency, currency, d.created_at, state, end_time, 
                buyer_id, seller_id, amount_subunit,
                buyer_commission_subunits + seller_commission_subunits - referral_commission_seller_subunits - referral_commission_buyer_subunits
            FROM deal d
            WHERE symbol = :symbol {date_condition}
            ORDER BY d.id
        """
        deals = session.execute(q, {'symbol': symbol}).fetchall()
        user_id_nickname = self._get_user_id_nickname_mapping(session)
        lot_id_idents = self._get_lot_id_identificator_mapping(session)
        res = []
        for deal, lot, amount_currency, currency, created, state, end_time, buyer, seller, amount_subunit, income in deals:
            d = {
                'id': deal,
                'lot': lot_id_idents[lot],
                'amount': f'{amount_currency} {currency.upper()}',
                'created': created,
                'end': end_time,
                'status': state_names[state],
                'buyer': user_id_nickname[buyer],
                'seller': user_id_nickname[seller],
                'income': f'{manager.from_subunit(symbol, income)} {symbol.upper()}',
                'crypto': f'{manager.from_subunit(symbol, amount_subunit)} {symbol.upper()}'
            }
            res.append(d)
        return res

    def _get_promocodes_report(self, symbol, date_condition, session):
        date_condition = date_condition.replace('created_at', 'p.created_at')
        q = f"""
            SELECT nickname, p.created_at, COUNT(p2.promocode_id), count, p.code, p.is_deleted, amount
            FROM promocodes p
            JOIN promocodeactivations p2 on p.id = p2.promocode_id
            JOIN wallet w on p.wallet_id = w.id
            JOIN "user" u on w.user_id = u.id
            WHERE symbol = :sym {date_condition}
            GROUP BY u.id, p.id
            ORDER BY p.id DESC
        """
        res = []
        for nickname, created, activations, count, code, is_deleted, amount in session.execute(q, {'sym': symbol}).fetchall():
            d = {
                'user': nickname,
                'code': code,
                'created': created,
                'deleted': is_deleted,
                'count': count,
                'activations': activations,
                'amount': f'{manager.from_subunit(symbol, amount)} {symbol.upper()}'
            }
            res.append(d)
        return res

    def _get_income_report(self, symbol, date_condition, session, year, month):
        print('income')
        txs = session.execute(
            f"""
                SELECT date_trunc('day', created_at + INTERVAL '3 hours') as created_at, sum(commission) as income
                FROM transactions
                JOIN wallet w on transactions.wallet_id = w.id
                WHERE symbol = :symbol {date_condition}
                GROUP BY date_trunc('day', created_at + INTERVAL '3 hours')
                ORDER BY date_trunc('day', created_at + INTERVAL '3 hours')
            """, {'symbol': symbol}
        ).fetchall()
        deals = session.execute(
            f"""
                SELECT date_trunc('day', created_at) as created_at, 
                    sum(buyer_commission) + sum(seller_commission) - 
                        sum(referral_commission_buyer) - sum(referral_commission_seller) as income
                FROM deal_commissions
                WHERE symbol = :symbol {date_condition}
                GROUP BY date_trunc('day', created_at)
                ORDER BY date_trunc('day', created_at)
            """, {'symbol': symbol}
        ).fetchall()
        merchants = session.execute(
            f"""
                SELECT date_trunc('day', created_at) as created_at, 
                    sum(merchant_commission) as income
                FROM deal_commissions
                WHERE symbol = :symbol {date_condition}
                GROUP BY date_trunc('day', created_at)
                ORDER BY date_trunc('day', created_at)
            """, {'symbol': symbol}
        ).fetchall()
        res = []
        for day in date_iter(year, month):
            tx_day_data = find_object_by_datetime(txs, day)
            deal_day_data = find_object_by_datetime(deals, day)
            merchant_day_data = find_object_by_datetime(merchants, day)
            d = {
                'date': day,
                'transactions_income': tx_day_data['income'] if tx_day_data else 0,
                'deals_income': deal_day_data['income'] if deal_day_data else 0,
                'merchants_income':  merchant_day_data['income'] if merchant_day_data else 0,
                'total_income': 0
            }
            d['total_income'] = d['transactions_income'] + d['deals_income'] + d['merchants_income']
            res.append(d)
        return res

    def _get_merchants_report(self, symbol, date_condition, session):
        merchants = session.execute(
            f"""
                SELECT date_trunc('day', created_at), 
                    sum(merchant_commission)
                FROM deal_commissions
                WHERE symbol = :symbol {date_condition}
                GROUP BY date_trunc('day', created_at)
                ORDER BY date_trunc('day', created_at)
            """, {'symbol': symbol}
        ).fetchall()
        res = []
        for merchant_at, merchants_income in merchants:
            d = {
                'date': merchant_at,
                'merchants_income': merchants_income,
            }
            res.append(d)
        return res

    def _get_transactions_report(self, symbol, date_condition, session):
        res = session.execute(
            f"""
                SELECT type, to_address, commission, tx_hash, created_at, processed_at, amount_units, is_confirmed, is_deleted
                FROM transactions t
                JOIN wallet w on t.wallet_id = w.id
                WHERE symbol = :symbol {date_condition}
                ORDER BY t.id
            """, {'symbol': symbol}
        ).fetchall()
        answ = []
        for t, to_address, commission, tx_hash, created_at, processed_at, amount_units, is_confirmed, is_deleted in res:
            d = {
                'type': t,
                'to_address': to_address,
                'commission': commission,
                'tx_hash': tx_hash,
                'created_at': created_at,
                'processed_at': processed_at,
                'amount': amount_units,
                'is_confirmed': is_confirmed,
                'is_deleted': is_deleted
            }
            answ.append(d)
        return answ

    def _get_lots_report(self, symbol, date_condition, session):
        date_condition = date_condition.replace('created_at', 'lot.created_at')
        q = f"""
            SELECT identificator, name, rate, nickname, lot.created_at, is_active, coefficient
            FROM lot
            JOIN "user" u ON lot.user_id = u.id
            JOIN broker b ON lot.broker_id = b.id
            WHERE symbol = :sym {date_condition}
            ORDER BY lot.id DESC
        """
        res = []
        for identificator, broker, rate, nickname, created_at, is_active, coefficient in session.execute(q, {'sym': symbol}).fetchall():
            d = {
                'id': identificator,
                'broker': broker,
                'rate': rate,
                'user': nickname,
                'created': created_at,
                'active': is_active,
                'coefficient': coefficient
            }
            res.append(d)
        return res

    def _get_exchange_report(self, symbol, date_condition, session):
        date_condition = date_condition.replace('created_at', 'e.created_at')
        q = f"""
            SELECT e.id as id, e.created_at as created_at, nickname, from_symbol, to_symbol, rate, amount_sent, amount_received, commission
            FROM exchanges e
            JOIN "user" u ON e.user_id = u.id
            WHERE to_symbol = :sym {date_condition}
            ORDER BY e.created_at DESC
        """
        res = []
        for eid, created_at, nickname, from_symbol, to_symbol, rate, amount_sent, amount_received, commission in session.execute(q, {'sym': symbol}).fetchall():
            d = {
                'id': eid,
                'created_at': created_at,
                'nickname': nickname,
                'from_symbol': from_symbol,
                'to_symbol': to_symbol,
                'rate': rate,
                'amount_sent': amount_sent,
                'amount_received': amount_received,
                'commission': commission
            }
            res.append(d)
        return res

    def _get_users_report(self, symbol, date_condition, session):
        q = f"""
            SELECT nickname, lang, telegram_id, created_at, is_deleted, is_baned, is_verify, rating
            FROM "user"
            WHERE TRUE {date_condition}
            ORDER BY id DESC
        """
        res = []
        for nickname, lang, telegram_id, created_at, is_deleted, is_baned, is_verify, rating in session.execute(q).fetchall():
            d = {
                'nickname': nickname,
                'lang': lang,
                'telegram_id': telegram_id,
                'deleted': is_deleted,
                'baned': is_baned,
                'verify': is_verify,
                'rating': rating
            }
            res.append(d)
        return res

    def _get_control_report(self, symbol, date_condition, session):
        q = f"""
            SELECT identificator as id,
               (SELECT nickname FROM "user" WHERE id = d.buyer_id) as buyer,
               (SELECT email FROM "user" WHERE id = d.buyer_id) as buyer_email,
               (SELECT nickname FROM "user" WHERE id = d.seller_id) as seller,
               state, requisite, created_at, end_time, amount_currency, payment_id, sell_id, ip
            FROM deal d
            WHERE symbol = :sym {date_condition}
            ORDER BY created_at;
        """
        data = session.execute(q, {'sym': symbol}).fetchall()
        return [dict(item) for item in data]

    def _get_revenue_and_deals_by_campaign(self, campaign_id, session):
        q = """
            SELECT COALESCE(SUM(d.amount_currency), 0), COUNT(d)
            FROM user_campaign uc
            JOIN "user" u on uc.user_id = u.id
            JOIN deal d on u.id = d.buyer_id or u.id = d.seller_id
            WHERE campaign_id = :cid AND state = 'closed'
        """
        return session.execute(q, {'cid': campaign_id}).fetchone()

    def _get_campaigns_report(self, symbol, session):
        q = f"""
            SELECT COUNT(cu.campaign_id), name, c.id
            FROM campaign c
            LEFT JOIN user_campaign cu ON c.id = cu.campaign_id
            GROUP BY name, c.id
            ORDER BY name DESC
        """
        res = []
        for registrations, name, campaign_id in session.execute(q).fetchall():
            d = self._serialize_campaign(campaign_id, name, registrations, include_links=False)
            d['deals_revenue'], d['deals'] = self._get_revenue_and_deals_by_campaign(campaign_id, session)
            res.append(d)
        return res

    def _serialize_campaign(self, campaign_id, name, registrations=0, include_links=True):
        data = {
            'id': campaign_id,
            'name': name,
            'registrations': registrations
        }
        if include_links:
            data['links'] = []
            prefixes = {
                'eth': 't.me/sky_eth_bot?start=c-',
                'btc': 't.me/sky_btc_bot?start=c-',
                'web': 'https://skycrypto.net?cmp='
            }
            for symbol, prefix in prefixes.items():
                data['links'].append(prefix + campaign_id)
        return data

    def create_new_campaign(self, name, session):
        campaign_id = generate_campaign_id()
        session.execute('INSERT INTO campaign (id, name) VALUES (:id, :name)', {'id': campaign_id, 'name': name})
        return self._serialize_campaign(campaign_id, name)

    def withdraw_from_payments_node(self, symbol, address, amount):
        return {'link': manager.get_link(symbol, manager.currencies[symbol].create_tx_out_payments(address, amount))}

    def get_all_reports(self, symbol, t, session, from_date=None, to_date=None):
        print(t)
        method = getattr(self, f'_get_{t}_report')
        kw = {'session': session}
        if 'date_condition' in method.__code__.co_varnames and isinstance(from_date, int) and isinstance(to_date, int):
            kw['date_condition'] = f' AND created_at BETWEEN to_timestamp({from_date}) AND to_timestamp({to_date})'
        if 'year' in method.__code__.co_varnames and 'month' in method.__code__.co_varnames and isinstance(from_date, int):
            date = datetime.fromtimestamp(from_date)
            kw['year'] = date.year
            kw['month'] = date.month
        return method(symbol, **kw)

    def upload_media(self, symbol, user_id, file, session, content_type=None):
        url = upload_file_to_s3(file, content_type)
        mid = session.execute(
            "INSERT INTO media (url, loaded_by_id) VALUES (:url, :uid) RETURNING id", {'url': url, 'uid': user_id}
        ).fetchone()[0]
        return {'id': mid}

    def update_last_action_time(self, user_id=None, telegram_id=None):
        with session_scope() as session:
            if user_id is not None:
                last_action = LAST_USER_ACTION_TIME.get(user_id)
                if not last_action or last_action < datetime.now(timezone.utc) - timedelta(minutes=1):
                    session.execute(
                        'UPDATE "user" SET last_action = NOW() WHERE id = :uid',
                        {'uid': user_id}
                    )
                    LAST_USER_ACTION_TIME[user_id] = datetime.now(timezone.utc)
            elif telegram_id is not None:
                session.execute(
                    'UPDATE "user" SET last_action = NOW() WHERE telegram_id = :tid',
                    {'tid': telegram_id}
                )
            else:
                raise ValueError('telegram_id and user_id are none')


dh = DataHandler()
