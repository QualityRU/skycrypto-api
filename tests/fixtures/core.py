import logging
from contextlib import contextmanager
from unittest.mock import patch

import jwt
import pytest
from flask import Flask
from flask.testing import FlaskClient, FlaskCliRunner
from sqlalchemy.engine import Engine, Connection
from sqlalchemy.orm import Session, sessionmaker

from system.settings import app as app_settings, db
from api import app as flask_app
logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def app() -> Flask:
    flask_app.config.update({"TESTING": True})
    return flask_app


@pytest.fixture()
def client(app: Flask) -> FlaskClient:
    return app.test_client()


@pytest.fixture()
def cli_runner(app: Flask) -> FlaskCliRunner:
    return app.test_cli_runner()


@pytest.fixture(scope="session")
def _db_engine() -> Engine:
    try:
        yield db
    finally:
        db.dispose()


@pytest.fixture()
def db_session(_db_engine: Engine) -> Session:
    session = sessionmaker(bind=_db_engine)()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(autouse=True)
def patch_session(db_session: Session) -> None:
    @contextmanager
    def session_scope():
        db_session.begin_nested()
        try:
            yield db_session
            db_session.commit()
        except BaseException:
            db_session.rollback()
            raise

    with patch("utils.db_sessions._session_scope", new_callable=lambda: session_scope):
        yield


@pytest.fixture(scope="session")
def token():
    token = jwt.encode({"symbol": "usdt"}, key=app_settings.secret_key, algorithm='HS256').decode()
    return token
