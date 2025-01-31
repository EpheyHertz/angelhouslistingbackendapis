"""added verification table

Revision ID: 07be882db574
Revises: 79ab331478a0
Create Date: 2025-01-12 03:50:10.116589

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '07be882db574'
down_revision: Union[str, None] = '79ab331478a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
