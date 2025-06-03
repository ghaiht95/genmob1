"""fix_network_name_foreign_key

Revision ID: fccc4fd229a6
Revises: 33a320302769
Create Date: 2024-03-21 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


# revision identifiers, used by Alembic.
revision = 'fccc4fd229a6'
down_revision = '33a320302769'
branch_labels = None
depends_on = None


def upgrade():
    # Get a connection
    connection = op.get_bind()
    
    # 1. First drop the foreign key constraint from room table
    op.drop_constraint('room_network_name_fkey', 'room', type_='foreignkey')
    
    # 2. Then drop the unique constraint from network_config
    op.drop_constraint('uq_network_config_network_name', 'network_config', type_='unique')
    
    # 3. Add the new network_name column
    op.add_column('network_config', sa.Column('network_name', sa.String(length=100), nullable=True))
    
    # 4. Copy data from NETWORK_NAME to network_name
    connection.execute(text("""
        UPDATE network_config 
        SET network_name = NETWORK_NAME 
        WHERE NETWORK_NAME IS NOT NULL
    """))
    
    # 5. Drop the old NETWORK_NAME column
    op.drop_column('network_config', 'NETWORK_NAME')
    
    # 6. Add the unique constraint on network_name
    op.create_unique_constraint('uq_network_config_network_name', 'network_config', ['network_name'])
    
    # 7. Finally, add back the foreign key constraint
    op.create_foreign_key('room_network_name_fkey', 'room', 'network_config', ['network_name'], ['network_name'], ondelete='CASCADE')


def downgrade():
    # Get a connection
    connection = op.get_bind()
    
    # 1. First drop the foreign key constraint
    op.drop_constraint('room_network_name_fkey', 'room', type_='foreignkey')
    
    # 2. Drop the unique constraint
    op.drop_constraint('uq_network_config_network_name', 'network_config', type_='unique')
    
    # 3. Add back the old NETWORK_NAME column
    op.add_column('network_config', sa.Column('NETWORK_NAME', sa.String(length=100), nullable=True))
    
    # 4. Copy data back from network_name to NETWORK_NAME
    connection.execute(text("""
        UPDATE network_config 
        SET NETWORK_NAME = network_name 
        WHERE network_name IS NOT NULL
    """))
    
    # 5. Drop the new network_name column
    op.drop_column('network_config', 'network_name')
    
    # 6. Add back the unique constraint
    op.create_unique_constraint('uq_network_config_network_name', 'network_config', ['NETWORK_NAME'])
    
    # 7. Add back the foreign key constraint
    op.create_foreign_key('room_network_name_fkey', 'room', 'network_config', ['network_name'], ['NETWORK_NAME'], ondelete='CASCADE') 