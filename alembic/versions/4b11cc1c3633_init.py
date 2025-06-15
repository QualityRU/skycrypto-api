"""init

Revision ID: 4b11cc1c3633
Revises: 
Create Date: 2023-06-22 19:02:37.603343

"""
from alembic import op
import sqlalchemy as sa
from pathlib import Path


# revision identifiers, used by Alembic.
revision = "4b11cc1c3633"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    migration_sql = Path(__file__).parent.joinpath("4b11cc1c3633_upgrade.sql").read_text()
    op.get_bind().execute(sa.text(migration_sql))


def downgrade() -> None:
    op.get_bind().execute(
        sa.text(
            """
        DROP SCHEMA public CASCADE;
        CREATE SCHEMA public;
        GRANT ALL ON SCHEMA public TO postgres;
        GRANT ALL ON SCHEMA public TO public;
        """
        )
    )

    op.create_table(
        "alembic_version",
        sa.Column("version_num", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("version_num", name=op.f("pk__alembic_version")),
    )
    op.get_bind().execute(sa.text("INSERT INTO alembic_version VALUES ('4b11cc1c3633');"))
