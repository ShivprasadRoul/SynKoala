"""analytics engine columns: simulation_runs.task_id, metrics.screen_id

Revision ID: 9a3f2c7e1b04
Revises: 7b37ad1adc60
Create Date: 2026-09-12 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9a3f2c7e1b04"
down_revision: str | None = "7b37ad1adc60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("simulation_runs", sa.Column("task_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_simulation_runs_task_id", "simulation_runs", "tasks", ["task_id"], ["id"]
    )
    op.add_column("metrics", sa.Column("screen_id", sa.UUID(), nullable=True))
    op.create_foreign_key("fk_metrics_screen_id", "metrics", "screens", ["screen_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_metrics_screen_id", "metrics", type_="foreignkey")
    op.drop_column("metrics", "screen_id")
    op.drop_constraint("fk_simulation_runs_task_id", "simulation_runs", type_="foreignkey")
    op.drop_column("simulation_runs", "task_id")
