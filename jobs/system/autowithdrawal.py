import os
from decimal import Decimal

from crypto.btc import BTC
from crypto.eth import ETH
from crypto.manager import manager
from crypto.usdt import USDT
from utils.db_sessions import session_scope
from utils.logger import logger

if os.getenv('TEST'):
    SETTINGS = {
        'btc': {
            'threshold': Decimal('0.22'),
            'withdraw_amount': Decimal('0.02'),
            'address': 'tb1q7mjyq8ud0mdxajsxupxzvwl5s73vw4tr2sa0d0',
        },
        'eth': {
            'threshold': Decimal('15'),
            'withdraw_amount': Decimal('2'),
            'address': '0x53c918958C91b59b181c7B43B7E52B628b1409b1',
        },
        'usdt': {
            'threshold': Decimal('90'),
            'withdraw_amount': Decimal('10'),
            'address': 'THqFm1qLm6bMiNWrBgAiDDZGFhHr9UxqEJ',
        },
    }
else:
    SETTINGS = {
        'btc': {
            'threshold': Decimal('5'),
            'withdraw_amount': Decimal('1'),
            'address': '',
        },
        'eth': {
            'threshold': Decimal('7'),
            'withdraw_amount': Decimal('2'),
            'address': '',
        },
        'usdt': {
            'threshold': Decimal('20000'),
            'withdraw_amount': Decimal('10000'),
            'address': '',
        },
    }


def auto_withdraw():
    for symbol, module in manager.currencies.items():
        threshold = SETTINGS[symbol]['threshold']
        withdraw_amount = SETTINGS[symbol]['withdraw_amount']
        address = SETTINGS[symbol]['address']

        if symbol == 'btc':
            balance = BTC.from_subunit(BTC.get_balance(confs=1))
        else:
            balance = module.from_subunit(module.get_balance())

        if balance > threshold:
            print(balance, threshold)

            if symbol == 'btc':
                tx_hash = BTC.create_tx_out_primary(address, withdraw_amount)
            elif symbol == 'eth':
                gas_price = ETH.get_gas_price(20)
                tx_hash = ETH.create_tx_out(address, withdraw_amount, gas_price)
            elif symbol == 'usdt':
                tx_hash = USDT.create_tx_out(address, withdraw_amount)

            logger.info(f'New auto withdrawal on {withdraw_amount} {symbol.upper()}, {tx_hash}')

            with session_scope() as session:
                session.execute(
                    "INSERT INTO wthd (tx_hash, amount, symbol) VALUES (:tx_hash, :amount, :sym)",
                    {'tx_hash': tx_hash, 'amount': withdraw_amount, 'sym': symbol}
                )
