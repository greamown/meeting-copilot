"""Add persistent idempotency records.

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "idempotency_records" not in tables:
        op.create_table(
            "idempotency_records",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("scope", sa.String(200), nullable=False),
            sa.Column("key", sa.String(200), nullable=False),
            sa.Column("request_hash", sa.String(64), nullable=False),
            sa.Column("resource_type", sa.String(80), nullable=False),
            sa.Column("resource_id", sa.String(100), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("scope", "key", name="uq_idempotency_scope_key"),
        )


def downgrade() -> None:
    if "idempotency_records" in set(sa.inspect(op.get_bind()).get_table_names()):
        op.drop_table("idempotency_records")
