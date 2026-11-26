"""enforce one active consultation per patient

Revision ID: a762c8f91b40
Revises: c2484246a61f
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "a762c8f91b40"
down_revision: str | None = "c2484246a61f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        WITH ranked_active AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY patient_id
                    ORDER BY started_at DESC, id DESC
                ) AS active_rank
            FROM consultations
            WHERE status = 'active'
        )
        UPDATE consultations
        SET status = 'cancelled',
            ended_at = COALESCE(ended_at, CURRENT_TIMESTAMP)
        WHERE id IN (
            SELECT id FROM ranked_active WHERE active_rank > 1
        )
        """
    )
    op.create_index(
        "uq_consultations_one_active_per_patient",
        "consultations",
        ["patient_id"],
        unique=True,
        mssql_where=sa.text("status = 'active'"),
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_consultations_one_active_per_patient",
        table_name="consultations",
    )