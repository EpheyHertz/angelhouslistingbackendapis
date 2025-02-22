"""Changed price to Decimal

Revision ID: 2733252c0eb3
Revises: d85feb1b4e54
Create Date: 2025-02-14 10:53:53.838319

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2733252c0eb3'
down_revision: Union[str, None] = 'd85feb1b4e54'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('houses', 'price',
               existing_type=sa.VARCHAR(),
               type_=sa.DECIMAL(),
               existing_nullable=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('houses', 'price',
               existing_type=sa.DECIMAL(),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    # ### end Alembic commands ###
