from flask import Response
from flask.testing import FlaskClient
from sqlalchemy import update, insert, select

from system.settings import Session
from tests.abstract_test import AbstractAPITest
from utils.db import mapping_result_to_dto
from utils.tables import users_table, UserDTO, WalletDTO, RateDTO, promo_codes_table, wallets_table


class TestCreatePromoCode(AbstractAPITest):
    def _create_promo_code(self, client: FlaskClient, data: dict, token: str) -> Response:
        response = self._make_post_request(client, "/new-promocode", token, data)
        return response

    def test_create_promo_code_valid(
            self,
            token: str,
            client: FlaskClient,
            user: UserDTO,
            wallet: WalletDTO,
            usdt_rate: RateDTO,
            db_session: Session
    ):
        activations = 2
        amount = 1
        data = {"activations": activations, "user_id": user.id, "amount": amount}

        response = self._create_promo_code(client, data, token)
        assert response.status == self.HttpStatus.OK
        assert response.json["amount"] == amount
        assert response.json["count"] == activations

        refresh_wallet = self._select_wallet(wallet.id, db_session)
        assert refresh_wallet.frozen == amount * activations * 1000000

    def test_create_promo_code_not_enough_money_invalid(
            self, token: str, client: FlaskClient, user: UserDTO, wallet: WalletDTO, usdt_rate
    ):
        activations = 1000
        amount = 1000
        data = {"activations": activations, "user_id": user.id, "amount": amount}
        response = self._create_promo_code(client, data, token)

        assert response.status == self.HttpStatus.BAD_REQUEST
        assert response.json["detail"] == "400 Bad Request: You don't have enough money"

    def test_create_promo_code_banned_user_invalid(
            self, token: str, client: FlaskClient, user: UserDTO, wallet: WalletDTO, usdt_rate, db_session: Session
    ):
        self._update_user({"is_baned": True}, user.id, db_session)
        activations = 1
        amount = 1
        data = {"activations": activations, "user_id": user.id, "amount": amount}

        response = self._create_promo_code(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST
        assert response.json["detail"] == "400 Bad Request: You are banned"

    def test_create_promo_code_wrong_min_amount_invalid(
            self, token: str, client: FlaskClient, user: UserDTO, wallet: WalletDTO, usdt_rate
    ):
        activations = 1
        amount = 0.1
        data = {"activations": activations, "user_id": user.id, "amount": amount}

        response = self._create_promo_code(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST
        assert response.json["detail"] == "400 Bad Request: wrong amount"

    def test_create_promo_code_wrong_data_invalid(
            self, token: str, client: FlaskClient, user: UserDTO, wallet: WalletDTO, usdt_rate
    ):
        activations = -1
        amount = 2
        data = {"activations": activations, "user_id": user.id, "amount": amount}

        response = self._create_promo_code(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST
        assert response.json["detail"] == "400 Bad Request: wrong data"

    def test_create_promo_code_exceeded_limit_invalid(
            self, token: str, client: FlaskClient, user: UserDTO, wallet: WalletDTO, usdt_rate, db_session: Session
    ):
        values = [
            {"wallet_id": wallet.id, "amount": 1,"code": str(_), "count": 1, "is_deleted": False} for _ in range(16)
        ]
        stmt = (
            insert(promo_codes_table)
            .values(
                values
            )
            .returning(promo_codes_table)
        )
        db_session.execute(stmt)

        activations = 1
        amount = 1
        data = {"activations": activations, "user_id": user.id, "amount": amount}

        response = self._create_promo_code(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST
        assert response.json["detail"] == "400 Bad Request: promocode limit"
