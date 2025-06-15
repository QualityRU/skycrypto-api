import jwt
from _decimal import Decimal
from flask import Response
from flask.testing import FlaskClient
from sqlalchemy import exists, select, update

from system.settings import Session
from tests.abstract_test import AbstractAPITest
from utils.db import mapping_result_to_dto
from utils.tables import (
    UserDTO,
    RateDTO,
    CryptoSettingsDTO,
    SettingsDTO,
    WalletDTO,
    transactions_table,
    users_table,
)
from system.settings import app as app_settings
from unittest.mock import patch


class TestCreateWithdrawal(AbstractAPITest):
    def _create_withdrawal(self, client: FlaskClient, data: dict, token: str) -> Response:
        response = self._make_post_request(client, "/send-transaction", token, data)
        return response

    def test_create_withdrawal_valid(
            self,
            client: FlaskClient,
            token: str,
            user: UserDTO,
            usdt_rate: RateDTO,
            wallet: WalletDTO,
            crypto_settings_usdt,
            advanced_deal_time_settings: SettingsDTO,
            base_deal_time_settings: SettingsDTO,
            usdt_commission_5,
            db_session: Session,
    ):
        amount = 7
        address = "TF8ndsFDyUmDi8mgqx61RuxTiW75NRb4UD"
        data = {
            "user_id": user.id,
            "address": address,
            "amount": amount,
        }

        response = self._create_withdrawal(client, data, token)
        assert response.status == self.HttpStatus.OK
        assert response.json["success"] == "transaction created"

        transaction = self._select_transaction(wallet.id, db_session)
        assert transaction.wallet_id == wallet.id
        assert transaction.to_address == address
        assert transaction.amount_units == amount

        refresh_wallet = self._select_wallet(wallet.id, db_session)
        assert self._to_unit_usdt(refresh_wallet.frozen) == amount + int(usdt_commission_5.value)

    def test_create_withdrawal_wrong_amount_invalid(
            self,
            client: FlaskClient,
            token: str,
            user: UserDTO,
            usdt_rate: RateDTO,
            wallet: WalletDTO,
            crypto_settings_usdt,
            advanced_deal_time_settings: SettingsDTO,
            base_deal_time_settings: SettingsDTO,
            usdt_commission_5,
    ):
        data = {
            "user_id": user.id,
            "address": "TF8ndsFDyUmDi8mgqx61RuxTiW75NRb4UD",
            "amount": "1.111111111111111111111",
        }

        response = self._create_withdrawal(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST
        assert response.json["detail"] == "400 Bad Request: Wrong amount"

    def test_create_withdrawal_wrong_limit_invalid(
            self,
            client: FlaskClient,
            token: str,
            user: UserDTO,
            usdt_rate: RateDTO,
            wallet: WalletDTO,
            crypto_settings_usdt,
            advanced_deal_time_settings: SettingsDTO,
            base_deal_time_settings: SettingsDTO,
            usdt_commission_5,
    ):
        data = {
            "user_id": user.id,
            "address": "TF8ndsFDyUmDi8mgqx61RuxTiW75NRb4UD",
            "amount": "1000000000",
        }

        response = self._create_withdrawal(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST
        assert response.json["detail"] == "400 Bad Request: Amount is more than limit"

    def test_create_withdrawal_baned_user_invalid(
            self,
            client: FlaskClient,
            token: str,
            user: UserDTO,
            usdt_rate: RateDTO,
            wallet: WalletDTO,
            crypto_settings_usdt,
            advanced_deal_time_settings: SettingsDTO,
            base_deal_time_settings: SettingsDTO,
            usdt_commission_5,
            db_session: Session,
    ):
        data = {
            "user_id": user.id,
            "address": "TF8ndsFDyUmDi8mgqx61RuxTiW75NRb4UD",
            "amount": "7",
        }

        self._update_user({"is_baned": True}, user.id, db_session)

        response = self._create_withdrawal(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST
        assert response.json["detail"] == "400 Bad Request: user is baned"

    def test_create_withdrawal_wrong_address_invalid(
            self,
            client: FlaskClient,
            token: str,
            user: UserDTO,
            usdt_rate: RateDTO,
            wallet: WalletDTO,
            crypto_settings_usdt,
            advanced_deal_time_settings: SettingsDTO,
            base_deal_time_settings: SettingsDTO,
            usdt_commission_5,
    ):
        data = {
            "user_id": user.id,
            "address": "2",
            "amount": "7",
        }

        response = self._create_withdrawal(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST
        assert response.json["detail"] == "400 Bad Request: Address not valid"

    def test_create_withdrawal_less_than_min_amount_invalid(
            self,
            client: FlaskClient,
            token: str,
            user: UserDTO,
            usdt_rate: RateDTO,
            wallet: WalletDTO,
            crypto_settings_usdt,
            advanced_deal_time_settings: SettingsDTO,
            base_deal_time_settings: SettingsDTO,
            usdt_commission_5,
    ):
        data = {
            "user_id": user.id,
            "address": "TF8ndsFDyUmDi8mgqx61RuxTiW75NRb4UD",
            "amount": 1,
        }

        response = self._create_withdrawal(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST
        assert response.json["detail"] == "400 Bad Request: Wrong amount"

    def test_create_withdrawal_not_enough_founds_invalid(
            self,
            client: FlaskClient,
            token: str,
            user: UserDTO,
            usdt_rate: RateDTO,
            wallet: WalletDTO,
            crypto_settings_usdt,
            advanced_deal_time_settings: SettingsDTO,
            base_deal_time_settings: SettingsDTO,
            usdt_commission_5,
    ):
        data = {
            "user_id": user.id,
            "address": "TF8ndsFDyUmDi8mgqx61RuxTiW75NRb4UD",
            "amount": 10000,
        }

        response = self._create_withdrawal(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST
        assert response.json["detail"] == "400 Bad Request: not enough funds"

    def test_create_withdrawal_limit_reached_btc_invalid(
            self,
            client: FlaskClient,
            user: UserDTO,
            btc_rate: RateDTO,
            wallet: WalletDTO,
            crypto_settings_btc: CryptoSettingsDTO,
            advanced_deal_time_settings: SettingsDTO,
            base_deal_time_settings: SettingsDTO,
            btc_commission_0001,
            wallet_factory
    ):
        wallet_factory(user.id, Decimal("10000000000.0"), "btc")
        data = {
            "user_id": user.id,
            "address": "tb1qp3maew7ys9wzctqpe8yvv9qhfqxvaaqqh6xlyp",
            "amount": 0.0003,
        }

        token = jwt.encode({"symbol": "btc"}, key=app_settings.secret_key, algorithm='HS256').decode()
        with patch("crypto.manager.Manager.is_address_valid", return_value=True):
            response = self._create_withdrawal(client, data, token)
            assert response.status == self.HttpStatus.OK

            response = self._create_withdrawal(client, data, token)
            assert response.status == self.HttpStatus.CONFLICT

    def test_create_withdrawal_limit_reached_usdt_invalid(
            self,
            client: FlaskClient,
            token: str,
            user: UserDTO,
            usdt_rate: RateDTO,
            wallet: WalletDTO,
            crypto_settings_usdt,
            advanced_deal_time_settings: SettingsDTO,
            base_deal_time_settings: SettingsDTO,
            usdt_commission_5,
            db_session: Session,
    ):
        data = {
            "user_id": user.id,
            "address": "TF8ndsFDyUmDi8mgqx61RuxTiW75NRb4UD",
            "amount": 7,
        }

        response = self._create_withdrawal(client, data, token)
        assert response.status == self.HttpStatus.OK

        response = self._create_withdrawal(client, data, token)
        assert response.status == self.HttpStatus.CONFLICT

    def test_create_withdrawal_shadow_ban_invalid(
            self,
            client: FlaskClient,
            token: str,
            user: UserDTO,
            usdt_rate: RateDTO,
            wallet: WalletDTO,
            crypto_settings_usdt,
            advanced_deal_time_settings: SettingsDTO,
            base_deal_time_settings: SettingsDTO,
            usdt_commission_5,
            db_session: Session,
    ):
        data = {
            "user_id": user.id,
            "address": "TF8ndsFDyUmDi8mgqx61RuxTiW75NRb4UD",
            "amount": 7,
        }
        self._update_user({"shadow_ban": True}, user.id, db_session)

        response = self._create_withdrawal(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST
        assert response.json["detail"] == "400 Bad Request: user is baned"

