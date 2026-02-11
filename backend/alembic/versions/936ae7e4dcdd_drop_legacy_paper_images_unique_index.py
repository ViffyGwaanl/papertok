"""drop legacy paper_images unique index

Revision ID: 936ae7e4dcdd
Revises: d27df05f0470
Create Date: 2026-02-11 16:59:47.062976

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '936ae7e4dcdd'
down_revision: Union[str, None] = 'd27df05f0470'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    bind = op.get_bind()

    # Some existing DBs may still have the old unique index without `lang`.
    # It conflicts with bilingual generation and must be removed.
    if bind.dialect.name == "sqlite":
        bind.execute(sa.text("DROP INDEX IF EXISTS idx_paper_images_paper_kind_provider_order"))
        return

    # Best-effort for other dialects
    try:
        op.drop_index(
            "idx_paper_images_paper_kind_provider_order",
            table_name="paper_images",
        )
    except Exception:
        pass


def downgrade() -> None:
    """Downgrade schema."""

    # We intentionally do not recreate the legacy index.
    return
