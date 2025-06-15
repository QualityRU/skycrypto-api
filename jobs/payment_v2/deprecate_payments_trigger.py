from utils.utils import get_payments_v2_to_deprecate, decline_payment_v2


def deprecate_payments_v2_trigger():
    purchases = get_payments_v2_to_deprecate()
    for payment in purchases:
        decline_payment_v2(payment['merchant_id'], payment['id'])
