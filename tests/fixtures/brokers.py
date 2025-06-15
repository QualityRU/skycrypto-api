from typing import Optional, Callable
from uuid import uuid4, UUID

import pytest
from sqlalchemy import insert
from sqlalchemy.orm import Session

from utils.db import mapping_result_to_dto
from utils.tables import BrokerDTO, brokers_table, CurrencyDTO, BrokerCurrencyDTO, broker_currencies_table


@pytest.fixture
def broker_factory(db_session: Session) -> Callable[..., BrokerDTO]:
    def create_broker(
        name: str,
        is_deleted: bool = False,
        sky_pay: bool = False,
        fast_deal: bool = False,
        is_card: bool = False,
        logo: Optional[str] = None,
    ) -> BrokerDTO:
        stmt = (
            insert(brokers_table)
            .values(
                id=str(uuid4()),
                name=name,
                is_deleted=is_deleted,
                sky_pay=sky_pay,
                fast_deal=fast_deal,
                is_card=is_card,
                logo=logo,
            )
            .returning(brokers_table)
        )
        result = db_session.execute(stmt)
        return mapping_result_to_dto(result, BrokerDTO)

    return create_broker


@pytest.fixture
def broker(broker_factory: Callable[..., BrokerDTO]) -> BrokerDTO:
    return broker_factory("ВТБ 5000")


@pytest.fixture
def broker_currency_factory(
    db_session: Session, currency: CurrencyDTO, broker: BrokerDTO
) -> Callable[..., BrokerCurrencyDTO]:
    def create_broker_currency(currency_id: str, broker_id: UUID) -> BrokerCurrencyDTO:
        stmt = (
            insert(broker_currencies_table)
            .values(currency=currency_id, broker_id=broker_id)
            .returning(broker_currencies_table)
        )
        result = db_session.execute(stmt)
        return mapping_result_to_dto(result, BrokerCurrencyDTO)

    return create_broker_currency


@pytest.fixture
def broker_currency(
    broker_currency_factory: Callable[..., BrokerCurrencyDTO], currency: CurrencyDTO, broker: BrokerDTO
) -> BrokerCurrencyDTO:
    return broker_currency_factory(currency.id, broker.id)
