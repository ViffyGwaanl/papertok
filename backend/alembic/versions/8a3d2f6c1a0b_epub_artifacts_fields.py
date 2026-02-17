"""epub artifacts fields

Revision ID: 8a3d2f6c1a0b
Revises: 936ae7e4dcdd
Create Date: 2026-02-17

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8a3d2f6c1a0b"
down_revision = "936ae7e4dcdd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("papers", sa.Column("epub_path_en", sa.String(), nullable=True))
    op.add_column("papers", sa.Column("epub_url_en", sa.String(), nullable=True))
    op.add_column("papers", sa.Column("epub_path_zh", sa.String(), nullable=True))
    op.add_column("papers", sa.Column("epub_url_zh", sa.String(), nullable=True))
    op.add_column("papers", sa.Column("epub_path_bilingual", sa.String(), nullable=True))
    op.add_column("papers", sa.Column("epub_url_bilingual", sa.String(), nullable=True))


def downgrade() -> None:
    # SQLite can't drop columns easily; keep downgrade as a no-op for MVP.
    pass
