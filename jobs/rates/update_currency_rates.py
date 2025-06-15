import requests

from utils.db_sessions import session_scope

url = "https://api.currencyapi.com/v3/latest"
CURRENCY_KEY = 'M4p7DduqVKAAWH5lA0UFY4NRYbxshBX7r0kq4Ti2'
headers = {
    'apikey': CURRENCY_KEY
}


def _get_currencies(session):
    curs = [item['id'] for item in session.execute("SELECT id FROM currency WHERE id <> 'usd'").fetchall()]
    return curs


def update_currency(currency, rate, session):
    if currency == 'byn':
        rate = round(rate * 1.2, 2)
    session.execute('UPDATE currency SET usd_rate = :usd_rate WHERE id = :currency', {'currency': currency, 'usd_rate': rate})


def update():
    with session_scope() as session:
        currencies = _get_currencies(session)
        rates = requests.get(url, headers=headers).json()['data']
        for currency in currencies:
            update_currency(currency, rates[currency.upper()]['value'], session)
