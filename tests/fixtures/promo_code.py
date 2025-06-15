from typing import Callable

import pytest
from _decimal import Decimal
from sqlalchemy import insert, update
from sqlalchemy.orm import Session

from utils.db import mapping_result_to_dto
from utils.tables import PromoCodeDTO, rates_table, promo_codes_table, WalletDTO, wallets_table
from utils.utils import generate_promocode


@pytest.fixture
def promo_code_factory(db_session: Session) -> Callable[..., PromoCodeDTO]:
    def create_promo_code(wallet: WalletDTO, amount: int, count: int, is_deleted: bool) -> PromoCodeDTO:
        code = generate_promocode()
        stmt = (
            insert(promo_codes_table)
            .values(wallet_id=wallet.id, code=code, amount=amount, count=count, is_deleted=is_deleted)
            .returning(promo_codes_table)
        )
        result = db_session.execute(stmt)
        frozen_amount = amount * count
        stmt = (
            update(wallets_table)
            .values(frozen=frozen_amount, balance=wallet.balance - frozen_amount)
            .returning(wallets_table)
        )
        db_session.execute(stmt)
        return mapping_result_to_dto(result, PromoCodeDTO)

    return create_promo_code


@pytest.fixture
def promo_code(wallet: WalletDTO, promo_code_factory: Callable[..., PromoCodeDTO]) -> PromoCodeDTO:
    return promo_code_factory(wallet, 100, 1, False)
