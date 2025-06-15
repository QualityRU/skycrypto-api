from utils.utils import get_payments_to_deprecate, decline_purchase


def deprecate_payments_trigger():
    purchases = get_payments_to_deprecate()
    for payment in purchases:
        decline_purchase(payment['merchant_id'], payment['id'])
