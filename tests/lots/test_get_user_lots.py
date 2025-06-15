from typing import Callable

from _decimal import Decimal
from flask import Response
from flask.testing import FlaskClient

from tests.lots.abstract_lot_test import AbstractLotTest
from utils.tables import LotDTO, UserDTO, WalletDTO, BrokerDTO, CurrencyDTO


class TestGetUserLots(AbstractLotTest):
    def _get_user_lots(self, user_id: int, client: FlaskClient, token: str) -> Response:
        response = self._make_get_request(client, f"/user-lots/{user_id}", token)
        return response

    def test_get_user_lots(
            self,
            client: FlaskClient,
            token: str,
            lot: LotDTO,
            user: UserDTO,
            user_factory: Callable[..., UserDTO],
            wallet: WalletDTO,
            lot_factory: Callable[..., LotDTO],
            currency: CurrencyDTO,
            broker: BrokerDTO
    ):
        new_user = user_factory()
        lot_factory(
            100, 1000, Decimal("2500000"), new_user.id, "usdt", currency.id, type_="buy", broker_id=broker.id
        )

        response = self._get_user_lots(user.id, client, token)
        assert response.status == self.HttpStatus.OK
        assert len(response.json) == 1
        assert response.json[0]["identificator"] == lot.identificator
