from typing import Callable
from unittest.mock import patch

from flask import Response
from flask.testing import FlaskClient

from system.settings import Session
from tests.deals.abstract_deal_test import AbstractDealTest
from utils.tables import UserDTO, WalletDTO, DealDTO, DisputeDTO


class TestUpdateDealState(AbstractDealTest):
    def _update_deal_state(self, client: FlaskClient, data: dict, token: str) -> Response:
        response = self._make_patch_request(client, "/deal-state", token, data)
        return response

    def test_update_deal_state_from_proposed_to_confirmed_valid(
            self, client: FlaskClient, token: str, user: UserDTO, wallet: WalletDTO, deal: DealDTO, db_session: Session
    ):
        data = {
            "deal_id": deal.identificator,
            "user_id": user.id
        }

        with patch("utils.notifications_queue._send_queue_notification"):
            response = self._update_deal_state(client, data, token)
            assert response.status == self.HttpStatus.OK
            assert response.json == {"success":"new deal status = confirmed"}

        refresh_deal = self._select_deal(deal.id, db_session)
        assert refresh_deal.state == "confirmed"

        notification = self._select_notification(deal.buyer_id, db_session)
        assert notification.type == "deal"
        assert notification.symbol == deal.symbol
        assert notification.deal_id == deal.id

    def test_update_deal_state_from_proposed_to_confirmed_not_none_payment_v2_id_valid(
        self, client: FlaskClient, token: str, user: UserDTO, wallet: WalletDTO, deal: DealDTO, db_session: Session
    ):
        data = {
            "deal_id": deal.identificator,
            "user_id": user.id
        }
        self._update_deal({"payment_v2_id": "123e4567-e89b-12d3-a456-426655440000"}, deal.id, db_session)

        response = self._update_deal_state(client, data, token)
        assert response.status == self.HttpStatus.OK
        assert response.json == {"success": "new deal status = confirmed"}

        refresh_deal = self._select_deal(deal.id, db_session)
        assert refresh_deal.state == "confirmed"

        notification = self._select_notification(deal.buyer_id, db_session)
        assert notification is None

    def test_update_deal_state_from_confirmed_to_paid_valid(
            self,
            client: FlaskClient,
            token: str,
            user: UserDTO,
            wallet: WalletDTO,
            deal: DealDTO,
            dispute: DisputeDTO,
            db_session: Session
    ):
        data = {
            "deal_id": deal.identificator,
            "user_id": deal.buyer_id
        }

        self._update_deal({"state": "confirmed"}, deal.id, db_session)

        with patch("utils.notifications_queue._send_queue_notification"):
            response = self._update_deal_state(client, data, token)
            assert response.status == self.HttpStatus.OK
            assert response.json == {"success": "new deal status = paid"}

        refresh_deal = self._select_deal(deal.id, db_session)
        assert refresh_deal.state == "paid"

        notification = self._select_notification(deal.seller_id, db_session)
        assert notification.type == "deal"
        assert notification.symbol == deal.symbol
        assert notification.deal_id == deal.id

    def test_update_deal_state_from_confirmed_not_none_sale_v2_id_valid(
            self,
            client: FlaskClient,
            token: str,
            user: UserDTO,
            wallet: WalletDTO,
            deal: DealDTO,
            dispute: DisputeDTO,
            db_session: Session
    ):
        data = {
            "deal_id": deal.identificator,
            "user_id": deal.buyer_id
        }

        self._update_deal(
            {"state": "confirmed", "sale_v2_id": "123e4567-e89b-12d3-a456-426655440000"},
            deal.id,
            db_session
        )

        with patch("data_handler.DataHandler._process_earnings"), patch("utils.notifications_queue._send_queue_notification"):
            response = self._update_deal_state(client, data, token)
            assert response.status == self.HttpStatus.OK
            assert response.json == {"success": "deal processed"}

        refresh_deal = self._select_deal(deal.id, db_session)
        assert refresh_deal.state == "closed"

        refresh_dispute = self._select_dispute(dispute.id, db_session)
        assert refresh_dispute.is_closed is True

    def test_update_deal_state_from_paid_to_closed_valid(
            self,
            client: FlaskClient,
            token: str,
            user: UserDTO,
            wallet: WalletDTO,
            deal: DealDTO,
            dispute: DisputeDTO,
            db_session: Session
    ):
        data = {
            "deal_id": deal.identificator,
            "user_id": deal.seller_id
        }

        self._update_deal({"state": "paid"}, deal.id, db_session)

        with patch("data_handler.DataHandler._process_earnings"), patch("utils.notifications_queue._send_queue_notification"):
            response = self._update_deal_state(client, data, token)
            assert response.status == self.HttpStatus.OK
            assert response.json == {"success": "deal processed"}

        refresh_deal = self._select_deal(deal.id, db_session)
        assert refresh_deal.state == "closed"

        refresh_dispute = self._select_dispute(dispute.id, db_session)
        assert refresh_dispute.is_closed is True

    def test_update_deal_none_data_invalid(self, client: FlaskClient, token: str, user: UserDTO, deal: DealDTO):
        data = {
            "deal_id": deal.identificator,
        }

        response = self._update_deal_state(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST

        data = {
            "user_id": deal.seller_id,
        }

        response = self._update_deal_state(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST

    def test_update_deal_wrong_state_invalid(
            self, client: FlaskClient, token: str, user: UserDTO, deal: DealDTO, db_session: Session
    ):
        data = {
            "deal_id": deal.identificator,
            "user_id": user.id
        }
        self._update_deal({"state": "deleted"}, deal.id, db_session)

        response = self._update_deal_state(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST
        assert response.json["detail"] == "400 Bad Request: wrong status"