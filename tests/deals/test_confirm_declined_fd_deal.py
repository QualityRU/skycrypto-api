from typing import Callable
from unittest.mock import patch

from _decimal import Decimal
from flask import Response
from flask.testing import FlaskClient

from system.constants import DealTypes
from system.settings import Session
from tests.deals.abstract_deal_test import AbstractDealTest
from utils.tables import WalletDTO, DealDTO, DisputeDTO


class TestConfirmDeclinedFdDeal(AbstractDealTest):
    def _confirm_declined_fd_deal(self, client: FlaskClient, data: dict, token: str) -> Response:
        response = self._make_post_request(client, "/fd-deal-confirm", token, data)
        return response

    def test_confirm_declined_fd_deal_valid(
            self,
            client: FlaskClient,
            token: str,
            wallet: WalletDTO,
            deal: DealDTO,
            wallet_factory: Callable[..., WalletDTO],
            dispute: DisputeDTO,
            db_session: Session
    ):

        data = {
            "user_id": deal.seller_id,
            "deal_id": deal.identificator
        }
        wallet_factory(deal.buyer_id, Decimal("100000000000"))
        self._update_deal({"state": "deleted"}, deal.id, db_session)

        with patch("utils.notifications_queue._send_queue_notification"):
            response = self._confirm_declined_fd_deal(client, data, token)
            assert response.status == self.HttpStatus.OK
            assert response.json == {"success": "deal processed"}

        refresh_wallet = self._select_wallet(wallet.id, db_session)
        assert refresh_wallet.frozen == 0

        refresh_deal = self._select_deal(deal.id, db_session)
        assert refresh_deal.state == "closed"

        refresh_dispute = self._select_dispute(dispute.id, db_session)
        assert refresh_dispute.is_closed is True

    def test_confirm_declined_fd_deal_not_deleted_invalid(
            self, client: FlaskClient, token: str, wallet: WalletDTO, deal: DealDTO, db_session: Session
    ):

        data = {
            "user_id": deal.seller_id,
            "deal_id": deal.identificator
        }
        response = self._confirm_declined_fd_deal(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST
        assert response.json["detail"] == "400 Bad Request: error while confirm deal"

    def test_confirm_declined_fd_deal_wrong_deal_type_invalid(
            self, client: FlaskClient, token: str, wallet: WalletDTO, deal: DealDTO, db_session: Session
    ):

        data = {
            "user_id": deal.seller_id,
            "deal_id": deal.identificator
        }
        self._update_deal({"type": DealTypes.fast, "state": "deleted"}, deal.id, db_session)

        response = self._confirm_declined_fd_deal(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST
        assert response.json["detail"] == "400 Bad Request: error while confirm deal"

    def test_confirm_declined_fd_deal_wrong_seller_id_invalid(
            self, client: FlaskClient, token: str, wallet: WalletDTO, deal: DealDTO, db_session: Session
    ):

        data = {
            "user_id": deal.buyer_id,
            "deal_id": deal.identificator
        }
        self._update_deal({"state": "deleted"}, deal.id, db_session)

        response = self._confirm_declined_fd_deal(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST
        assert response.json["detail"] == "400 Bad Request: error while confirm deal"

    def test_confirm_declined_fd_deal_no_requisite_invalid(
            self, client: FlaskClient, token: str, wallet: WalletDTO, deal: DealDTO, db_session: Session
    ):

        data = {
            "user_id": deal.seller_id,
            "deal_id": deal.identificator
        }
        self._update_deal({"state": "deleted", "requisite": ""}, deal.id, db_session)

        response = self._confirm_declined_fd_deal(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST
        assert response.json["detail"] == "400 Bad Request: error while confirm deal"

    def test_confirm_declined_fd_deal_none_data_invalid(
            self, client: FlaskClient, token: str,  deal: DealDTO,
    ):
        data = {
            "user_id": deal.seller_id,
        }

        response = self._confirm_declined_fd_deal(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST

        data = {
            "deal_id": deal.identificator,
        }

        response = self._confirm_declined_fd_deal(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST

