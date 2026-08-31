"""Add AI analysis fields to reports

Revision ID: b1c8d9f5e2a1
Revises: a97bc4447c57
Create Date: 2026-08-29 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1c8d9f5e2a1'
down_revision: Union[str, None] = 'a97bc4447c57'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add AI analysis fields to reports table
    op.add_column('reports', sa.Column('ai_summary', sa.Text(), nullable=True))
    op.add_column('reports', sa.Column('ai_confidence', sa.Float(), nullable=True))
    op.add_column('reports', sa.Column('ai_image_findings', sa.JSON(), nullable=True))
    op.add_column('reports', sa.Column('ai_uncertainties', sa.JSON(), nullable=True))


def downgrade() -> None:
    # Remove AI analysis fields from reports table
    op.drop_column('reports', 'ai_uncertainties')
    op.drop_column('reports', 'ai_image_findings')
    op.drop_column('reports', 'ai_confidence')
    op.drop_column('reports', 'ai_summary')
