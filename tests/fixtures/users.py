import random
from typing import Optional, Callable

import pytest
from sqlalchemy import insert
from sqlalchemy.orm import Session

from utils.db import mapping_result_to_dto
from utils.tables import CurrencyDTO, UserDTO, users_table
from utils.utils import get_nickname, generate_ref_code


@pytest.fixture
def user_factory(db_session: Session, currency: CurrencyDTO) -> Callable[..., UserDTO]:
    def create_user(telegram_id: Optional[int] = None) -> UserDTO:
        telegram_id = telegram_id or random.randint(10000, 99999)
        stmt = (
            insert(users_table)
            .values(
                telegram_id=telegram_id,
                nickname=get_nickname(""),
                ref_kw=generate_ref_code(),
                currency=currency.id,
                is_verify=True
            )
            .returning(users_table)
        )
        result = db_session.execute(stmt)
        return mapping_result_to_dto(result, UserDTO)

    return create_user


@pytest.fixture
def user(user_factory: Callable[..., UserDTO]) -> UserDTO:
    return user_factory()
