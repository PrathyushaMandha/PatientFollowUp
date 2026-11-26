"""add voice recordings

Revision ID: d136a4cbe027
Revises: a762c8f91b40
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "d136a4cbe027"
down_revision: str | None = "a762c8f91b40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "voice_recordings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=36), nullable=False),
        sa.Column("consultation_id", sa.Integer(), nullable=False),
        sa.Column("recorded_by_user_id", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("sysutcdatetime()"), nullable=False),
        sa.ForeignKeyConstraint(["consultation_id"], ["consultations.id"]),
        sa.ForeignKeyConstraint(["recorded_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_voice_recordings_consultation_id", "voice_recordings", ["consultation_id"])
    op.create_index("ix_voice_recordings_public_id", "voice_recordings", ["public_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_voice_recordings_public_id", table_name="voice_recordings")
    op.drop_index("ix_voice_recordings_consultation_id", table_name="voice_recordings")
    op.drop_table("voice_recordings")