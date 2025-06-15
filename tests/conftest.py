from os import environ
import atexit

from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from sqlalchemy_utils import create_database, drop_database

load_dotenv()
environ["DB_NAME"] = environ["DB_NAME"] + "_test"

from system.settings import DB_URL

alembic_cfg = Config("./alembic.ini")
alembic_cfg.set_main_option("script_location", "./alembic")
alembic_cfg.set_main_option("sqlalchemy.url", DB_URL)


def upgrade_database():
    create_database(DB_URL)
    command.upgrade(alembic_cfg, "head")


def downgrade_database() -> None:
    command.downgrade(alembic_cfg, "base")
    drop_database(DB_URL)


upgrade_database()
atexit.register(downgrade_database)

pytest_plugins = [
    "tests.fixtures.core",
    "tests.fixtures.currencies",
    "tests.fixtures.users",
    "tests.fixtures.wallets",
    "tests.fixtures.brokers",
    "tests.fixtures.lots",
    "tests.fixtures.deals",
    "tests.fixtures.rates",
    "tests.fixtures.promo_code",
    "tests.fixtures.crypto_settings",
    "tests.fixtures.settings",
    "tests.fixtures.disputes",
    "tests.fixtures.merchant",
    "tests.fixtures.commissions",
]
