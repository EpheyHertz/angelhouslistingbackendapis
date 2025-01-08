"""Added cascading

Revision ID: cee684ab541d
Revises: f2059376080d
Create Date: 2024-12-13 17:45:41.863004

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cee684ab541d'
down_revision: Union[str, None] = 'f2059376080d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('bookings_user_id_fkey', 'bookings', type_='foreignkey')
    op.drop_constraint('bookings_house_id_fkey', 'bookings', type_='foreignkey')
    op.create_foreign_key(None, 'bookings', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key(None, 'bookings', 'houses', ['house_id'], ['id'], ondelete='CASCADE')
    op.drop_constraint('cart_house_id_fkey', 'cart', type_='foreignkey')
    op.drop_constraint('cart_user_id_fkey', 'cart', type_='foreignkey')
    op.create_foreign_key(None, 'cart', 'houses', ['house_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key(None, 'cart', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.alter_column('houses', 'price',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.alter_column('houses', 'room_count',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.drop_constraint('houses_owner_id_fkey', 'houses', type_='foreignkey')
    op.create_foreign_key(None, 'houses', 'users', ['owner_id'], ['id'], ondelete='CASCADE')
    op.drop_constraint('likes_user_id_fkey', 'likes', type_='foreignkey')
    op.drop_constraint('likes_house_id_fkey', 'likes', type_='foreignkey')
    op.create_foreign_key(None, 'likes', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key(None, 'likes', 'houses', ['house_id'], ['id'], ondelete='CASCADE')
    op.drop_constraint('logs_user_id_fkey', 'logs', type_='foreignkey')
    op.create_foreign_key(None, 'logs', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.drop_constraint('refresh_tokens_user_id_fkey', 'refresh_tokens', type_='foreignkey')
    op.create_foreign_key(None, 'refresh_tokens', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.alter_column('reviews', 'rating',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.drop_constraint('reviews_house_id_fkey', 'reviews', type_='foreignkey')
    op.drop_constraint('reviews_user_id_fkey', 'reviews', type_='foreignkey')
    op.create_foreign_key(None, 'reviews', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key(None, 'reviews', 'houses', ['house_id'], ['id'], ondelete='CASCADE')
    op.create_index(op.f('ix_users_is_verified'), 'users', ['is_verified'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_users_is_verified'), table_name='users')
    op.drop_constraint(None, 'reviews', type_='foreignkey')
    op.drop_constraint(None, 'reviews', type_='foreignkey')
    op.create_foreign_key('reviews_user_id_fkey', 'reviews', 'users', ['user_id'], ['id'])
    op.create_foreign_key('reviews_house_id_fkey', 'reviews', 'houses', ['house_id'], ['id'])
    op.alter_column('reviews', 'rating',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.drop_constraint(None, 'refresh_tokens', type_='foreignkey')
    op.create_foreign_key('refresh_tokens_user_id_fkey', 'refresh_tokens', 'users', ['user_id'], ['id'])
    op.drop_constraint(None, 'logs', type_='foreignkey')
    op.create_foreign_key('logs_user_id_fkey', 'logs', 'users', ['user_id'], ['id'])
    op.drop_constraint(None, 'likes', type_='foreignkey')
    op.drop_constraint(None, 'likes', type_='foreignkey')
    op.create_foreign_key('likes_house_id_fkey', 'likes', 'houses', ['house_id'], ['id'])
    op.create_foreign_key('likes_user_id_fkey', 'likes', 'users', ['user_id'], ['id'])
    op.drop_constraint(None, 'houses', type_='foreignkey')
    op.create_foreign_key('houses_owner_id_fkey', 'houses', 'users', ['owner_id'], ['id'])
    op.alter_column('houses', 'room_count',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.alter_column('houses', 'price',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.drop_constraint(None, 'cart', type_='foreignkey')
    op.drop_constraint(None, 'cart', type_='foreignkey')
    op.create_foreign_key('cart_user_id_fkey', 'cart', 'users', ['user_id'], ['id'])
    op.create_foreign_key('cart_house_id_fkey', 'cart', 'houses', ['house_id'], ['id'])
    op.drop_constraint(None, 'bookings', type_='foreignkey')
    op.drop_constraint(None, 'bookings', type_='foreignkey')
    op.create_foreign_key('bookings_house_id_fkey', 'bookings', 'houses', ['house_id'], ['id'])
    op.create_foreign_key('bookings_user_id_fkey', 'bookings', 'users', ['user_id'], ['id'])
    # ### end Alembic commands ###
