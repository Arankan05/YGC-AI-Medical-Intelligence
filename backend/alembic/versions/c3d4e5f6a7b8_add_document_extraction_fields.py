"""add document extraction fields

Revision ID: c3d4e5f6a7b8
Revises: b1b8329252b7
Create Date: 2026-08-14 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b1b8329252b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add extracted_text, extraction_method, and page_count columns to documents table."""
    op.add_column('documents', sa.Column('extracted_text', sa.Text(), nullable=True))
    op.add_column('documents', sa.Column('extraction_method', sa.String(length=50), nullable=True))
    op.add_column('documents', sa.Column('page_count', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Remove extracted_text, extraction_method, and page_count columns from documents table."""
    op.drop_column('documents', 'page_count')
    op.drop_column('documents', 'extraction_method')
    op.drop_column('documents', 'extracted_text')
