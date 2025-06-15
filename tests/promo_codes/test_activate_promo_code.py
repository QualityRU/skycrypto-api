import json
from typing import Callable

from _decimal import Decimal
from flask import Response
from flask.testing import FlaskClient
from sqlalchemy import select, update

from system.constants import Action
from system.settings import Session
from tests.abstract_test import AbstractAPITest
from utils.db import mapping_result_to_dto
from utils.tables import PromoCodeDTO, UserDTO, WalletDTO, wallets_table, promo_codes_table


class TestActivatePromoCode(AbstractAPITest):
    def _activate_promo_code(self, client: FlaskClient, data: dict, token: str) -> Response:
        response = self._make_post_request(client, "/promocode-activation", token, data)
        return response

    def test_activate_promo_code_valid(
            self,
            client: FlaskClient,
            token: str,
            promo_code: PromoCodeDTO,
            user_factory: Callable[..., UserDTO],
            wallet_factory: Callable[..., WalletDTO],
            wallet: WalletDTO,
            user: UserDTO,
            db_session: Session
    ):
        activate_user = user_factory()
        activate_wallet = wallet_factory(activate_user.id, Decimal("100000"))
        data = {
            "code": promo_code.code,
            "user_id": activate_wallet.user_id
        }

        response = self._activate_promo_code(client, data, token)
        assert response.status == self.HttpStatus.OK
        assert response.json["code"] == promo_code.code
        assert response.json["owner_id"] == user.id
        assert response.json["symbol"] == wallet.symbol

        refresh_activate_wallet = self._select_wallet(activate_wallet.id, db_session)
        assert refresh_activate_wallet.balance == activate_wallet.balance + promo_code.amount * promo_code.count

        refresh_creator_wallet = self._select_wallet(wallet.id, db_session)
        assert refresh_creator_wallet.frozen == 0
        assert refresh_creator_wallet.balance == wallet.balance - promo_code.amount * promo_code.count

        creator_operation = self._select_operation(promo_code.code, user.id, db_session)
        assert creator_operation.user_id == user.id
        assert creator_operation.amount == -self._to_unit_usdt(promo_code.amount)
        assert creator_operation.action == Action.promocode

        activator_operation = self._select_operation(promo_code.code, activate_user.id, db_session)
        assert activator_operation.user_id == activate_user.id
        assert activator_operation.amount == self._to_unit_usdt(promo_code.amount)
        assert activator_operation.action == Action.promocode

    def test_activate_promo_code_wrong_count_invalid(
            self,
            client: FlaskClient,
            token: str,
            promo_code: PromoCodeDTO,
            user_factory: Callable[..., UserDTO],
            wallet_factory: Callable[..., WalletDTO],
            db_session: Session
    ):
        activate_user = user_factory()
        activate_wallet = wallet_factory(activate_user.id, Decimal("100000"))
        data = {
            "code": promo_code.code,
            "user_id": activate_wallet.user_id
        }
        stmt = (
            update(promo_codes_table)
            .values(count=0)
            .where(promo_codes_table.c.id == promo_code.id)
        )
        db_session.execute(stmt)

        response = self._activate_promo_code(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST

    def test_activate_promo_code_self_activation_invalid(
            self,
            client: FlaskClient,
            token: str,
            promo_code: PromoCodeDTO,
            user: UserDTO,
    ):
        data = {
            "code": promo_code.code,
            "user_id": user.id
        }

        response = self._activate_promo_code(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST

    def test_activate_promo_code_deleted_invalid(
            self,
            client: FlaskClient,
            token: str,
            promo_code: PromoCodeDTO,
            user_factory: Callable[..., UserDTO],
            wallet_factory: Callable[..., WalletDTO],
            db_session: Session
    ):
        activate_user = user_factory()
        activate_wallet = wallet_factory(activate_user.id, Decimal("100000"))
        data = {
            "code": promo_code.code,
            "user_id": activate_wallet.user_id
        }
        stmt = (
            update(promo_codes_table)
            .values(is_deleted=True)
            .where(promo_codes_table.c.id == promo_code.id)
        )
        db_session.execute(stmt)

        response = self._activate_promo_code(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST

    def test_activate_promo_code_wrong_code_invalid(
            self,
            client: FlaskClient,
            token: str,
            promo_code: PromoCodeDTO,
            user_factory: Callable[..., UserDTO],
            wallet_factory: Callable[..., WalletDTO],
    ):
        activate_user = user_factory()
        activate_wallet = wallet_factory(activate_user.id, Decimal("100000"))
        data = {
            "code": "12afaw",
            "user_id": activate_wallet.user_id
        }

        response = self._activate_promo_code(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST

    def test_activate_promo_code_wrong_symbol(
            self,
            client: FlaskClient,
            token: str,
            wallet: WalletDTO,
            promo_code: PromoCodeDTO,
            user_factory: Callable[..., UserDTO],
            wallet_factory: Callable[..., WalletDTO],
            db_session: Session
    ):
        activate_user = user_factory()
        activate_wallet = wallet_factory(activate_user.id, Decimal("100000"))
        data = {
            "code": promo_code.code,
            "user_id": activate_wallet.user_id
        }
        self._update_wallet({"symbol": "btc"}, wallet.id, db_session)

        response = self._activate_promo_code(client, data, token)
        assert response.status == self.HttpStatus.BAD_REQUEST
