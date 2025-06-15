from flask import Response
from flask.testing import FlaskClient

from tests.lots.abstract_lot_test import AbstractLotTest
from utils.tables import UserDTO, LotDTO, BrokerDTO


class TestGetLot(AbstractLotTest):
    def _get_lot_by_id(self, identificator: str, client: FlaskClient, token: str) -> Response:
        response = self._make_get_request(client, f"/lot/{identificator}", token)
        return response

    def test_get_lot_valid(
            self, client: FlaskClient, token: str, user: UserDTO, lot: LotDTO, broker: BrokerDTO
    ):
        response = self._get_lot_by_id(lot.identificator, client, token)
        assert response.status == self.HttpStatus.OK
        assert isinstance(response.json, dict)
        assert response.json["identificator"] == lot.identificator
        assert response.json["broker"] == broker.name

    def test_get_lot_not_exist_invalid(
            self, client: FlaskClient, token: str, user: UserDTO, lot: LotDTO, broker: BrokerDTO
    ):

        response = self._get_lot_by_id("identificator", client, token)
        assert response.status == self.HttpStatus.BAD_REQUEST