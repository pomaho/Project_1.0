"""initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2024-03-01 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.Enum("admin", "editor", "viewer", name="role"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "files",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "storage_mode",
            sa.Enum("filesystem", "minio", name="storage_mode"),
            nullable=False,
        ),
        sa.Column("original_key", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("ext", sa.String(length=16), nullable=False),
        sa.Column("mime", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("mtime", sa.DateTime(), nullable=False),
        sa.Column("sha1", sa.String(length=40), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column(
            "orientation",
            sa.Enum("portrait", "landscape", "square", "unknown", name="orientation"),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column("shot_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("duplicate_of", sa.String(length=36), sa.ForeignKey("files.id"), nullable=True),
    )
    op.create_index("ix_files_original_key", "files", ["original_key"], unique=True)

    op.create_table(
        "keywords",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("value_norm", sa.Text(), nullable=False),
        sa.Column("value_display", sa.Text(), nullable=False),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_keywords_value_norm", "keywords", ["value_norm"], unique=True)

    op.create_table(
        "file_keywords",
        sa.Column("file_id", sa.String(length=36), sa.ForeignKey("files.id"), primary_key=True),
        sa.Column("keyword_id", sa.String(length=36), sa.ForeignKey("keywords.id"), primary_key=True),
        sa.UniqueConstraint("file_id", "keyword_id", name="uq_file_keyword"),
    )

    op.create_table(
        "previews",
        sa.Column("file_id", sa.String(length=36), sa.ForeignKey("files.id"), primary_key=True),
        sa.Column("thumb_key", sa.Text(), nullable=False),
        sa.Column("medium_key", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "action",
            sa.Enum(
                "login",
                "search",
                "download",
                "keywords_update",
                "user_manage",
                "reindex",
                "rescan",
                name="audit_action",
            ),
            nullable=False,
        ),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("previews")
    op.drop_table("file_keywords")
    op.drop_index("ix_keywords_value_norm", table_name="keywords")
    op.drop_table("keywords")
    op.drop_index("ix_files_original_key", table_name="files")
    op.drop_table("files")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS audit_action")
    op.execute("DROP TYPE IF EXISTS orientation")
    op.execute("DROP TYPE IF EXISTS storage_mode")
    op.execute("DROP TYPE IF EXISTS role")
