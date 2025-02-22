"""Added ondelete cascade functionality

Revision ID: b1831f581eb6
Revises: bd3ac6e7e1ae
Create Date: 2025-01-12 13:23:03.921237

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1831f581eb6'
down_revision: Union[str, None] = 'bd3ac6e7e1ae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('verification_codes_user_id_fkey', 'verification_codes', type_='foreignkey')
    op.create_foreign_key(None, 'verification_codes', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'verification_codes', type_='foreignkey')
    op.create_foreign_key('verification_codes_user_id_fkey', 'verification_codes', 'users', ['user_id'], ['id'])
    # ### end Alembic commands ###
