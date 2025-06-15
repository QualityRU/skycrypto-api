from typing import Callable
from uuid import UUID

from _decimal import Decimal
from flask import Response
from flask.testing import FlaskClient

from system.settings import Session
from tests.lots.abstract_lot_test import AbstractLotTest
from utils.tables import UserDTO, WalletDTO, BrokerDTO, LotDTO, CurrencyDTO


class TestGetBrokerLots(AbstractLotTest):
    def _get_broker_lots(self, params: str, type: str, client: FlaskClient, token: str) -> Response:
        response = self._make_get_request(client, f"/broker-lots/{type}?{params}", token)
        return response

    def test_get_broker_lots_sell_valid(
            self,
            client: FlaskClient,
            token: str,
            user: UserDTO,
            wallet: WalletDTO,
            broker: BrokerDTO,
            lot_factory: Callable[..., LotDTO],
            currency: CurrencyDTO,
            lot: LotDTO,
    ):
        lot_buy = lot_factory(
            100, 1000, Decimal("2500000"), user.id, "usdt", currency.id, type_="buy", broker_id=broker.id
        )

        params = f"user_id={user.id}&broker={broker.id}"

        response = self._get_broker_lots(params, "sell", client, token)
        assert response.status == self.HttpStatus.OK
        assert len(response.json) == 1
        assert response.json[0]["identificator"] == lot_buy.identificator

    def test_get_broker_lots_sell_limit_to_less_limit_from_valid(
            self,
            client: FlaskClient,
            token: str,
            user: UserDTO,
            wallet: WalletDTO,
            broker: BrokerDTO,
            lot_factory: Callable[..., LotDTO],
            currency: CurrencyDTO,
            lot: LotDTO,
    ):
        lot_factory(
            10000, 1000, Decimal("2500000"), user.id, "usdt", currency.id, type_="buy", broker_id=broker.id
        )
        params = f"user_id={user.id}&broker={broker.id}"

        response = self._get_broker_lots(params, "sell", client, token)
        assert response.status == self.HttpStatus.OK
        assert len(response.json) == 0


    def test_get_broker_lots_buy_valid(
            self,
            client: FlaskClient,
            token: str,
            user: UserDTO,
            wallet: WalletDTO,
            broker: BrokerDTO,
            lot_factory: Callable[..., LotDTO],
            currency: CurrencyDTO,
            lot: LotDTO,
    ):
        lot_factory(
            100, 1000, Decimal("2500000"), user.id, "usdt", currency.id, type_="buy", broker_id=broker.id
        )
        params = f"user_id={user.id}&broker={broker.id}"

        response = self._get_broker_lots(params, "buy", client, token)
        assert response.status == self.HttpStatus.OK
        assert len(response.json) == 1
        assert response.json[0]["identificator"] == lot.identificator

    def test_get_broker_lots_buy_limit_to_less_limit_from_valid(
            self,
            client: FlaskClient,
            token: str,
            user: UserDTO,
            wallet: WalletDTO,
            broker: BrokerDTO,
            lot_factory: Callable[..., LotDTO],
            currency: CurrencyDTO,
            lot: LotDTO,
            db_session: Session
    ):
        self._update_lot({"limit_to": 200, "limit_from":300}, lot.id, db_session)
        params = f"user_id={user.id}&broker={broker.id}"

        response = self._get_broker_lots(params, "buy", client, token)
        assert response.status == self.HttpStatus.OK
        assert len(response.json) == 0

    def test_get_broker_lots_buy_wrong_limit_to_valid(
            self,
            client: FlaskClient,
            token: str,
            user: UserDTO,
            wallet: WalletDTO,
            broker: BrokerDTO,
            lot_factory: Callable[..., LotDTO],
            currency: CurrencyDTO,
            lot: LotDTO,
            db_session: Session
    ):
        self._update_lot({"limit_to": 20, "limit_from": 10}, lot.id, db_session)
        params = f"user_id={user.id}&broker={broker.id}"

        response = self._get_broker_lots(params, "buy", client, token)
        assert response.status == self.HttpStatus.OK
        assert len(response.json) == 0

    def test_get_broker_lots_buy_max_to_sell_less_limit_to_valid(
            self,
            client: FlaskClient,
            token: str,
            user: UserDTO,
            wallet: WalletDTO,
            broker: BrokerDTO,
            lot_factory: Callable[..., LotDTO],
            currency: CurrencyDTO,
            lot: LotDTO,
            db_session: Session
    ):
        new_balance = Decimal("50")
        self._update_wallet({"balance": new_balance}, wallet.id, db_session)
        params = f"user_id={user.id}&broker={broker.id}"

        response = self._get_broker_lots(params, "buy", client, token)
        assert response.status == self.HttpStatus.OK
        assert len(response.json) == 1
        assert response.json[0]["limit_to"] == self._to_unit_usdt(new_balance) * lot.rate

    def test_get_broker_lots_without_params_invalid(self, client: FlaskClient, token: str):
        response = self._get_broker_lots("params", "buy", client, token)
        assert response.status == self.HttpStatus.BAD_REQUEST

    def test_get_broker_lots_wrong_type_invalid(self, client: FlaskClient, token: str, user: UserDTO,broker: BrokerDTO):
        params = f"user_id={user.id}&broker={broker.id}"

        response = self._get_broker_lots(params, "buyy", client, token)
        assert response.status == self.HttpStatus.BAD_REQUEST