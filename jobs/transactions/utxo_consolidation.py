import logging
import os

from crypto.btc import BTC
from utils.frozen_control_bot import bot


CHAT_ID = os.getenv('CONSOLIDATION_CHAT_ID')


logging.basicConfig(level=logging.ERROR,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger()


def send_message_new_consolidation(address, tx_link, amount, fee, inputs_used, inputs_total):
    text = (
        f'<b>НОВАЯ КОНСОЛИДАЦИЯ:</b>\n'
        f'<b>Адрес:</b> {address}\n'
        f'<b>Ссылка:</b> {tx_link}\n'
        f'<b>Сумма:</b> {amount}\n'
        f'<b>Комиссия:</b> {fee}\n'
        f'<b>Всего выходов на момент транзакции:</b> {inputs_total}\n'
        f'<b>Выходов использовано:</b> {inputs_used}'
    )
    bot.send_message(chat_id=CHAT_ID, text=text)    


def consolidate():
    max_amount = 0.01
    unspents = BTC.get_unspents(max_amount)
    total_unspents = len(unspents)
    send_message_new_consolidation(
        'тут будет адрес ноды',
        'ссылка на транзу',
        amount=sum([unspent['amount'] for unspent in unspents]),
        fee=0,
        inputs_used=min(300, total_unspents),
        inputs_total=total_unspents
    )
    # if total_unspents > 300:
    #     unspents = unspents[:300]
    #     address = BTC.get_new_pk()
    #     res, total_sum = BTC.wallet_create_psbt(unspents, address)
    #     fee = res['fee']
    #     res, hex_str = BTC.finalize_transaction(res['psbt'])
    #     info = {
    #             'address': address,
    #             'total_amount': total_sum,
    #             'amount': total_sum - fee,
    #             'fee': fee,
    #             'hex': hex_str,
    #             'inputs_used': len(unspents),
    #             'inputs_total': total_unspents
    #     }
    #     transaction_hex_result = BTC.send_raw_transaction(info['hex'])
    #     tx_link = f'https://www.blockchain.com/explorer/transactions/btc/{transaction_hex_result}'
    #     send_message_new_consolidation(
    #         address, tx_link, info['amount'],
    #         info['fee'], info['inputs_used'],
    #         info['inputs_total']
    #     )
