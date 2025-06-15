from typing import Union
from uuid import UUID

from _decimal import Decimal
from flask import Response
from flask.testing import FlaskClient
from sqlalchemy import select, update

from system.settings import Session
from utils.db import mapping_result_to_dto
from utils.tables import wallets_table, WalletDTO, DealDTO, users_table, operations_table, OperationDTO, \
    notifications_table, NotificationDTO, TransactionDTO, transactions_table, UserDTO


class AbstractAPITest:
    class HttpStatus:
        OK = "200 OK"
        CREATED = "201 CREATED"
        BAD_REQUEST = "400 BAD REQUEST"
        FORBIDDEN = "403 FORBIDDEN"
        NOT_FOUND = "404 NOT FOUND"
        CONFLICT = "409 CONFLICT"

    def _make_request(self, client: FlaskClient, method: str, url: str, token, data: dict = None,) -> Response:
        headers = {
            "Token": token
        }
        return getattr(client, method)(url, headers=headers, json=data)

    def _make_get_request(self, client, url, token) -> Response:
        return self._make_request(client, "get", url, token)

    def _make_post_request(self, client, url, token, data) -> Response:
        return self._make_request(client, "post", url, token, data)

    def _make_patch_request(self, client, url, token, data) -> Response:
        return self._make_request(client, "patch", url, token, data)

    def _to_unit_usdt(self, value: Union[Decimal, int]) -> Union[Decimal, int]:
        return value / 10**6

    def _select_wallet(self, wallet_id: int, db_session: Session) -> WalletDTO:
        stmt = (
            select([wallets_table])
            .where(wallets_table.c.id == wallet_id)
        )
        db_session.execute(stmt)
        result = db_session.execute(stmt)
        result_wallet_dto = mapping_result_to_dto(result, WalletDTO)
        return result_wallet_dto

    def _select_user(self, user_id: int, db_session: Session) -> UserDTO:
        stmt = (
            select([users_table])
            .where(users_table.c.id ==user_id)
        )
        db_session.execute(stmt)
        result = db_session.execute(stmt)
        result_user_dto = mapping_result_to_dto(result, UserDTO)
        return result_user_dto

    def _select_operation(self, operation_id: Union[str, UUID], user_id: int, db_session: Session) -> OperationDTO:
        stmt = (
            select([operations_table])
            .where((operations_table.c.id == operation_id) & (operations_table.c.user_id == user_id))
        )
        db_session.execute(stmt)
        result = db_session.execute(stmt)
        result_operation_dto = mapping_result_to_dto(result, OperationDTO)
        return result_operation_dto

    def _select_notification(self, user_id: int, db_session: Session) -> NotificationDTO:
        stmt = (
            select([notifications_table])
            .where(notifications_table.c.user_id == user_id)
        )
        db_session.execute(stmt)
        result = db_session.execute(stmt)
        result_notification_dto = mapping_result_to_dto(result, NotificationDTO)
        return result_notification_dto

    def _select_transaction(self, wallet_id: int, db_session: Session) -> TransactionDTO:
        stmt = (
            select([transactions_table])
            .where(transactions_table.c.wallet_id == wallet_id)
        )
        db_session.execute(stmt)
        result = db_session.execute(stmt)
        result_transaction_dto = mapping_result_to_dto(result, TransactionDTO)
        return result_transaction_dto

    def _update_wallet(self, values: dict ,wallet_id: int, db_session: Session):
        stmt = (
            update(wallets_table)
            .where(wallets_table.c.id == wallet_id)
            .values(**values)
        )
        db_session.execute(stmt)

    def _update_user(self, values: dict, user_id: int, db_session: Session):
        stmt = (
            update(users_table)
            .where(users_table.c.id == user_id)
            .values(**values)
        )
        db_session.execute(stmt)