from typing import Callable

import pytest
from _decimal import Decimal
from sqlalchemy import insert
from sqlalchemy.orm import Session

from utils.db import mapping_result_to_dto
from utils.tables import CryptoSettingsDTO, crypto_settings_table


@pytest.fixture
def crypto_settings_factory(db_session: Session) -> Callable[..., CryptoSettingsDTO]:
    def crypto_settings(
            coin_name: str,
            symbol: str,
            tx_out_commission: Decimal,
            min_tx_amount: Decimal,
            net_commission: int,
            buyer_commission: Decimal,
            seller_commission: Decimal
    ) -> CryptoSettingsDTO:
        stmt = (
            insert(crypto_settings_table)
            .values(
                coin_name=coin_name,
                symbol=symbol,
                tx_out_commission=tx_out_commission,
                min_tx_amount=min_tx_amount,
                net_commission=net_commission,
                buyer_commission=buyer_commission,
                seller_commission=seller_commission
            )
            .returning(crypto_settings_table)
        )
        result = db_session.execute(stmt)
        return mapping_result_to_dto(result, CryptoSettingsDTO)

    return crypto_settings


@pytest.fixture
def crypto_settings_usdt(crypto_settings_factory: Callable[..., CryptoSettingsDTO]) -> CryptoSettingsDTO:
    return crypto_settings_factory("Tether (TRC20)", "usdt", 5, 5, 0, 0, 0)

@pytest.fixture
def crypto_settings_btc(crypto_settings_factory: Callable[..., CryptoSettingsDTO]) -> CryptoSettingsDTO:
    return crypto_settings_factory("Bitcoin", "btc", 0.00001000, 0.00010000, 0.0200, 0.00400, 0)