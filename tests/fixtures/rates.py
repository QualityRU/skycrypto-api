from typing import Callable

import pytest
from _decimal import Decimal
from sqlalchemy import insert
from sqlalchemy.orm import Session

from utils.db import mapping_result_to_dto
from utils.tables import RateDTO, rates_table


@pytest.fixture
def rate_factory(db_session: Session) -> Callable[..., RateDTO]:
    def create_rate(symbol: str, rate: Decimal, currency: str) -> RateDTO:
        stmt = (
            insert(rates_table)
            .values(symbol=symbol, rate=rate, currency=currency)
            .returning(rates_table)
        )
        result = db_session.execute(stmt)
        return mapping_result_to_dto(result, RateDTO)

    return create_rate


@pytest.fixture
def usdt_rate(rate_factory: Callable[..., RateDTO]) -> RateDTO:
    return rate_factory("usdt", Decimal("1"), "rub")


@pytest.fixture
def btc_rate(rate_factory: Callable[..., RateDTO]) -> RateDTO:
    return rate_factory("btc", Decimal("1"), "rub")
