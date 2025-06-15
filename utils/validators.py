from decimal import Decimal
from crypto.manager import manager


def is_valid_float_digits(value: Decimal, digits: int):
    return abs(value.as_tuple().exponent) <= digits


def is_amount_precision_right_for_symbol(symbol: float, value: Decimal):
    return is_valid_float_digits(value, digits=manager.currencies[symbol].DECIMALS)
