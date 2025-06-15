from typing import Callable

import pytest
from _decimal import Decimal
from sqlalchemy import insert
from sqlalchemy.orm import Session

from utils.db import mapping_result_to_dto
from utils.tables import LotDTO, lots_table, UserDTO, CurrencyDTO, BrokerDTO
from utils.utils import get_lot_id


@pytest.fixture
def lot_factory(db_session: Session) -> Callable[..., LotDTO]:
    def create_lot(
        limit_from: int, limit_to: int, rate: Decimal, user_id: int, symbol: str, currency: str, type_: str, **kwargs
    ) -> LotDTO:
        stmt = (
            insert(lots_table)
            .values(
                identificator=get_lot_id(),
                limit_from=limit_from,
                limit_to=limit_to,
                rate=rate,
                user_id=user_id,
                symbol=symbol,
                currency=currency,
                type=type_,
                **kwargs
            )
            .returning(lots_table)
        )
        result = db_session.execute(stmt)
        return mapping_result_to_dto(result, LotDTO)

    return create_lot


@pytest.fixture
def lot(lot_factory: Callable[..., LotDTO], user: UserDTO, currency: CurrencyDTO, broker: BrokerDTO) -> LotDTO:
    return lot_factory(100, 1000, Decimal("2500000"), user.id, "usdt", currency.id, type_="sell", broker_id=broker.id)
