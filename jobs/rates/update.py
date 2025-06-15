from decimal import Decimal

from utils.binance_client import binance_client
from utils.db_sessions import session_scope
from utils.logger import logger


def get_rates():
    rates = {}
    for symbol in ('ETH', 'BTC', 'USDT'):
        rates[symbol.lower()] = {}
        for currency in ('RUB', 'USD', 'UAH'):
            binance_symbol = symbol + currency
            if currency == 'USD':
                binance_symbol += 'T'
            if binance_symbol == 'USDTUSDT':
                rates[symbol.lower()][currency.lower()] = 1
            else:
                rates[symbol.lower()][currency.lower()] = binance_client.get_symbol_price(binance_symbol)
    logger.debug(f'UPDATE RATE, new rate = {rates}')
    return rates


def _get_currencies(session):
    curs = [item['id'] for item in session.execute('SELECT id FROM currency').fetchall()]
    return curs


def upload_to_database(rates: dict, session):
    logger.info(f'UPDATE RATE, new rate = {rates}')
    # {btc: {rub: 1, usd: 2}}
    for symbol, currencies in rates.items():
        for currency, rate in currencies.items():
            session.execute(
                """
                    INSERT INTO rates (symbol, rate, currency)
                    VALUES (:sym, :rate, :cur)
                    ON CONFLICT (symbol, currency) 
                    DO
                        UPDATE SET rate = :rate
                """, {'sym': symbol, 'rate': rate, 'cur': currency}
            )


def extend_rates(rates_dict, currencies, session):
    available_rates = set(rates_dict['btc'].keys())
    non_rated_currencies = set(currencies).difference(available_rates)
    for cur in non_rated_currencies:
        usd_rate = session.execute('SELECT usd_rate FROM currency WHERE id = :cur', {'cur': cur}).scalar()
        for crypto in rates_dict.keys():
            rates_dict[crypto][cur] = Decimal(str(rates_dict[crypto]['usd'])) * usd_rate


def update_rates():
    with session_scope() as session:
        currencies = _get_currencies(session)
        rates = get_rates()
        extend_rates(rates, currencies, session)
        upload_to_database(rates, session)
