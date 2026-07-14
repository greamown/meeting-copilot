"""Add projects, glossary, project memory, and meeting association.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "projects" not in tables:
        op.create_table(
            "projects",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("goals", sa.Text(), nullable=False, server_default=""),
            sa.Column("non_goals", sa.Text(), nullable=False, server_default=""),
            sa.Column("default_language", sa.String(20), nullable=False, server_default="zh-TW"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_projects_name", "projects", ["name"])

    if "project_glossary" not in tables:
        op.create_table(
            "project_glossary",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "project_id",
                sa.String(36),
                sa.ForeignKey("projects.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("term", sa.String(200), nullable=False),
            sa.Column("language", sa.String(20), nullable=False, server_default="zh-TW"),
            sa.Column("preferred_spelling", sa.String(200), nullable=False, server_default=""),
            sa.Column("translation", sa.String(500), nullable=False, server_default=""),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("aliases_json", sa.JSON(), nullable=False),
            sa.Column("do_not_translate", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("project_id", "term", "language"),
        )
        op.create_index("ix_project_glossary_project_id", "project_glossary", ["project_id"])

    if "project_memory" not in tables:
        op.create_table(
            "project_memory",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "project_id",
                sa.String(36),
                sa.ForeignKey("projects.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("category", sa.String(50), nullable=False),
            sa.Column("title", sa.String(300), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column(
                "source_meeting_id",
                sa.String(36),
                sa.ForeignKey("meetings.id", ondelete="SET NULL"),
            ),
            sa.Column(
                "source_decision_id",
                sa.String(36),
                sa.ForeignKey("decisions.id", ondelete="SET NULL"),
            ),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="1"),
            sa.Column("status", sa.String(20), nullable=False, server_default="active"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_project_memory_project_id", "project_memory", ["project_id"])
        op.create_index("ix_project_memory_category", "project_memory", ["category"])
        op.create_index("ix_project_memory_status", "project_memory", ["status"])

    meeting_columns = {column["name"] for column in inspector.get_columns("meetings")}
    if "project_id" not in meeting_columns:
        op.add_column("meetings", sa.Column("project_id", sa.String(36), nullable=True))
        op.create_foreign_key(
            "fk_meetings_project_id_projects",
            "meetings",
            "projects",
            ["project_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index("ix_meetings_project_id", "meetings", ["project_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    meeting_columns = {column["name"] for column in inspector.get_columns("meetings")}
    if "project_id" in meeting_columns:
        op.drop_index("ix_meetings_project_id", table_name="meetings")
        op.drop_constraint("fk_meetings_project_id_projects", "meetings", type_="foreignkey")
        op.drop_column("meetings", "project_id")
    for table in ("project_memory", "project_glossary", "projects"):
        if table in set(sa.inspect(bind).get_table_names()):
            op.drop_table(table)
