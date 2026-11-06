"""merge_heads

Revision ID: 3991f2b40841
Revises: 60bf177ba117
Create Date: 2026-11-06 03:26:59.927700

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3991f2b40841'
down_revision: Union[str, Sequence[str], None] = '60bf177ba117'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
