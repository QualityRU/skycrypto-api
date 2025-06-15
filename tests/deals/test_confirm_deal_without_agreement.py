from typing import Callable
from unittest.mock import patch

from flask import Response
from flask.testing import FlaskClient

from system.settings import Session
from tests.deals.abstract_deal_test import AbstractDealTest
from utils.tables import WalletDTO, DealDTO, DisputeDTO


class TestConfirmDealWithoutAgreement(AbstractDealTest):
    def _confirm_deal_without_agreement(self, client: FlaskClient, data: dict, token: str) -> Response:
        response = self._make_post_request(client, "/deal-confirmation-no-agreement", token, data)
        return response

    def test_confirm_deal_without_agreement_valid(
            self,
            client: FlaskClient,
            token: str,
            deal: DealDTO,
            db_session: Session
    ):

        data = {
            "user_id": deal.seller_id,
            "deal_id": deal.identificator
        }
        self._update_deal(
            {"state": "confirmed", "payment_id": "123e4567-e89b-12d3-a456-426655440000"}, deal.id, db_session
        )
        with patch("data_handler.DataHandler._process_deal"):
            response = self._confirm_deal_without_agreement(client, data, token)
            assert response.status == self.HttpStatus.OK
            assert response.json == {"success": "deal processed"}

    def test_confirm_deal_without_agreement_not_confirmed_invalid(
            self,
            client: FlaskClient,
            token: str,
            deal: DealDTO,
            db_session: Session
    ):
        data = {
            "user_id": deal.seller_id,
            "deal_id": deal.identificator
        }
        self._update_deal({"payment_id": "123e4567-e89b-12d3-a456-426655440000"}, deal.id, db_session)

        response = self._confirm_deal_without_agreement(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST

    def test_confirm_deal_without_agreement_none_payment_id_invalid(
            self,
            client: FlaskClient,
            token: str,
            deal: DealDTO,
            db_session: Session
    ):
        data = {
            "user_id": deal.seller_id,
            "deal_id": deal.identificator
        }
        self._update_deal({"state": "confirmed"}, deal.id, db_session)

        response = self._confirm_deal_without_agreement(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST

    def test_confirm_deal_without_agreement_wrong_seller_id_invalid(
            self,
            client: FlaskClient,
            token: str,
            deal: DealDTO,
            db_session: Session
    ):
        data = {
            "user_id": deal.buyer_id,
            "deal_id": deal.identificator
        }
        self._update_deal(
            {"state": "confirmed", "payment_id": "123e4567-e89b-12d3-a456-426655440000"}, deal.id, db_session
        )

        response = self._confirm_deal_without_agreement(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST



