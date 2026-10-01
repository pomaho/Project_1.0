"""add denormalized metadata state

Revision ID: 0004_add_metadata_state
Revises: 0003_add_index_runs
Create Date: 2026-10-01 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_add_metadata_state"
down_revision = "0003_add_index_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "files",
        sa.Column("keyword_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("files", sa.Column("metadata_checked_at", sa.DateTime(), nullable=True))
    op.add_column("files", sa.Column("metadata_error", sa.Text(), nullable=True))

    # This is the only scan of the large relation table. Future status requests
    # read the compact files table and its partial indexes instead.
    op.execute(
        """
        UPDATE files AS f
        SET keyword_count = counts.keyword_count
        FROM (
            SELECT file_id, COUNT(*)::integer AS keyword_count
            FROM file_keywords
            GROUP BY file_id
        ) AS counts
        WHERE counts.file_id = f.id
        """
    )
    op.execute("UPDATE files SET metadata_checked_at = updated_at")

    op.create_index(
        "ix_files_active_missing_keywords_mtime",
        "files",
        [sa.text("mtime DESC")],
        postgresql_where=sa.text("deleted_at IS NULL AND keyword_count = 0"),
    )
    op.create_index(
        "ix_files_active_missing_text",
        "files",
        ["id"],
        postgresql_where=sa.text(
            "deleted_at IS NULL AND "
            "(trim(coalesce(title, '')) = '' OR trim(coalesce(description, '')) = '')"
        ),
    )
    op.create_index(
        "ix_files_active_missing_shot_at",
        "files",
        ["id"],
        postgresql_where=sa.text("deleted_at IS NULL AND shot_at IS NULL"),
    )
    op.create_index(
        "ix_files_active_pending_metadata",
        "files",
        ["id"],
        postgresql_where=sa.text(
            "deleted_at IS NULL AND "
            "(metadata_checked_at IS NULL OR metadata_checked_at < mtime)"
        ),
    )


def downgrade() -> None:
    op.drop_index("ix_files_active_pending_metadata", table_name="files")
    op.drop_index("ix_files_active_missing_shot_at", table_name="files")
    op.drop_index("ix_files_active_missing_text", table_name="files")
    op.drop_index("ix_files_active_missing_keywords_mtime", table_name="files")
    op.drop_column("files", "metadata_error")
    op.drop_column("files", "metadata_checked_at")
    op.drop_column("files", "keyword_count")
