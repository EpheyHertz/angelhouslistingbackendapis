"""Create verification_codes table

Revision ID: bd3ac6e7e1ae
Revises: 07be882db574
Create Date: 2025-01-12 03:57:35.591942

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bd3ac6e7e1ae'
down_revision: Union[str, None] = '07be882db574'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('verification_codes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(), nullable=True),
    sa.Column('expiration_date', sa.DateTime(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_verification_codes_code'), 'verification_codes', ['code'], unique=False)
    op.create_index(op.f('ix_verification_codes_id'), 'verification_codes', ['id'], unique=False)
    op.alter_column('houses', 'price',
               existing_type=sa.INTEGER(),
               type_=sa.String(),
               existing_nullable=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('houses', 'price',
               existing_type=sa.String(),
               type_=sa.INTEGER(),
               existing_nullable=False)
    op.drop_index(op.f('ix_verification_codes_id'), table_name='verification_codes')
    op.drop_index(op.f('ix_verification_codes_code'), table_name='verification_codes')
    op.drop_table('verification_codes')
    # ### end Alembic commands ###
