from typing import Callable

import pytest
from sqlalchemy import insert
from sqlalchemy.orm import Session

from utils.db import mapping_result_to_dto
from utils.tables import SettingsDTO, settings_table


@pytest.fixture
def settings_factory(db_session: Session) -> Callable[..., SettingsDTO]:
    def create_settings(key: str, value: str) -> SettingsDTO:
        stmt = (
            insert(settings_table)
            .values(key=key, value=value)
            .returning(settings_table)
        )
        result = db_session.execute(stmt)
        return mapping_result_to_dto(result, SettingsDTO)

    return create_settings


@pytest.fixture
def advanced_deal_time_settings(settings_factory: Callable[..., SettingsDTO]) -> SettingsDTO:
    return settings_factory("advanced_deal_time", "30")


@pytest.fixture
def base_deal_time_settings(settings_factory: Callable[..., SettingsDTO]) -> SettingsDTO:
    return settings_factory("base_deal_time", "2")


@pytest.fixture
def usdt_commission_5(settings_factory: Callable[..., SettingsDTO]) -> SettingsDTO:
    return settings_factory("USDT_COMM_5", "2")


@pytest.fixture
def btc_commission_0001(settings_factory: Callable[..., SettingsDTO]) -> SettingsDTO:
    return settings_factory("BTC_COMM_0.0001", "0.0000001")
