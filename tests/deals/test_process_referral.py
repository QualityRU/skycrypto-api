from typing import Callable
from unittest.mock import patch

from _decimal import Decimal
from flask import Response
from flask.testing import FlaskClient
from sqlalchemy import insert

from data_handler import DataHandler
from system.constants import Action, DealTypes
from system.settings import Session
from tests.deals.abstract_deal_test import AbstractDealTest
from utils.tables import UserDTO, DealDTO, WalletDTO, DisputeDTO, CryptoSettingsDTO, SettingsDTO, RateDTO, \
    merchant_table, MerchantDTO, CommissionDTO


class TestProcessReferral(AbstractDealTest):
    def _update_deal_state(self, client: FlaskClient, data: dict, token: str) -> Response:
        response = self._make_patch_request(client, "/deal-state", token, data)
        return response

    def test_process_referral_valid(
            self,
            client: FlaskClient,
            token: str,
            user_factory: Callable[..., UserDTO],
            wallet_factory: Callable[..., WalletDTO],
            wallet: WalletDTO,
            deal: DealDTO,
            user: UserDTO,
            buyer_referral_commission_usdt: CommissionDTO,
            db_session: Session
    ):

        buyer = self._select_user(deal.buyer_id, db_session)
        buyer_ref = user_factory()

        buyer_ref_wallet = wallet_factory(buyer_ref.id, Decimal("100000"))
        buyer_wallet = wallet_factory(deal.buyer_id, Decimal("10000000000.0"), referred_from_id=buyer_ref.id)
        self._update_wallet({"frozen": deal.amount_subunit_frozen}, wallet.id, db_session)

        buyer_commission_subunits = Decimal("100")
        self._update_deal({"state": "paid", "buyer_commission_subunits": Decimal("100")}, deal.id, db_session)

        data = {
            "deal_id": deal.identificator,
            "user_id": deal.seller_id
        }

        with patch("utils.notifications_queue._send_queue_notification"):
            response = self._update_deal_state(client, data, token)
            assert response.status == self.HttpStatus.OK
            assert response.json == {"success": "deal processed"}

        ref_commission = buyer_commission_subunits * buyer_referral_commission_usdt.commission
        buyer_ref_refresh_wallet = self._select_wallet(buyer_ref_wallet.id, db_session)
        assert buyer_ref_refresh_wallet.balance == buyer_ref_wallet.balance + ref_commission
        assert buyer_ref_refresh_wallet.earned_from_ref == ref_commission

        operation = self._select_operation(buyer.nickname, buyer_ref.id, db_session)
        assert operation.user_id == buyer_ref.id
        assert operation.amount == self._to_unit_usdt(ref_commission)
        assert operation.action == Action.referral

        refresh_deal = self._select_deal(deal.id, db_session)
        assert refresh_deal.referral_commission_buyer_subunits == ref_commission

        deal_commission = self._select_deal_commissions(deal.id, db_session)
        assert deal_commission.referral_commission_buyer == self._to_unit_usdt(ref_commission)

        notification = self._select_notification(buyer_ref.id, db_session)
        assert notification.user_id == buyer_ref.id
        assert notification.deal_id == deal.id
