"""Persist transcript language and optional translations.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("transcript_segments")
    }
    if "language" not in columns:
        op.add_column(
            "transcript_segments",
            sa.Column("language", sa.String(20), nullable=False, server_default="und"),
        )
    if "translated_language" not in columns:
        op.add_column(
            "transcript_segments", sa.Column("translated_language", sa.String(20), nullable=True)
        )
    if "translated_text" not in columns:
        op.add_column("transcript_segments", sa.Column("translated_text", sa.Text(), nullable=True))


def downgrade() -> None:
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("transcript_segments")
    }
    for name in ("translated_text", "translated_language", "language"):
        if name in columns:
            op.drop_column("transcript_segments", name)
