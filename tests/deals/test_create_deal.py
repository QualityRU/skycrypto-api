from typing import Callable
from unittest.mock import patch

from _decimal import Decimal
from flask import Response
from flask.testing import FlaskClient
from sqlalchemy import select, update

from system.settings import Session
from tests.deals.abstract_deal_test import AbstractDealTest
from utils.tables import (
    UserDTO,
    WalletDTO,
    LotDTO,
    CryptoSettingsDTO,
    RateDTO,
    lots_table,
    DealDTO, CurrencyDTO,
)


class TestCreateDeal(AbstractDealTest):
    def _create_deal(self, client: FlaskClient, data: dict, token: str) -> Response:
        response = self._make_post_request(client, "/new-deal", token, data)
        return response

    def test_create_deal_lot_type_sell_valid(
            self,
            client: FlaskClient,
            token: str,
            user: UserDTO,
            user_factory: Callable[..., UserDTO],
            wallet: WalletDTO,
            wallet_factory: Callable[..., WalletDTO],
            lot: LotDTO,
            crypto_settings_usdt: CryptoSettingsDTO,
            usdt_rate: RateDTO,
            db_session: Session
    ):
        user_buyer = user_factory()
        wallet_factory(user_buyer.id, Decimal("10000000000.0"))

        amount = 56
        data = {
            "user_id": user_buyer.id,
            "lot_id": lot.identificator,
            "rate": lot.rate,
            "amount": amount,
            "amount_currency": 1,
        }
        with patch("utils.notifications_queue._send_queue_notification"):
            response = self._create_deal(client, data, token)
            assert response.status == self.HttpStatus.OK
            assert response.json["amount"] == amount
            assert response.json["buyer"]["id"] == user_buyer.id
            assert response.json["seller"]["id"] == lot.user_id

        refresh_wallet = self._select_wallet(wallet.id, db_session)
        assert refresh_wallet.frozen == amount * 1000000

    def test_create_deal_lot_type_buy_valid(
            self,
            client: FlaskClient,
            token: str,
            user: UserDTO,
            user_factory: Callable[..., UserDTO],
            wallet: WalletDTO,
            wallet_factory: Callable[..., WalletDTO],
            lot: LotDTO,
            crypto_settings_usdt: CryptoSettingsDTO,
            usdt_rate: RateDTO,
            db_session: Session
    ):
        user_buyer = user_factory()
        wallet_buyer = wallet_factory(user_buyer.id, Decimal("10000000000.0"))

        amount = 56
        data = {
            "user_id": user_buyer.id,
            "lot_id": lot.identificator,
            "rate": lot.rate,
            "amount": amount,
            "amount_currency": 1,
        }

        stmt = (
            update(lots_table)
            .values(type="buy")
            .returning(lots_table)
        )
        db_session.execute(stmt)

        with patch("utils.notifications_queue._send_queue_notification"):
            response = self._create_deal(client, data, token)
            assert response.status == self.HttpStatus.OK
            assert response.json["amount"] == amount
            assert response.json["buyer"]["id"] == lot.user_id
            assert response.json["seller"]["id"] == user_buyer.id

        refresh_wallet = self._select_wallet(wallet_buyer.id, db_session)
        assert refresh_wallet.frozen == amount * 1000000

    def test_create_deal_none_data_invalid(
            self,
            client: FlaskClient,
            token: str,
            user: UserDTO,
            user_factory: Callable[..., UserDTO],
            wallet: WalletDTO,
            wallet_factory: Callable[..., WalletDTO],
            lot: LotDTO,
    ):
        user_buyer = user_factory()
        wallet_factory(user_buyer.id, Decimal("10000000000.0"))
        data = {
            "user_id": user_buyer.id,
            "lot_id": lot.identificator,
            "rate": lot.rate,
            "amount": 56,
        }

        response = self._create_deal(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST

        data.pop("amount")
        data["amount_currency"] = 1
        response = self._create_deal(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST

        data.pop("rate")
        data["amount"] = 56
        response = self._create_deal(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST

        data.pop("lot_id")
        data["rate"] = lot.rate
        response = self._create_deal(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST

        data.pop("user_id")
        data["lot_id"] = lot.identificator
        response = self._create_deal(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST

    def test_create_deal_shadow_ban_invalid(
            self,
            client: FlaskClient,
            token: str,
            user: UserDTO,
            user_factory: Callable[..., UserDTO],
            wallet: WalletDTO,
            wallet_factory: Callable[..., WalletDTO],
            lot: LotDTO,
            crypto_settings_usdt: CryptoSettingsDTO,
            usdt_rate: RateDTO,
            db_session: Session
    ):
        user_buyer = user_factory()
        wallet_factory(user_buyer.id, Decimal("10000000000.0"))

        self._update_user({"shadow_ban": True}, user_buyer.id, db_session)

        data = {
            "user_id": user_buyer.id,
            "lot_id": lot.identificator,
            "rate": lot.rate,
            "amount": 56,
            "amount_currency": 1,
        }

        response = self._create_deal(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST
        assert response.json["detail"] == "400 Bad Request: user is baned"

    def test_create_deal_wrong_lot_invalid(
            self,
            client: FlaskClient,
            token: str,
            user: UserDTO,
            wallet: WalletDTO,
            crypto_settings_usdt: CryptoSettingsDTO,
            lot: LotDTO
    ):
        data = {
            "user_id": user.id,
            "lot_id": "lot.identificator",
            "rate": lot.rate,
            "amount": 56,
            "amount_currency": 1,
        }

        response = self._create_deal(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST

    def test_create_deal_wrong_lot_symbol_invalid(
            self,
            client: FlaskClient,
            token: str,
            user: UserDTO,
            user_factory: Callable[..., UserDTO],
            wallet: WalletDTO,
            wallet_factory: Callable[..., WalletDTO],
            lot: LotDTO,
            crypto_settings_usdt: CryptoSettingsDTO,
            usdt_rate: RateDTO,
            db_session: Session
    ):
        user_buyer = user_factory()
        wallet_factory(user_buyer.id, Decimal("10000000000.0"))

        stmt = (
            update(lots_table)
            .values(symbol="btc")
            .returning(lots_table)
        )
        db_session.execute(stmt)

        data = {
            "user_id": user_buyer.id,
            "lot_id": lot.identificator,
            "rate": lot.rate,
            "amount": 56,
            "amount_currency": 1,
        }

        response = self._create_deal(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST

    def test_create_deal_exceeded_limit_invalid(
            self,
            client: FlaskClient,
            token: str,
            user: UserDTO,
            wallet: WalletDTO,
            lot: LotDTO,
            crypto_settings_usdt: CryptoSettingsDTO,
            usdt_rate: RateDTO,
            deal: DealDTO,
            db_session: Session
    ):

        data = {
            "user_id": user.id,
            "lot_id": lot.identificator,
            "rate": lot.rate,
            "amount": 56,
            "amount_currency": 1,
        }
        self._update_user({"is_verify": False}, user.id, db_session)

        response = self._create_deal(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST
        assert response.json["detail"] == "400 Bad Request: limit of this lot exceeded"

    def test_create_deal_insufficient_funds_invalid(
            self,
            client: FlaskClient,
            token: str,
            user: UserDTO,
            user_factory: Callable[..., UserDTO],
            wallet: WalletDTO,
            wallet_factory: Callable[..., WalletDTO],
            lot: LotDTO,
            crypto_settings_usdt: CryptoSettingsDTO,
            usdt_rate: RateDTO
    ):
        user_buyer = user_factory()
        wallet_factory(user_buyer.id, Decimal("100000.0"))
        data = {
            "user_id": user_buyer.id,
            "lot_id": lot.identificator,
            "rate": lot.rate,
            "amount": 5600000,
            "amount_currency": 1,
        }

        response = self._create_deal(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST
        assert response.json["detail"] == "400 Bad Request: insufficient funds"

