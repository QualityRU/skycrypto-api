from typing import Optional, Callable
from uuid import uuid4

import pytest
from _decimal import Decimal
from sqlalchemy import insert
from sqlalchemy.orm import Session

from utils.db import mapping_result_to_dto
from utils.tables import WalletDTO, wallets_table, UserDTO


@pytest.fixture
def wallet_factory(db_session: Session) -> Callable[..., WalletDTO]:
    def create_wallet(
            user_id: int,
            balance: Decimal,
            symbol: Optional[str] = None,
            private_key: Optional[str] = None,
            **kwargs
    ) -> WalletDTO:
        symbol = symbol or "usdt"
        private_key = private_key or str(uuid4())
        stmt = (
            insert(wallets_table)
            .values(
                user_id=user_id,
                symbol=symbol,
                balance=balance,
                private_key=private_key,
                **kwargs
            )
            .returning(wallets_table)
        )
        result = db_session.execute(stmt)
        return mapping_result_to_dto(result, WalletDTO)

    return create_wallet


@pytest.fixture
def wallet(user: UserDTO, wallet_factory: Callable[..., WalletDTO]) -> WalletDTO:
    return wallet_factory(user.id, Decimal("10000000000.0"))
