"""add study population_size

Revision ID: 7b37ad1adc60
Revises: 2d1b11d73d95
Create Date: 2026-09-12 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7b37ad1adc60"
down_revision: str | None = "2d1b11d73d95"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("studies", sa.Column("population_size", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("studies", "population_size")
