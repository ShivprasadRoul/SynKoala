"""journey capture

Revision ID: 2d1b11d73d95
Revises: 1c46bd1eb5d3
Create Date: 2026-09-12 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2d1b11d73d95"
down_revision: str | None = "1c46bd1eb5d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("intended_path", sa.dialects.postgresql.JSONB(), nullable=True))
    op.add_column(
        "simulation_runs",
        sa.Column("source", sa.String(), nullable=False, server_default="SYNTHETIC"),
    )
    op.create_check_constraint(
        "ck_simulation_runs_source",
        "simulation_runs",
        "source IN ('SYNTHETIC', 'HUMAN')",
    )
    op.alter_column("participant_runs", "participant_id", nullable=True)
    op.add_column("participant_runs", sa.Column("tester_label", sa.String(), nullable=True))
    op.add_column("participant_runs", sa.Column("voice_note_url", sa.String(), nullable=True))
    op.add_column("observations", sa.Column("screen_figma_node_id", sa.String(), nullable=True))
    op.add_column("observations", sa.Column("element_figma_node_id", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("observations", "element_figma_node_id")
    op.drop_column("observations", "screen_figma_node_id")
    op.drop_column("participant_runs", "voice_note_url")
    op.drop_column("participant_runs", "tester_label")
    op.alter_column("participant_runs", "participant_id", nullable=False)
    op.drop_constraint("ck_simulation_runs_source", "simulation_runs", type_="check")
    op.drop_column("simulation_runs", "source")
    op.drop_column("tasks", "intended_path")
