from sqlalchemy import update, select

from system.settings import Session
from tests.abstract_test import AbstractAPITest
from utils.db import mapping_result_to_dto
from utils.tables import DealDTO, deals_table, DisputeDTO, disputes_table, DealCommissionDTO, deal_commissions_table


class AbstractDealTest(AbstractAPITest):
    def _update_deal(self, values: dict, deal_id: int, db_session: Session):
        stmt = (
            update(deals_table)
            .where(deals_table.c.id == deal_id)
            .values(**values)
            .returning(deals_table)
        )
        db_session.execute(stmt)

    def _select_deal(self, deal_id: int, db_session: Session) -> DealDTO:
        stmt = (
            select([deals_table])
            .where(deals_table.c.id == deal_id)
        )
        db_session.execute(stmt)
        result = db_session.execute(stmt)
        result_deal_dto = mapping_result_to_dto(result, DealDTO)
        return result_deal_dto

    def _select_dispute(self, dispute_id: int, db_session: Session) -> DisputeDTO:
        stmt = (
            select([disputes_table])
            .where(disputes_table.c.id == dispute_id)
        )
        db_session.execute(stmt)
        result = db_session.execute(stmt)
        result_dispute_dto = mapping_result_to_dto(result, DisputeDTO)
        return result_dispute_dto

    def _select_deal_commissions(self, deal_id: int, db_session: Session) -> DealCommissionDTO:
        stmt = (
            select([deal_commissions_table])
            .where(deal_commissions_table.c.deal_id == deal_id)
        )
        db_session.execute(stmt)
        result = db_session.execute(stmt)
        result_commissions_dto = mapping_result_to_dto(result, DealCommissionDTO)
        return result_commissions_dto