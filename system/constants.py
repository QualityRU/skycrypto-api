import os
from decimal import Decimal

NICKNAME_DIGITS = 3
NICKNAME_LETTERS = 2
LOT_ID_LENGTH = 10
DEAL_ID_LENGTH = 10
PROMOCODE_LENGTH = 5
TOKEN_LENGTH = 10
FILENAME_LENGTH = 30
REF_CODE_LENGTH = 10
CAMPAIGN_ID_LENGTH = 16

RATING_SMILES = ['🥉', '🥉🥉', '🥉🥉🥉', '🥈', '🥈🥈', '🥈🥈🥈', '🥇', '🥇🥇', '🥇🥇🥇', '💎']
MINUS_RATING_SMILE = '🚫'

TRANSACTION_TYPE = 'transaction'
MESSAGE_TYPE = 'message'
DEAL_TYPE = 'deal'

ONLINE_MINUTES = 60
CURRENCIES = ('rub', 'inr', 'usd', 'uah')

PROFITS_CHAT = int(os.environ.get('PROFITS_CHAT', -362970675))
EARNINGS_CHAT = int(os.environ.get('EARNINGS_CHAT', -346792762))
CONTROL_CHATS = {
    'eth': int(os.environ.get('CONTROL_CHAT_ETH', -1001284616087)),
    'btc': int(os.environ.get('CONTROL_CHAT_BTC', -289227802)),
    'usdt': int(os.environ.get('CONTROL_CHAT_USDT', -289227802))
}
MESSAGES_CHAT = int(os.environ.get('MESSAGES_CHAT', -250067491))

DEAL_CONTROL_CHAT = int(os.environ.get('DEAL_CONTROL_CHAT', -455045911))

LOT_TYPE_BUY = 'buy'
LOT_TYPE_SELL = 'sell'

STATES = ('proposed', 'confirmed', 'paid', 'closed', 'deleted')

if os.environ.get('TEST') == '1':
    DISPUTE_TIME = 3
    ADDITIONAL_DISPUTE_NOTIFICATION_TIME = 2
else:
    DISPUTE_TIME = 30
    ADDITIONAL_DISPUTE_NOTIFICATION_TIME = 20

MIN_PROMOCODE_AMOUNT = {
    'eth': Decimal('0.001'),
    'btc': Decimal('0.0001'),
    'usdt': Decimal('1')
}

withdraws_activation_statuses = {
    'eth': True,
    'btc': True,
    'usdt': True
}


class DealTypes:
    plain = 0
    fast = 1
    sky_pay = 2
    sky_sale = 3
    sky_sale_v2 = 4
    sky_pay_v2 = 5


class Action:
    deal = 1
    transaction = 2
    promocode = 3
    referral = 4
    sky_pay = 5
    sky_sale = 6
    sky_sale_v2 = 7
    api_withdrawal = 8
    cpayment = 9
    sky_pay_v2 = 10


class OperationTypes:
    plain = 1
    public_api = 2


ADMIN_ROLE = 0

PUBLIC_API_HOST = os.getenv('PUBLIC_API_HOST')
if PUBLIC_API_HOST is None:
    PUBLIC_API_HOST = 'http://35.179.52.209/rest/v2' if os.environ.get('TEST') else 'https://papi.skycrypto.net/rest/v2'

WITHDRAWAL_DEFAULT_LIMITS = {
    'btc': 1,
    'eth': 5,
    'usdt': 10000
}
