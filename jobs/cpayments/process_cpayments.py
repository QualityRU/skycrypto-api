from datetime import datetime, timezone, timedelta
from decimal import Decimal

from crypto.manager import manager
from system.constants import Action, OperationTypes
from system.funds_changer import change_balance
from utils.db_sessions import session_scope
from utils.utils import get_cpayments_to_process, update_cpayment, get_merchant, create_operation

COMMISSIONS = {
    'btc': Decimal('0.000004'),
    'eth': Decimal('0.0007'),
    'usdt': Decimal('1')
}

COMMISSION = Decimal('0.005')
HOURS_TO_PROCESS = 2


def process_cpayments_v2():
    cpaments_to_process = get_cpayments_to_process()
    for cpayment in cpaments_to_process:
        symbol = cpayment['symbol']
        merchant_id = cpayment['merchant_id']
        amount = Decimal(str(cpayment['amount']))
        with session_scope() as session:
            pk, created_at = session.execute(
                'SELECT private_key, created_at FROM cpayment WHERE cpayment_id = :cid',
                {'cid': cpayment['id']}
            ).fetchone()
            if symbol == 'btc':
                balance = manager.from_subunit('btc', manager.currencies['btc'].get_cpayment_address_balance(pk))
            else:
                balance = manager.from_subunit(cpayment['symbol'], manager.get_balance(symbol, pk))
            merchant = get_merchant(merchant_id, session)
            print(balance, amount)
            if balance >= amount:
                commission = round(COMMISSION * amount + COMMISSIONS[cpayment['symbol']], 6)
                amount_to_balance = round(amount - commission, 6)
                update_cpayment(
                    user_id=-1, cpayment_id=cpayment['id'],
                    data={
                        'status': 2, 'received_crypto': amount_to_balance,
                        'ended_at': str(datetime.now(timezone.utc)),
                        'callback_url_cpay': merchant['callback_url_cpay'],
                        'amount_left': 0, 'amount_received': balance
                    }
                )
                session.execute(
                    'UPDATE cpayment SET is_done = TRUE, commission = :comm WHERE cpayment_id = :cid',
                    {'cid': cpayment['id'], 'comm': commission}
                )
                if symbol != 'btc':
                    manager.currencies[symbol].create_tx_in_cpay(pk)
                change_balance(
                    merchant_id, msg=f'Cpayment {cpayment["id"]} done',
                    amount=amount_to_balance, symbol=symbol, session=session
                )
                create_operation(
                    session, merchant_id, cpayment['id'], symbol, cpayment['currency'],
                    amount_to_balance, action=Action.cpayment,
                    operation_type=OperationTypes.public_api, amount_currency=cpayment['amount_currency']
                )
            elif balance > 0:
                amount_left = amount - balance
                if amount_left != cpayment['amount_left']:
                    update_cpayment(
                        user_id=-1, cpayment_id=cpayment['id'],
                        data={
                            'amount_left': amount_left, 'amount_received': balance
                        }
                    )
            else:
                if created_at + timedelta(hours=HOURS_TO_PROCESS) < datetime.now(timezone.utc):
                    update_cpayment(
                        user_id=-1, cpayment_id=cpayment['id'],
                        data={
                            'status': 3, 'ended_at': str(datetime.now(timezone.utc)),
                            'callback_url_cpay': merchant['callback_url_cpay']
                        }
                    )
                    session.execute(
                        'UPDATE cpayment SET is_expired = TRUE WHERE cpayment_id = :cid',
                        {'cid': cpayment['id']}
                    )
