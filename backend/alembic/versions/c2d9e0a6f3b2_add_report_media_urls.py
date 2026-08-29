"""Add retained media URL list to reports.

Revision ID: c2d9e0a6f3b2
Revises: b1c8d9f5e2a1
Create Date: 2026-08-29 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c2d9e0a6f3b2"
down_revision: Union[str, None] = "b1c8d9f5e2a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("reports", sa.Column("media_urls", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("reports", "media_urls")
