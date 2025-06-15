from typing import Callable

from _decimal import Decimal
from flask import Response
from flask.testing import FlaskClient

from system.settings import Session
from tests.lots.abstract_lot_test import AbstractLotTest
from utils.tables import LotDTO, UserDTO, WalletDTO, BrokerDTO, CurrencyDTO


class TestGetLots(AbstractLotTest):
    def _get_lots(self, type: str, params: str, client: FlaskClient, token: str) -> Response:
        response = self._make_get_request(client, f"/lots/{type}?{params}", token)
        return response

    def test_get_lots_buy_valid(
            self,
            client: FlaskClient,
            token: str,
            lot: LotDTO,
            user: UserDTO,
            user_factory: Callable[..., UserDTO],
            wallet: WalletDTO,
            lot_factory: Callable[..., LotDTO],
            currency: CurrencyDTO,
            broker: BrokerDTO,
            broker_factory: Callable[..., BrokerDTO],
    ):
        params = f"user_id={user.id}"
        new_broker = broker_factory("Райфайзен")
        lot_factory(
            100, 1000, Decimal("2500000"), user.id, "usdt", currency.id, type_="buy", broker_id=new_broker.id
        )

        response = self._get_lots("buy", params, client, token)
        assert response.status == self.HttpStatus.OK
        assert len(response.json) == 1
        assert response.json[0]["broker"]["id"] == lot.broker_id
        assert response.json[0]["rate"] == lot.rate

    def test_get_lots_buy_limit_to_less_limit_from_valid(
            self,
            client: FlaskClient,
            token: str,
            lot: LotDTO,
            user: UserDTO,
            user_factory: Callable[..., UserDTO],
            wallet: WalletDTO,
            lot_factory: Callable[..., LotDTO],
            currency: CurrencyDTO,
            broker: BrokerDTO,
            db_session: Session,
    ):

        self._update_lot({"limit_to": 20, "limit_from": 30}, lot.id, db_session)
        params = f"user_id={user.id}"

        response = self._get_lots("buy", params, client, token)
        assert response.status == self.HttpStatus.OK
        assert len(response.json) == 0

    def test_get_lots_buy_too_small_balance_balance_valid(
            self,
            client: FlaskClient,
            token: str,
            lot: LotDTO,
            user: UserDTO,
            user_factory: Callable[..., UserDTO],
            wallet: WalletDTO,
            lot_factory: Callable[..., LotDTO],
            currency: CurrencyDTO,
            broker: BrokerDTO,
            db_session: Session,
    ):
        self._update_wallet({"balance": Decimal("1")}, wallet.id, db_session)
        params = f"user_id={user.id}"

        response = self._get_lots("buy", params, client, token)
        assert response.status == self.HttpStatus.OK
        assert len(response.json) == 0

    def test_get_lots_sell_valid(
            self,
            client: FlaskClient,
            token: str,
            lot: LotDTO,
            user: UserDTO,
            user_factory: Callable[..., UserDTO],
            wallet: WalletDTO,
            lot_factory: Callable[..., LotDTO],
            currency: CurrencyDTO,
            broker: BrokerDTO,
            broker_factory
    ):
        params = f"user_id={user.id}"

        new_broker = broker_factory("Райфайзен")
        buy_lot = lot_factory(
            100, 1000, Decimal("2500000"), user.id, "usdt", currency.id, type_="buy", broker_id=new_broker.id
        )

        response = self._get_lots("sell", params, client, token)
        assert response.status == self.HttpStatus.OK
        assert len(response.json) == 1
        assert response.json[0]["broker"]["id"] == buy_lot.broker_id
        assert response.json[0]["rate"] == buy_lot.rate

    def test_get_lots_sell_limit_to_less_limit_from_valid(
            self,
            client: FlaskClient,
            token: str,
            lot: LotDTO,
            user: UserDTO,
            user_factory: Callable[..., UserDTO],
            wallet: WalletDTO,
            lot_factory: Callable[..., LotDTO],
            currency: CurrencyDTO,
            broker: BrokerDTO,
            broker_factory
    ):
        params = f"user_id={user.id}"

        new_broker = broker_factory("Райфайзен")
        lot_factory(
            10000, 1000, Decimal("2500000"), user.id, "usdt", currency.id, type_="sell", broker_id=new_broker.id
        )

        response = self._get_lots("sell", params, client, token)
        assert response.status == self.HttpStatus.OK
        assert len(response.json) == 0

    def test_get_lots_without_user_id_invalid(self, client: FlaskClient, token: str):
        params = ""
        response = self._get_lots("sell", params, client, token)
        assert response.status == self.HttpStatus.BAD_REQUEST

    def test_get_lots_wrong_type_invalid(self, client: FlaskClient, token: str):
        params = ""
        response = self._get_lots("obi-van", params, client, token)
        assert response.status == self.HttpStatus.BAD_REQUEST