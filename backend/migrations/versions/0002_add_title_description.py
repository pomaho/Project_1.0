"""add title and description to files

Revision ID: 0002_add_title_description
Revises: 0001_initial
Create Date: 2024-03-01 00:10:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_add_title_description"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("files", sa.Column("title", sa.Text(), nullable=True))
    op.add_column("files", sa.Column("description", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("files", "description")
    op.drop_column("files", "title")
