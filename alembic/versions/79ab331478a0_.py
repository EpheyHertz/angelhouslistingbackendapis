"""empty message

Revision ID: 79ab331478a0
Revises: 1e5664ab6523
Create Date: 2025-01-10 22:52:04.680842

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '79ab331478a0'
down_revision: Union[str, None] = '1e5664ab6523'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
