from data_handler import dh
from utils.db_sessions import session_scope
from utils.logger import logger
from utils.utils import get_payments_v2_to_complete


def confirm_payments_v2():
    payments_v2_to_complete = get_payments_v2_to_complete()
    for payment_v2 in payments_v2_to_complete:
        print(payment_v2)

        with session_scope() as session:
            try:
                deal = dh.get_deal_for_update_state(payment_v2['symbol'], payment_v2['deal'], session=session)
                if deal['requisite'] and deal['state'] == 'confirmed' and payment_v2['fiat_sent']:
                    dh.update_deal_state(payment_v2['symbol'], payment_v2['deal'], payment_v2['merchant_id'], session=session)
            except Exception as e:
                logger.exception(e)
                continue
