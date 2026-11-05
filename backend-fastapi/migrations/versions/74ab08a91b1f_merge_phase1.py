"""merge_phase1

Revision ID: 74ab08a91b1f
Revises: 60bf177ba117, f8e7d6c5b4a3
Create Date: 2026-11-05 15:37:58.360264

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '74ab08a91b1f'
down_revision: Union[str, Sequence[str], None] = ('60bf177ba117', 'f8e7d6c5b4a3')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
