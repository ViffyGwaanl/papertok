"""paper_events

Revision ID: fd84f4a0755a
Revises: 4b07fddd60af
Create Date: 2026-02-07 01:50:00.258038

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fd84f4a0755a'
down_revision: Union[str, None] = '4b07fddd60af'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    bind = op.get_bind()

    if bind.dialect.name == "sqlite":
        # Idempotent creation for existing local MVP DBs.
        bind.execute(
            sa.text(
                """
                CREATE TABLE IF NOT EXISTS paper_events (
                  id INTEGER PRIMARY KEY,
                  paper_id INTEGER NOT NULL,
                  stage VARCHAR NOT NULL,
                  status VARCHAR NOT NULL,
                  error VARCHAR,
                  meta_json VARCHAR,
                  log_path VARCHAR,
                  created_at DATETIME NOT NULL,
                  FOREIGN KEY(paper_id) REFERENCES papers (id)
                )
                """
            )
        )
        bind.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_paper_events_paper_id ON paper_events (paper_id)"
            )
        )
        bind.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_paper_events_stage ON paper_events (stage)"
            )
        )
        bind.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_paper_events_status ON paper_events (status)"
            )
        )
        bind.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_paper_events_created_at ON paper_events (created_at)"
            )
        )
        bind.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS idx_paper_events_paper_stage_created ON paper_events (paper_id, stage, created_at)"
            )
        )
        return

    op.create_table(
        "paper_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id"), nullable=False),
        sa.Column("stage", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("meta_json", sa.String(), nullable=True),
        sa.Column("log_path", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_paper_events_paper_id", "paper_events", ["paper_id"], unique=False)
    op.create_index("ix_paper_events_stage", "paper_events", ["stage"], unique=False)
    op.create_index("ix_paper_events_status", "paper_events", ["status"], unique=False)
    op.create_index("ix_paper_events_created_at", "paper_events", ["created_at"], unique=False)
    op.create_index(
        "idx_paper_events_paper_stage_created",
        "paper_events",
        ["paper_id", "stage", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""

    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        bind.execute(sa.text("DROP TABLE IF EXISTS paper_events"))
        return

    op.drop_index("idx_paper_events_paper_stage_created", table_name="paper_events")
    op.drop_index("ix_paper_events_created_at", table_name="paper_events")
    op.drop_index("ix_paper_events_status", table_name="paper_events")
    op.drop_index("ix_paper_events_stage", table_name="paper_events")
    op.drop_index("ix_paper_events_paper_id", table_name="paper_events")
    op.drop_table("paper_events")
