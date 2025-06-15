from unittest.mock import patch

from flask import Response
from flask.testing import FlaskClient
from sqlalchemy import update, select

from system.settings import Session
from tests.deals.abstract_deal_test import AbstractDealTest
from utils.db import mapping_result_to_dto
from utils.tables import UserDTO, WalletDTO, wallets_table, DealDTO, deals_table, DisputeDTO, disputes_table, LotDTO


class TestCancelDeal(AbstractDealTest):
    def _cancel_deal(self, client: FlaskClient, data: dict, token: str) -> Response:
        response = self._make_post_request(client, "/cancel-deal", token, data)
        return response

    def test_cancel_deal_valid(
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
            "user_id": user.id
        }

        self._update_wallet({"frozen": deal.amount_subunit_frozen}, wallet.id, db_session)

        with patch("utils.notifications_queue._send_queue_notification"):
            response = self._cancel_deal(client, data, token)
            assert response.status == self.HttpStatus.OK
            assert response.json == {"success": "deal canceled"}

        refresh_wallet = self._select_wallet(wallet.id, db_session)
        assert refresh_wallet.frozen == 0

        refresh_deal = self._select_deal(deal.id, db_session)
        assert refresh_deal.state == "deleted"

        refresh_dispute = self._select_dispute(dispute.id, db_session)
        assert refresh_dispute.is_closed is True

    def test_cancel_deal_wrong_id_invalid(
            self, client: FlaskClient, token: str, user: UserDTO, wallet: WalletDTO, deal: DealDTO
    ):
        data = {
            "deal_id": "id",
            "user_id": user.id
        }

        response = self._cancel_deal(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST
        assert response.json["detail"] == "400 Bad Request: no such deal"

    def test_cancel_deal_wrong_user_invalid(
            self, client: FlaskClient, token: str, user: UserDTO, wallet: WalletDTO, deal: DealDTO
    ):
        data = {
            "deal_id": deal.identificator,
            "user_id": deal.buyer_id + deal.seller_id
        }

        response = self._cancel_deal(client, data, token)
        assert response.status == self.HttpStatus.FORBIDDEN

    def test_cancel_deal_closed_status_invalid(
            self, client: FlaskClient, token: str, user: UserDTO, wallet: WalletDTO, deal: DealDTO, db_session: Session
    ):
        data = {
            "deal_id": deal.identificator,
            "user_id": user.id
        }
        self._update_deal({"state": "closed"}, deal.id, db_session)

        response = self._cancel_deal(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST

    def test_cancel_deal_deleted_status_invalid(
            self, client: FlaskClient, token: str, user: UserDTO, wallet: WalletDTO, deal: DealDTO, db_session: Session
    ):
        data = {
            "deal_id": deal.identificator,
            "user_id": user.id
        }
        self._update_deal({"state": "deleted"}, deal.id, db_session)

        response = self._cancel_deal(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST

    def test_cancel_deal_paid_invalid(
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
            "user_id": user.id
        }

        self._update_deal({"state": "paid"}, deal.id, db_session)

        response = self._cancel_deal(client, data, token)
        assert response.status == self.HttpStatus.FORBIDDEN

    def test_cancel_deal_paid_with_dispute_valid(
            self,
            client: FlaskClient,
            token: str,
            user: UserDTO,
            wallet: WalletDTO,
            deal: DealDTO,
            dispute: DisputeDTO,
            db_session: Session,
    ):
        data = {
            "deal_id": deal.identificator,
            "user_id": deal.buyer_id
        }

        self._update_deal({"state": "paid"}, deal.id, db_session)
        self._update_wallet({"frozen": deal.amount_subunit_frozen}, wallet.id, db_session)

        with patch("utils.notifications_queue._send_queue_notification"):
            response = self._cancel_deal(client, data, token)
            assert response.status == self.HttpStatus.OK
            assert response.json == {"success": "deal canceled"}

    def test_cancel_deal_confirmed_with_requisite_invalid(
            self, client: FlaskClient, token: str, user: UserDTO, wallet: WalletDTO, deal: DealDTO, db_session: Session
    ):
        data = {
            "deal_id": deal.identificator,
            "user_id": user.id
        }

        self._update_deal({"state": "confirmed"}, deal.id, db_session)

        response = self._cancel_deal(client, data, token)
        assert response.status == self.HttpStatus.FORBIDDEN

    def test_cancel_deal_confirmed_with_requisite_by_buyer_valid(
            self, client: FlaskClient, token: str, user: UserDTO, wallet: WalletDTO, deal: DealDTO, db_session: Session
    ):
        data = {
            "deal_id": deal.identificator,
            "user_id": deal.buyer_id
        }

        self._update_deal({"state": "confirmed"}, deal.id, db_session)
        self._update_wallet({"frozen": deal.amount_subunit_frozen}, wallet.id, db_session)

        with patch("utils.notifications_queue._send_queue_notification"):
            response = self._cancel_deal(client, data, token)
            assert response.status == self.HttpStatus.OK
            assert response.json == {"success": "deal canceled"}