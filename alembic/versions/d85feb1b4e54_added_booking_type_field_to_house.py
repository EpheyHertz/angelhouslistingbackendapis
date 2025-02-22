"""Added booking_type  field to house

Revision ID: d85feb1b4e54
Revises: 3740d7d991f0
Create Date: 2025-01-27 20:41:29.321576

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd85feb1b4e54'
down_revision: Union[str, None] = '3740d7d991f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('bookings', sa.Column('booking_type', sa.String(), nullable=False))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('bookings', 'booking_type')
    # ### end Alembic commands ###
