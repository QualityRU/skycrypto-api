from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal

from crypto.btc import BTC
from crypto.manager import manager
from data_handler import dh
from system.funds_changer import change_balance, freeze
from utils.db_sessions import session_scope
from utils.utils import get_withdrawals_v2_to_process, update_withdrawal_v2


COMMISSIONS = {
    'btc': Decimal('0.0001'),
    'eth': Decimal('0.001'),
    'usdt': Decimal('1')
}
COMMISSION = Decimal('0.005')


def process_withdrawal_v2():
    withdrawals_v2_to_process = get_withdrawals_v2_to_process()
    for withdrawal_v2 in withdrawals_v2_to_process:
        user_id = withdrawal_v2['merchant_id']
        if not manager.is_address_valid(withdrawal_v2['symbol'], withdrawal_v2['address']):
            update_withdrawal_v2(user_id=-1, withdrawal_v2_id=withdrawal_v2['id'], data={'status': 3})
            continue
        with session_scope() as session:
            wallet = dh.get_wallet(withdrawal_v2['symbol'], user_id, session)
            balance = Decimal(str(wallet['balance']))
            amount = round(Decimal(str(withdrawal_v2['amount'])), 8)
            commission = round(amount * COMMISSION + COMMISSIONS[withdrawal_v2['symbol']], 8)
            target_amount = amount + commission
            if balance < target_amount:
                update_withdrawal_v2(user_id=-1, withdrawal_v2_id=withdrawal_v2['id'], data={'status': 3})
                continue
            else:
                freeze(
                    user_id, msg=f'Withdraw v2 {withdrawal_v2["id"]}',
                    amount=target_amount, symbol=withdrawal_v2['symbol'],
                    session=session
                )
                q = """
                           INSERT INTO transactions (wallet_id, type, to_address, amount_units, commission, sky_commission, tx_type)
                           VALUES (:wid, 'out', :address, :amount, :comm, :comm, 2)
                       """
                session.execute(
                    q, {
                        'wid': wallet['id'],
                        'address': withdrawal_v2['address'],
                        'amount': amount,
                        'comm': commission
                    }
                )
                update_withdrawal_v2(
                    user_id=-1,
                    withdrawal_v2_id=withdrawal_v2['id'],
                    data={'status': 2, 'processed_at': str(datetime.now(timezone.utc))}
                )
