from flask import Response
from flask.testing import FlaskClient
from sqlalchemy import update, select

from system.settings import Session
from tests.deals.abstract_deal_test import AbstractDealTest
from utils.db import mapping_result_to_dto
from utils.tables import UserDTO, WalletDTO, wallets_table, DealDTO


class TestStopDeal(AbstractDealTest):
    def _stop_deal(self, client: FlaskClient, data: dict, token: str) -> Response:
        response = self._make_post_request(client, "/stop-deal", token, data)
        return response

    def test_stop_deal_valid(
            self, client: FlaskClient, token: str, user: UserDTO, wallet: WalletDTO, deal: DealDTO, db_session: Session
    ):
        self._update_wallet({"frozen": deal.amount_subunit_frozen}, wallet.id, db_session)

        data = {
            "deal_id": deal.identificator
        }

        response = self._stop_deal(client, data, token)
        assert response.status == self.HttpStatus.OK
        assert response.json == {'success': 'deal deleted'}

        refresh_wallet = self._select_wallet(wallet.id, db_session)
        assert refresh_wallet.frozen == 0

    def test_stop_deal_none_deal_id_invalid(
            self, client: FlaskClient, token: str, user: UserDTO, wallet: WalletDTO, deal: DealDTO
    ):
        data = {}

        response = self._stop_deal(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST
