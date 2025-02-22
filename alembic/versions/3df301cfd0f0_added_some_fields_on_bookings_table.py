"""Added some fields on Bookings table

Revision ID: 3df301cfd0f0
Revises: c35fff1c41cf
Create Date: 2025-01-16 22:52:32.396607

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3df301cfd0f0'
down_revision: Union[str, None] = 'c35fff1c41cf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('bookings', sa.Column('guest_count', sa.Integer(), nullable=False))
    op.add_column('bookings', sa.Column('end_date', sa.DateTime(), nullable=False))
    op.add_column('bookings', sa.Column('special_request', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('bookings', 'special_request')
    op.drop_column('bookings', 'end_date')
    op.drop_column('bookings', 'guest_count')
    # ### end Alembic commands ###
