"""Add original citizen location_text to reports.

Revision ID: d3e0f1a7g4c3
Revises: c2d9e0a6f3b2
Create Date: 2026-08-31 20:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d3e0f1a7g4c3"
down_revision: Union[str, None] = "c2d9e0a6f3b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("reports", sa.Column("location_text", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("reports", "location_text")
