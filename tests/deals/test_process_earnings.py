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
    merchant_table, MerchantDTO


class TestProcessEarnings(AbstractDealTest):
    def _update_deal_state(self, client: FlaskClient, data: dict, token: str) -> Response:
        response = self._make_patch_request(client, "/deal-state", token, data)
        return response

    def test_process_deal_plain_type_valid(
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
        self._update_deal({"type": DealTypes.plain, "state": "paid"}, deal.id, db_session)

        self._update_wallet({"frozen": deal.amount_subunit_frozen}, wallet.id, db_session)
        buyer_wallet = wallet_factory(deal.buyer_id, Decimal("10000000000.0"))

        data = {
            "deal_id": deal.identificator,
            "user_id": deal.seller_id
        }

        with patch("utils.notifications_queue._send_queue_notification"):
            response = self._update_deal_state(client, data, token)
            assert response.status == self.HttpStatus.OK
            assert response.json == {"success": "deal processed"}

        refresh_seller_wallet = self._select_wallet(wallet.id, db_session)
        assert refresh_seller_wallet.frozen == 0

        to_balance = deal.amount_subunit - deal.buyer_commission_subunits
        refresh_buyer_wallet = self._select_wallet(buyer_wallet.id, db_session)
        assert refresh_buyer_wallet.balance == buyer_wallet.balance + to_balance

        refresh_deal = self._select_deal(deal.id, db_session)
        assert refresh_deal.state == "closed"

        seller_operation = self._select_operation(deal.identificator, deal.seller_id, db_session)
        assert seller_operation.user_id == deal.seller_id
        assert seller_operation.amount == -self._to_unit_usdt(deal.amount_subunit_frozen)
        assert seller_operation.action == Action.deal

        buyer_operation = self._select_operation(deal.identificator, deal.buyer_id, db_session)
        assert buyer_operation.user_id == deal.buyer_id
        assert buyer_operation.amount == self._to_unit_usdt(to_balance)
        assert buyer_operation.action == Action.deal

        deal_commissions = self._select_deal_commissions(deal.id, db_session)
        assert deal_commissions.deal_id == deal.id
        assert deal_commissions.buyer_commission == deal.buyer_commission_subunits
        assert deal_commissions.seller_commission == deal.seller_commission_subunits
        assert deal_commissions.merchant_commission == 0

    def test_process_deal_fast_type_valid(
            self,
            client: FlaskClient,
            token: str,
            user: UserDTO,
            wallet: WalletDTO,
            wallet_factory: Callable[..., WalletDTO],
            deal: DealDTO,
            dispute: DisputeDTO,
            crypto_settings_usdt: CryptoSettingsDTO,
            base_deal_time_settings: SettingsDTO,
            advanced_deal_time_settings: SettingsDTO,
            db_session: Session
    ):
        address = "TF8ndsFDyUmDi8mgqx61RuxTiW75NRb4UD"
        self._update_deal({"type": DealTypes.fast, "state": "paid", "address": address}, deal.id, db_session)

        self._update_wallet({"frozen": deal.amount_subunit_frozen}, wallet.id, db_session)
        buyer_wallet = wallet_factory(deal.buyer_id, Decimal("10000000000.0"))

        data = {
            "deal_id": deal.identificator,
            "user_id": deal.seller_id
        }

        with patch("utils.notifications_queue._send_queue_notification"):
            response = self._update_deal_state(client, data, token)
            assert response.status == self.HttpStatus.OK
            assert response.json == {"success": "deal processed"}

        refresh_seller_wallet = self._select_wallet(wallet.id, db_session)
        assert refresh_seller_wallet.frozen == 0

        to_balance = deal.amount_subunit - deal.buyer_commission_subunits
        refresh_buyer_wallet = self._select_wallet(buyer_wallet.id, db_session)
        assert refresh_buyer_wallet.frozen == to_balance

        operation = self._select_operation(deal.identificator, deal.seller_id, db_session)
        assert operation.user_id == deal.seller_id
        assert operation.amount == -self._to_unit_usdt(deal.amount_subunit_frozen)
        assert operation.action == Action.deal

        deal_commissions = self._select_deal_commissions(deal.id, db_session)
        assert deal_commissions.deal_id == deal.id
        assert deal_commissions.buyer_commission == deal.buyer_commission_subunits
        assert deal_commissions.seller_commission == deal.seller_commission_subunits
        assert deal_commissions.merchant_commission == 0

        transaction = self._select_transaction(buyer_wallet.id, db_session)
        assert transaction.to_address == address
        assert transaction.type == "out"
        assert transaction.amount_units == self._to_unit_usdt(to_balance) - Decimal(crypto_settings_usdt.tx_out_commission)

    def test_process_deal_sky_pay_type_with_address_valid(
            self,
            client: FlaskClient,
            token: str,
            user: UserDTO,
            wallet: WalletDTO,
            wallet_factory: Callable[..., WalletDTO],
            deal: DealDTO,
            dispute: DisputeDTO,
            crypto_settings_usdt: CryptoSettingsDTO,
            base_deal_time_settings: SettingsDTO,
            advanced_deal_time_settings: SettingsDTO,
            usdt_commission_5,
            usdt_rate: RateDTO,
            db_session: Session
    ):
        payment_id = "123e4567-e89b-12d3-a456-426655440000"
        self._update_deal({"type": DealTypes.sky_pay, "state": "paid", "payment_id": payment_id}, deal.id, db_session)

        self._update_wallet({"frozen": deal.amount_subunit_frozen}, wallet.id, db_session)
        buyer_wallet = wallet_factory(deal.buyer_id, Decimal("10000000000.0"))

        data = {
            "deal_id": deal.identificator,
            "user_id": deal.seller_id
        }
        address = "TF8ndsFDyUmDi8mgqx61RuxTiW75NRb4UD"
        purchase_value = {
            "merchant_id": deal.seller_id,
            "address": address,
            "is_currency_amount": True,
            "amount": deal.amount_currency,
            "label": "label"
        }

        with patch(
                "utils.notifications_queue._send_queue_notification"
        ), patch(
            "utils.utils._get_purchase", return_value=purchase_value
        ),patch(
            "utils.utils._complete_purchase"
        ):
            response = self._update_deal_state(client, data, token)
            assert response.status == self.HttpStatus.OK
            assert response.json == {"success": "deal processed"}

        to_balance = deal.amount_subunit - deal.buyer_commission_subunits
        refresh_buyer_wallet = self._select_wallet(buyer_wallet.id, db_session)
        assert refresh_buyer_wallet.frozen == to_balance

        transaction = self._select_transaction(buyer_wallet.id, db_session)
        assert transaction.to_address == address
        assert transaction.type == "out"
        assert transaction.amount_units == self._to_unit_usdt(to_balance) - Decimal(usdt_commission_5.value)

        operation = self._select_operation(payment_id, deal.seller_id, db_session)
        assert operation.user_id == deal.seller_id
        assert operation.amount == self._to_unit_usdt(to_balance) - Decimal(usdt_commission_5.value)
        assert operation.action == Action.sky_pay

        deal_commissions = self._select_deal_commissions(deal.id, db_session)
        assert deal_commissions.deal_id == deal.id
        assert deal_commissions.buyer_commission == deal.buyer_commission_subunits
        assert deal_commissions.seller_commission == deal.seller_commission_subunits
        assert deal_commissions.merchant_commission == Decimal(usdt_commission_5.value)

    def test_process_deal_sky_pay_type_without_address_valid(
            self,
            client: FlaskClient,
            token: str,
            user: UserDTO,
            wallet: WalletDTO,
            wallet_factory: Callable[..., WalletDTO],
            deal: DealDTO,
            dispute: DisputeDTO,
            crypto_settings_usdt: CryptoSettingsDTO,
            base_deal_time_settings: SettingsDTO,
            advanced_deal_time_settings: SettingsDTO,
            usdt_commission_5,
            usdt_rate: RateDTO,
            db_session: Session
    ):
        payment_id = "123e4567-e89b-12d3-a456-426655440000"
        self._update_deal({"type": DealTypes.sky_pay, "state": "paid", "payment_id": payment_id}, deal.id, db_session)

        self._update_wallet({"frozen": deal.amount_subunit_frozen}, wallet.id, db_session)
        wallet_factory(deal.buyer_id, Decimal("10000000000.0"))

        data = {
            "deal_id": deal.identificator,
            "user_id": deal.seller_id
        }
        purchase_value = {
            "merchant_id": deal.seller_id,
            "address": None,
            "is_currency_amount": True,
            "amount": deal.amount_currency,
            "label": "label"
        }

        with patch(
                "utils.notifications_queue._send_queue_notification"
        ), patch(
            "utils.utils._get_purchase", return_value=purchase_value
        ), patch(
            "utils.utils._complete_purchase"
        ):
            response = self._update_deal_state(client, data, token)
            assert response.status == self.HttpStatus.OK
            assert response.json == {"success": "deal processed"}

        to_balance = deal.amount_subunit - deal.buyer_commission_subunits
        refresh_seller_wallet = self._select_wallet(wallet.id, db_session)
        assert refresh_seller_wallet.balance == wallet.balance + (to_balance) - Decimal(usdt_commission_5.value) * 10**6

        operation = self._select_operation(payment_id, deal.seller_id, db_session)
        assert operation.user_id == deal.seller_id
        assert operation.amount == self._to_unit_usdt(to_balance) - Decimal(usdt_commission_5.value)
        assert operation.action == Action.sky_pay

        deal_commissions = self._select_deal_commissions(deal.id, db_session)
        assert deal_commissions.deal_id == deal.id
        assert deal_commissions.buyer_commission == deal.buyer_commission_subunits
        assert deal_commissions.seller_commission == deal.seller_commission_subunits
        assert deal_commissions.merchant_commission == Decimal(usdt_commission_5.value)

    def test_process_deal_sky_pay_v2_type_valid(
            self,
            client: FlaskClient,
            token: str,
            user: UserDTO,
            wallet: WalletDTO,
            wallet_factory: Callable[..., WalletDTO],
            deal: DealDTO,
            dispute: DisputeDTO,
            usdt_commission_5: SettingsDTO,
            merchant: MerchantDTO,
            usdt_rate: RateDTO,
            db_session: Session
    ):
        payment_v2_id = "123e4567-e89b-12d3-a456-426655440000"
        self._update_deal({"type": DealTypes.sky_pay_v2, "state": "paid", "payment_v2_id": payment_v2_id}, deal.id, db_session)

        self._update_wallet({"frozen": deal.amount_subunit_frozen}, wallet.id, db_session)
        wallet_factory(deal.buyer_id, Decimal("10000000000.0"))

        data = {
            "deal_id": deal.identificator,
            "user_id": deal.seller_id
        }

        payment_v2_value = {
            "merchant_id": deal.seller_id,
            "is_currency_amount": True,
            "amount": deal.amount_currency,
            "label": "label"
        }

        with patch(
                "utils.notifications_queue._send_queue_notification"
        ), patch(
            "utils.utils._get_payment_v2", return_value=payment_v2_value
        ), patch(
            "utils.utils._complete_payment_v2"
        ):
            response = self._update_deal_state(client, data, token)
            assert response.status == self.HttpStatus.OK
            assert response.json == {"success": "deal processed"}

        to_balance = deal.amount_subunit - deal.buyer_commission_subunits
        refresh_seller_wallet = self._select_wallet(wallet.id, db_session)
        assert refresh_seller_wallet.balance == wallet.balance + to_balance - to_balance * merchant.commission

        operation = self._select_operation(payment_v2_id, deal.seller_id, db_session)
        assert operation.user_id == deal.seller_id
        assert operation.amount == self._to_unit_usdt(to_balance - to_balance * merchant.commission)
        assert operation.action == Action.sky_pay_v2
        assert operation.commission_currency == payment_v2_value["amount"] * merchant.commission

        deal_commissions = self._select_deal_commissions(deal.id, db_session)
        assert deal_commissions.deal_id == deal.id
        assert deal_commissions.buyer_commission == deal.buyer_commission_subunits
        assert deal_commissions.seller_commission == deal.seller_commission_subunits
        assert deal_commissions.merchant_commission == 0

    def test_process_deal_sky_sale_type_valid(
            self,
            client: FlaskClient,
            token: str,
            user: UserDTO,
            wallet: WalletDTO,
            wallet_factory: Callable[..., WalletDTO],
            deal: DealDTO,
            dispute: DisputeDTO,
            usdt_commission_5: SettingsDTO,
            merchant: MerchantDTO,
            usdt_rate: RateDTO,
            db_session: Session
    ):
        sell_id = "123e4567-e89b-12d3-a456-426655440000"
        self._update_deal({"type": DealTypes.sky_sale, "state": "paid", "sell_id": sell_id}, deal.id, db_session)

        self._update_wallet({"frozen": deal.amount_subunit_frozen}, wallet.id, db_session)
        buyer_wallet = wallet_factory(deal.buyer_id, Decimal("10000000000.0"))

        data = {
            "deal_id": deal.identificator,
            "user_id": deal.seller_id
        }

        sell_value = {
            "merchant_id": deal.seller_id,
        }

        with patch(
                "utils.notifications_queue._send_queue_notification"
        ), patch(
            "utils.utils._get_sell", return_value=sell_value
        ), patch(
            "utils.utils._complete_sell"
        ):
            response = self._update_deal_state(client, data, token)
            assert response.status == self.HttpStatus.OK
            assert response.json == {"success": "deal processed"}

        to_balance = deal.amount_subunit - deal.buyer_commission_subunits
        refresh_buyer_wallet = self._select_wallet(buyer_wallet.id, db_session)
        assert refresh_buyer_wallet.balance == buyer_wallet.balance + to_balance

        refresh_seller_wallet = self._select_wallet(wallet.id, db_session)
        assert refresh_seller_wallet.balance == 0

        operation = self._select_operation(deal.identificator, deal.buyer_id, db_session)
        assert operation.user_id == deal.buyer_id
        assert operation.amount == self._to_unit_usdt(to_balance)
        assert operation.action == Action.deal

        deal_commissions = self._select_deal_commissions(deal.id, db_session)
        assert deal_commissions.deal_id == deal.id
        assert deal_commissions.buyer_commission == deal.buyer_commission_subunits
        assert deal_commissions.seller_commission == deal.seller_commission_subunits
        assert deal_commissions.merchant_commission == 0

    def test_process_deal_sky_sale_type_zero_balance_valid(
            self,
            client: FlaskClient,
            token: str,
            user: UserDTO,
            wallet: WalletDTO,
            wallet_factory: Callable[..., WalletDTO],
            deal: DealDTO,
            dispute: DisputeDTO,
            usdt_commission_5: SettingsDTO,
            merchant: MerchantDTO,
            usdt_rate: RateDTO,
            db_session: Session
    ):
        sell_id = "123e4567-e89b-12d3-a456-426655440000"
        self._update_deal({"type": DealTypes.sky_sale, "state": "paid", "sell_id": sell_id}, deal.id, db_session)

        new_balance = 0
        self._update_wallet({"frozen": deal.amount_subunit_frozen, "balance": new_balance}, wallet.id, db_session)
        buyer_wallet = wallet_factory(deal.buyer_id, Decimal("10000000.0"))

        data = {
            "deal_id": deal.identificator,
            "user_id": deal.seller_id
        }

        sell_value = {
            "merchant_id": deal.seller_id,
        }

        with patch(
                "utils.notifications_queue._send_queue_notification"
        ), patch(
            "utils.utils._get_sell", return_value=sell_value
        ), patch(
            "utils.utils._complete_sell"
        ):
            response = self._update_deal_state(client, data, token)
            assert response.status == self.HttpStatus.OK
            assert response.json == {"success": "deal processed"}

        to_balance = deal.amount_subunit - deal.buyer_commission_subunits
        refresh_buyer_wallet = self._select_wallet(buyer_wallet.id, db_session)
        assert refresh_buyer_wallet.balance == buyer_wallet.balance + to_balance

        refresh_seller_wallet = self._select_wallet(wallet.id, db_session)
        assert refresh_seller_wallet.balance == new_balance

        operation = self._select_operation(deal.identificator, deal.buyer_id, db_session)
        assert operation.user_id == deal.buyer_id
        assert operation.amount == self._to_unit_usdt(to_balance)
        assert operation.action == Action.deal

        deal_commissions = self._select_deal_commissions(deal.id, db_session)
        assert deal_commissions.deal_id == deal.id
        assert deal_commissions.buyer_commission == deal.buyer_commission_subunits
        assert deal_commissions.seller_commission == deal.seller_commission_subunits
        assert deal_commissions.merchant_commission == 0

    def test_process_deal_sky_sale_v2_type_valid(
            self,
            client: FlaskClient,
            token: str,
            user: UserDTO,
            wallet: WalletDTO,
            wallet_factory: Callable[..., WalletDTO],
            deal: DealDTO,
            dispute: DisputeDTO,
            usdt_commission_5: SettingsDTO,
            merchant: MerchantDTO,
            usdt_rate: RateDTO,
            db_session: Session
    ):
        sale_v2_id = "123e4567-e89b-12d3-a456-426655440000"
        self._update_deal({"type": DealTypes.sky_sale_v2, "state": "paid", "sale_v2_id": sale_v2_id}, deal.id, db_session)

        self._update_wallet({"frozen": deal.amount_subunit_frozen}, wallet.id, db_session)
        buyer_wallet = wallet_factory(deal.buyer_id, Decimal("10000000000.0"))

        data = {
            "deal_id": deal.identificator,
            "user_id": deal.seller_id
        }

        with patch(
                "utils.notifications_queue._send_queue_notification"
        ), patch(
            "utils.utils._complete_sale_v2"
        ):
            response = self._update_deal_state(client, data, token)
            assert response.status == self.HttpStatus.OK
            assert response.json == {"success": "deal processed"}

        to_balance = deal.amount_subunit - deal.buyer_commission_subunits
        commission = merchant.commission * to_balance
        refresh_seller_wallet = self._select_wallet(wallet.id, db_session)
        assert refresh_seller_wallet.frozen == 0
        assert refresh_seller_wallet.balance == wallet.balance - commission

        refresh_buyer_wallet = self._select_wallet(buyer_wallet.id, db_session)
        assert refresh_buyer_wallet.balance == buyer_wallet.balance + to_balance

        buyer_operation = self._select_operation(deal.identificator, deal.buyer_id, db_session)
        assert buyer_operation.user_id == deal.buyer_id
        assert buyer_operation.amount == self._to_unit_usdt(to_balance)
        assert buyer_operation.action == Action.deal

        seller_operation = self._select_operation(sale_v2_id, deal.seller_id, db_session)
        assert seller_operation.user_id == deal.seller_id
        assert seller_operation.amount == -self._to_unit_usdt(to_balance + commission)
        assert seller_operation.action == Action.sky_sale_v2

        deal_commissions = self._select_deal_commissions(deal.id, db_session)
        assert deal_commissions.deal_id == deal.id
        assert deal_commissions.buyer_commission == deal.buyer_commission_subunits
        assert deal_commissions.seller_commission == deal.seller_commission_subunits
        assert deal_commissions.merchant_commission == self._to_unit_usdt(commission)