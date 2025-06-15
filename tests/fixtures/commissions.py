import random
from typing import Optional, Callable

import pytest
from _decimal import Decimal
from sqlalchemy import insert
from sqlalchemy.orm import Session

from utils.db import mapping_result_to_dto
from utils.tables import commissions_table, CommissionDTO
from utils.utils import get_nickname, generate_ref_code


@pytest.fixture
def commission_factory(db_session: Session, currency: CommissionDTO) -> Callable[..., CommissionDTO]:
    def create_commission(type: str, symbol: str, commission: Decimal) -> CommissionDTO:

        stmt = (
            insert(commissions_table)
            .values(
                type=type, symbol=symbol, commission=commission
            )
            .returning(commissions_table)
        )
        result = db_session.execute(stmt)
        return mapping_result_to_dto(result, CommissionDTO)

    return create_commission


@pytest.fixture
def buyer_referral_commission_usdt(commission_factory: Callable[..., CommissionDTO]) -> CommissionDTO:
    return commission_factory("buyer_referral", "usdt", Decimal("100"))
