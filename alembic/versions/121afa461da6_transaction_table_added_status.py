"""transaction table added status 

Revision ID: 121afa461da6
Revises: 7db732f10bbc
Create Date: 2025-03-11 11:42:45.167198

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '121afa461da6'
down_revision: Union[str, None] = '7db732f10bbc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Define the Enum type
transaction_status_enum = sa.Enum('PENDING', 'COMPLETED', 'FAILED', name='transactionstatus')

def upgrade() -> None:
    # Create the ENUM type first if it doesn't exist
    transaction_status_enum.create(op.get_bind(), checkfirst=True)

    # Now add the column with the ENUM type
    op.add_column('transactions', sa.Column('status', transaction_status_enum, nullable=False, server_default='PENDING'))


def downgrade() -> None:
    # Drop the column first
    op.drop_column('transactions', 'status')

    # Then drop the ENUM type
    transaction_status_enum.drop(op.get_bind(), checkfirst=True)
