"""add source_document_id to findings

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-19 18:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add source_document_id column, foreign key, and index to findings table."""
    op.add_column(
        'findings',
        sa.Column(
            'source_document_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('documents.id', ondelete='SET NULL'),
            nullable=True,
        )
    )
    op.create_index('ix_findings_source_document_id', 'findings', ['source_document_id'], unique=False)


def downgrade() -> None:
    """Remove source_document_id column, foreign key, and index from findings table."""
    op.drop_index('ix_findings_source_document_id', table_name='findings')
    op.drop_column('findings', 'source_document_id')
