from os import path, environ as env
from typing import Tuple

from cachetools import TTLCache
from flask import Flask
from flask_mail import Mail
from sqlalchemy import create_engine, MetaData
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

APP_NAME = 'SKY API'


def create_app(secret_key: str, mail_password: str) -> Flask:
    root_path = '/'.join(path.realpath(__file__).split('/')[:-2])
    application = Flask(APP_NAME, root_path=root_path)
    application.secret_key = secret_key
    application.config.update(
        MAIL_SERVER='smtp.gmail.com',
        MAIL_PORT=465,
        MAIL_USE_SSL=True,
        MAIL_USERNAME='pay@skycrypto.shop',
        MAIL_PASSWORD=mail_password,
        APP_NAME=APP_NAME
    )
    return application


def create_session(db_url: str) -> Tuple[Engine, sessionmaker, MetaData]:
    engine = create_engine(db_url, pool_size=80)
    return engine, sessionmaker(bind=engine), MetaData(bind=engine)


DB_URL = f'postgres://{env["DB_USER"]}:{env["DB_PASSWORD"]}@{env["DB_HOST"]}:{env["DB_PORT"]}/{env["DB_NAME"]}'
db, Session, metadata = create_session(DB_URL)
app = create_app(env.get('KEY', ""), env.get('MAIL_PASSWORD', ""))
mail = Mail(app)
TEST = env.get('TEST')

cache = TTLCache(maxsize=100, ttl=60)
