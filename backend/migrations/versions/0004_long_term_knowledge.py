"""Add immutable decisions, action tracking, and knowledge documents.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _add_columns(table: str, definitions: list[sa.Column[object]]) -> None:
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}
    for column in definitions:
        if column.name not in existing:
            op.add_column(table, column)


def upgrade() -> None:
    common = [
        sa.Column("project_id", sa.String(36), nullable=True),
        sa.Column("evidence_segment_ids_json", sa.JSON(), nullable=False, server_default="[]"),
    ]
    for table in ("decisions", "open_questions", "risks", "action_items"):
        _add_columns(table, [column.copy() for column in common])
        op.create_index(f"ix_{table}_project_id", table, ["project_id"], if_not_exists=True)

    _add_columns(
        "decisions",
        [
            sa.Column("title", sa.String(300), nullable=False, server_default=""),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("owner", sa.String(100), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="1"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("supersedes_id", sa.String(36), nullable=True),
            sa.Column("superseded_by_id", sa.String(36), nullable=True),
            sa.Column("created_by", sa.String(100), nullable=False, server_default="user"),
            sa.Column("updated_by", sa.String(100), nullable=False, server_default="user"),
        ],
    )
    op.create_index("ix_decisions_status", "decisions", ["status"], if_not_exists=True)
    _add_columns("open_questions", [sa.Column("owner", sa.String(100), nullable=True)])
    _add_columns(
        "risks",
        [
            sa.Column("severity", sa.String(20), nullable=False, server_default="medium"),
            sa.Column("probability", sa.Float(), nullable=False, server_default="0.5"),
            sa.Column("owner", sa.String(100), nullable=True),
        ],
    )
    _add_columns(
        "action_items",
        [
            sa.Column("title", sa.String(300), nullable=False, server_default=""),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("priority", sa.String(20), nullable=False, server_default="normal"),
            sa.Column("linked_decision_id", sa.String(36), nullable=True),
        ],
    )
    op.create_index("ix_action_items_priority", "action_items", ["priority"], if_not_exists=True)

    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "knowledge_documents" not in tables:
        op.create_table(
            "knowledge_documents",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "project_id",
                sa.String(36),
                sa.ForeignKey("projects.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column("source_type", sa.String(40), nullable=False, server_default="uploaded"),
            sa.Column("title", sa.String(300), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("language", sa.String(20), nullable=False, server_default="und"),
            sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        for column in ("project_id", "source_type", "title", "language"):
            op.create_index(f"ix_knowledge_documents_{column}", "knowledge_documents", [column])


def downgrade() -> None:
    if "knowledge_documents" in set(sa.inspect(op.get_bind()).get_table_names()):
        op.drop_table("knowledge_documents")
