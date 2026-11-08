from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '3991f2b40841'
down_revision: Union[str, Sequence[str], None] = '60bf177ba117'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    pass

def downgrade() -> None:
    pass
