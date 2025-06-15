from typing import Callable

import pytest
from sqlalchemy import insert
from sqlalchemy.orm import Session

from utils.db import mapping_result_to_dto
from utils.tables import SettingsDTO, settings_table, merchant_table, MerchantDTO, DealDTO


@pytest.fixture
def merchant_factory(db_session: Session) -> Callable[..., MerchantDTO]:
    def create_merchant(user_id: int, name: str) -> MerchantDTO:
        stmt = (
            insert(merchant_table)
            .values(user_id=user_id, name=name)
            .returning(merchant_table)
        )
        result = db_session.execute(stmt)
        return mapping_result_to_dto(result, MerchantDTO)

    return create_merchant


@pytest.fixture
def merchant(deal: DealDTO,merchant_factory: Callable[..., MerchantDTO]) -> MerchantDTO:
    return merchant_factory(deal.seller_id, "name")




























