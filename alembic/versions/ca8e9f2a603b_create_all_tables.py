"""
Create all tables

Revision ID: ca8e9f2a603b
Revises: 
Create Date: 2024-12-09 18:57:42.010543
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM

# revision identifiers, used by Alembic.
revision = 'ca8e9f2a603b'
down_revision = None
branch_labels = None
depends_on = None

# Define ENUMs as Python objects for reuse
verification_status_enum = ENUM('pending', 'verified', 'rejected', name='verificationstatus', create_type=False)
user_role_enum = ENUM('admin', 'house_owner', 'regular_user', name='userrole', create_type=False)
social_auth_provider_enum = ENUM('local', 'google', name='socialauthprovider', create_type=False)
house_type_enum = ENUM('bedsitter', 'single_room', 'one_bedroom', 'two_bedroom', name='housetype', create_type=False)


def upgrade() -> None:
    # Create ENUM types if they don't already exist
    op.execute("""
    DO $$ 
    BEGIN 
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'verificationstatus') THEN
            CREATE TYPE verificationstatus AS ENUM ('pending', 'verified', 'rejected');
        END IF;
    END $$;
    """)

    op.execute("""
    DO $$ 
    BEGIN 
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'userrole') THEN
            CREATE TYPE userrole AS ENUM ('admin', 'house_owner', 'regular_user');
        END IF;
    END $$;
    """)

    op.execute("""
    DO $$ 
    BEGIN 
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'socialauthprovider') THEN
            CREATE TYPE socialauthprovider AS ENUM ('local', 'google');
        END IF;
    END $$;
    """)

    op.execute("""
    DO $$ 
    BEGIN 
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'housetype') THEN
            CREATE TYPE housetype AS ENUM ('bedsitter', 'single_room', 'one_bedroom', 'two_bedroom');
        END IF;
    END $$;
    """)

    # Create 'users' table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('username', sa.String, unique=True, index=True),
        sa.Column('full_name', sa.String),
        sa.Column('email', sa.String, unique=True, index=True),
        sa.Column('contact_number', sa.String),
        sa.Column('password', sa.String),
        sa.Column('profile_image', sa.String, nullable=True),
        sa.Column('location', sa.String),
        sa.Column('id_document_url', sa.String, nullable=True),
        sa.Column('verification_status', verification_status_enum, server_default='pending'),
        sa.Column('role', user_role_enum, server_default='regular_user'),
        sa.Column('is_verified', sa.Boolean, default=False),
        sa.Column('social_auth_provider', social_auth_provider_enum, server_default='local'),
        sa.Column('social_auth_id', sa.String, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now())
    )

    # Create 'houses' table
    op.create_table(
        'houses',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('title', sa.String, index=True),
        sa.Column('description', sa.String),
        sa.Column('price', sa.Integer),
        sa.Column('location', sa.String, index=True),
        sa.Column('image_urls', sa.ARRAY(sa.String)),
        sa.Column('owner_id', sa.Integer, sa.ForeignKey('users.id')),
        sa.Column('is_approved', sa.Boolean, default=False),
        sa.Column('availability', sa.Boolean, default=True),
        sa.Column('room_count', sa.Integer),
        sa.Column('type', house_type_enum),
        sa.Column('amenities', sa.ARRAY(sa.String)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now())
    )

    # Create 'reviews' table
    op.create_table(
        'reviews',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('rating', sa.Integer),
        sa.Column('comment', sa.String),
        sa.Column('house_id', sa.Integer, sa.ForeignKey('houses.id')),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now())
    )

    # Create 'logs' table
    op.create_table(
        'logs',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('action', sa.String),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id')),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

    # Create 'likes' table
    op.create_table(
        'likes',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('house_id', sa.Integer, sa.ForeignKey('houses.id')),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

    # Create 'refresh_tokens' table
    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('token', sa.String, unique=True, index=True),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id')),
    )


def downgrade() -> None:
    # Drop tables in reverse order of creation
    op.drop_table('refresh_tokens')
    op.drop_table('likes')
    op.drop_table('logs')
    op.drop_table('reviews')
    op.drop_table('houses')
    op.drop_table('users')

    # Drop ENUM types
    op.execute('DROP TYPE IF EXISTS verificationstatus;')
    op.execute('DROP TYPE IF EXISTS userrole;')
    op.execute('DROP TYPE IF EXISTS socialauthprovider;')
    op.execute('DROP TYPE IF EXISTS housetype;')
