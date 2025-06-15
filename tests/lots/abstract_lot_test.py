from flask import Response
from sqlalchemy import update

from system.settings import Session
from tests.abstract_test import AbstractAPITest
from utils.tables import lots_table


class AbstractLotTest(AbstractAPITest):
    def _update_lot(self, values: dict, lot_id: int, db_session: Session) -> Response:
        stmt = (
            update(lots_table)
            .where(lots_table.c.id == lot_id)
            .values(**values)
        )
        db_session.execute(stmt)