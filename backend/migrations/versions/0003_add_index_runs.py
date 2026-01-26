"""add index_runs table

Revision ID: 0003_add_index_runs
Revises: 0002_add_title_description
Create Date: 2024-03-01 00:20:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_add_index_runs"
down_revision = "0002_add_title_description"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "index_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "status",
            sa.Enum("running", "completed", "failed", name="index_run_status"),
            nullable=False,
        ),
        sa.Column("scanned_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("restored_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deleted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("index_runs")
    op.execute("DROP TYPE IF EXISTS index_run_status")
