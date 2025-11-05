"""init

Revision ID: 4560b3029a3d
Revises: 
Create Date: 2025-10-20 18:05:48.947705

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4560b3029a3d'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # USERS
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('email', sa.String(length=180), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)

    # VEHICLES (create first WITHOUT the FK to bids to avoid cycle)
    op.create_table(
        'vehicles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('seller_id', sa.Integer(), nullable=False),
        sa.Column('make', sa.String(length=80), nullable=False),
        sa.Column('model', sa.String(length=80), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('base_price', sa.Integer(), nullable=False),
        sa.Column('lot_code', sa.String(length=20), nullable=False),
        sa.Column('images', sa.JSON(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('auction_start_at', sa.DateTime(), nullable=False),
        sa.Column('auction_end_at', sa.DateTime(), nullable=False),
        sa.Column('min_increment', sa.Integer(), nullable=False),
        sa.Column('winner_bid_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['seller_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # BIDS (now that vehicles exists, we can reference it)
    op.create_table(
        'bids',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('vehicle_id', sa.Integer(), nullable=False),
        sa.Column('bidder_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['bidder_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('bids', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_bids_bidder_id'), ['bidder_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_bids_vehicle_id'), ['vehicle_id'], unique=False)

    # Add the FK from vehicles.winner_bid_id -> bids.id AFTER bids table exists
    op.create_foreign_key(
        'fk_vehicles_winner_bid_id', 'vehicles', 'bids',
        ['winner_bid_id'], ['id']
    )

    # NOTIFICATIONS
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_notifications_user_id'), ['user_id'], unique=False)


def downgrade():
    # Drop indexes / constraints in reverse-safe order, then tables

    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_notifications_user_id'))
    op.drop_table('notifications')

    # vehicles has an FK to bids; drop that FK before dropping bids
    op.drop_constraint('fk_vehicles_winner_bid_id', 'vehicles', type_='foreignkey')

    with op.batch_alter_table('bids', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_bids_vehicle_id'))
        batch_op.drop_index(batch_op.f('ix_bids_bidder_id'))
    op.drop_table('bids')

    op.drop_table('vehicles')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_email'))
    op.drop_table('users')
