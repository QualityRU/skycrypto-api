from typing import Callable

import pytest
from _decimal import Decimal
from sqlalchemy import insert
from sqlalchemy.orm import Session

from utils.db import mapping_result_to_dto
from utils.tables import CurrencyDTO, currencies_table


@pytest.fixture
def currency_factory(db_session: Session) -> Callable[..., CurrencyDTO]:
    def create_currency(id_: str, is_active: bool, usd_rate: Decimal, rate_variation: Decimal) -> CurrencyDTO:
        stmt = (
            insert(currencies_table)
            .values(id=id_, is_active=is_active, usd_rate=usd_rate, rate_variation=rate_variation)
            .returning(currencies_table)
        )
        result = db_session.execute(stmt)
        return mapping_result_to_dto(result, CurrencyDTO)

    return create_currency


@pytest.fixture
def currency(currency_factory: Callable[..., CurrencyDTO]) -> CurrencyDTO:
    return currency_factory("rub", True, Decimal("83.8501"), Decimal("0.25"))
