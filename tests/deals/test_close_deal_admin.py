from typing import Callable
from unittest.mock import patch

from _decimal import Decimal
from flask import Response
from flask.testing import FlaskClient

from system.constants import Action
from system.settings import Session
from tests.deals.abstract_deal_test import AbstractDealTest
from utils.tables import UserDTO, WalletDTO, wallets_table, DealDTO, deals_table, DisputeDTO, disputes_table, LotDTO


class TestCancelDealAdmin(AbstractDealTest):
    def _cancel_deal_admin(self, client: FlaskClient, data: dict, token: str) -> Response:
        response = self._make_post_request(client, "/close-deal-admin", token, data)
        return response

    def test_cancel_deal_admin_seller_winner_valid(
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
            "winner": "seller"
        }

        self._update_wallet({"frozen": deal.amount_subunit_frozen}, wallet.id, db_session)

        with patch("utils.notifications_queue._send_queue_notification"):
            response = self._cancel_deal_admin(client, data, token)
            assert response.status == self.HttpStatus.OK
            assert response.json == {"success": "deal canceled"}

        refresh_wallet = self._select_wallet(wallet.id, db_session)
        assert refresh_wallet.frozen == 0

        refresh_deal = self._select_deal(deal.id, db_session)
        assert refresh_deal.state == "deleted"

        refresh_dispute = self._select_dispute(dispute.id, db_session)
        assert refresh_dispute.is_closed is True

    def test_cancel_deal_admin_buyer_winner_valid(
            self,
            client: FlaskClient,
            token: str,
            user: UserDTO,
            wallet: WalletDTO,
            wallet_factory: Callable[..., WalletDTO],
            deal: DealDTO,
            dispute: DisputeDTO,
            db_session: Session
    ):
        self._update_wallet({"frozen": deal.amount_subunit_frozen}, wallet.id, db_session)
        buyer_wallet = wallet_factory(deal.buyer_id, Decimal("10000000000.0"))
        data = {
            "deal_id": deal.identificator,
            "winner": "buyer"
        }

        with patch("utils.notifications_queue._send_queue_notification"):
            response = self._cancel_deal_admin(client, data, token)
            assert response.status == self.HttpStatus.OK
            assert response.json == {"success": "deal canceled"}

        refresh_seller_wallet = self._select_wallet(wallet.id, db_session)
        assert refresh_seller_wallet.frozen == 0

        refresh_buyer_wallet = self._select_wallet(buyer_wallet.id, db_session)
        assert refresh_buyer_wallet.balance == buyer_wallet.balance + deal.amount_subunit

        refresh_dispute = self._select_dispute(dispute.id, db_session)
        assert refresh_dispute.is_closed is True

        refresh_deal = self._select_deal(deal.id, db_session)
        assert refresh_deal.state == "closed"

        operation = self._select_operation(deal.identificator, deal.seller_id, db_session)
        assert operation.user_id == deal.seller_id
        assert operation.amount * 10**6 == Decimal(-deal.amount_subunit_frozen)
        assert operation.action == Action.deal

    def test_cancel_deal_admin_wrong_winner_invalid(
            self,
            client: FlaskClient,
            token: str,
            user: UserDTO,
            wallet: WalletDTO,
            wallet_factory: Callable[..., WalletDTO],
            deal: DealDTO,
            dispute: DisputeDTO,
            db_session: Session
    ):
        data = {
            "deal_id": deal.identificator,
            "winner": "winner"
        }

        response = self._cancel_deal_admin(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST
