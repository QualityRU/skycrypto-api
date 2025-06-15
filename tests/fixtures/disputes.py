from typing import Callable

import pytest
from _decimal import Decimal
from sqlalchemy import insert
from sqlalchemy.orm import Session

from utils.db import mapping_result_to_dto
from utils.tables import DisputeDTO, disputes_table
from datetime import datetime


@pytest.fixture
def dispute_factory(db_session: Session) -> Callable[..., DisputeDTO]:
    def create_dispute(
            deal_id: int,
            initiator: int,
            opponent: int,
            is_closed: bool,
            created_at: datetime,
            is_second_notification_sent: bool
    ) -> DisputeDTO:
        stmt = (
            insert(disputes_table)
            .values(
                deal_id=deal_id,
                initiator=initiator,
                opponent=opponent,
                is_closed=is_closed,
                created_at=created_at,
                is_second_notification_sent=is_second_notification_sent,
            )
            .returning(disputes_table)
        )
        result = db_session.execute(stmt)
        return mapping_result_to_dto(result, DisputeDTO)

    return create_dispute


@pytest.fixture
def dispute(dispute_factory: Callable[..., DisputeDTO], deal) -> DisputeDTO:
    return dispute_factory(deal.id, deal.seller_id, deal.buyer_id, False, "2023-12-07", False)


