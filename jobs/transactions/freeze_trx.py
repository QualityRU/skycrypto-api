import os

from crypto.trx import TRX


def freeze_trx():
    if not os.getenv('TEST'):
        TRX.freeze(10)
