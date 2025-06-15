from typing import Callable

import pytest
from _decimal import Decimal
from sqlalchemy import insert, update
from sqlalchemy.orm import Session

from utils.db import mapping_result_to_dto
from utils.tables import DealDTO, deals_table, UserDTO, LotDTO, CurrencyDTO, BrokerDTO, wallets_table, WalletDTO
from utils.utils import get_deal_id


@pytest.fixture
def deal_factory(db_session: Session) -> Callable[..., DealDTO]:
    def create_deal(
        amount_currency: Decimal,
        amount_subunit: Decimal,
        amount_subunit_frozen: Decimal,
        buyer_id: int,
        seller_id: int,
        lot_id: int,
        rate: Decimal,
        requisite: str,
        symbol: str,
        currency_id: str,
        type_: int,
        **kwargs
    ) -> DealDTO:
        stmt = (
            insert(deals_table)
            .values(
                identificator=get_deal_id(),
                amount_currency=amount_currency,
                amount_subunit=amount_subunit,
                amount_subunit_frozen=amount_subunit_frozen,
                buyer_id=buyer_id,
                seller_id=seller_id,
                lot_id=lot_id,
                rate=rate,
                requisite=requisite,
                symbol=symbol,
                currency=currency_id,
                type=type_,
                **kwargs
            )
            .returning(deals_table)
        )
        result = db_session.execute(stmt)
        return mapping_result_to_dto(result, DealDTO)

    return create_deal


@pytest.fixture
def deal(
    deal_factory: Callable[..., DealDTO],
    user_factory,
    user: UserDTO,
    lot: LotDTO,
    currency: CurrencyDTO,
    broker: BrokerDTO,
    wallet: WalletDTO,
) -> DealDTO:
    buyer = user_factory()
    return deal_factory(
        Decimal("1000"),
        Decimal("5033000"),
        Decimal("5049100"),
        buyer.id,
        user.id,
        lot.id,
        Decimal("24"),
        "123123123",
        "usdt",
        currency.id,
        0,
    )
