"""Add long-term knowledge foreign keys to upgraded databases.

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def _foreign_key(
    name: str, table: str, local: str, remote_table: str, remote: str = "id"
) -> None:
    existing = {
        tuple(item["constrained_columns"])
        for item in sa.inspect(op.get_bind()).get_foreign_keys(table)
    }
    if (local,) not in existing:
        op.create_foreign_key(
            name,
            table,
            remote_table,
            [local],
            [remote],
            ondelete="SET NULL",
        )


def upgrade() -> None:
    for table in ("decisions", "open_questions", "risks", "action_items"):
        _foreign_key(f"fk_{table}_project_id", table, "project_id", "projects")
    _foreign_key("fk_decisions_supersedes_id", "decisions", "supersedes_id", "decisions")
    _foreign_key(
        "fk_decisions_superseded_by_id", "decisions", "superseded_by_id", "decisions"
    )
    _foreign_key(
        "fk_action_items_linked_decision_id",
        "action_items",
        "linked_decision_id",
        "decisions",
    )


def downgrade() -> None:
    names = [
        ("action_items", "fk_action_items_linked_decision_id"),
        ("decisions", "fk_decisions_superseded_by_id"),
        ("decisions", "fk_decisions_supersedes_id"),
        ("action_items", "fk_action_items_project_id"),
        ("risks", "fk_risks_project_id"),
        ("open_questions", "fk_open_questions_project_id"),
        ("decisions", "fk_decisions_project_id"),
    ]
    existing = {
        (table, item["name"])
        for table, _ in names
        for item in sa.inspect(op.get_bind()).get_foreign_keys(table)
    }
    for table, name in names:
        if (table, name) in existing:
            op.drop_constraint(name, table, type_="foreignkey")
