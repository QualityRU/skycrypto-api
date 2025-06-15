from utils.utils import deprecate_inactive_sales, deprecate_inactive_sales_v2


def deprecate_sales():
    deprecate_inactive_sales(user_id=-1)
    deprecate_inactive_sales_v2(user_id=-1)
