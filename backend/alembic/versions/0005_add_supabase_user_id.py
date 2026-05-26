"""add supabase_user_id to users (Supabase as canonical identity)

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-26 14:00:00.000000

Promotes Supabase Auth to the canonical identity for ChessIQ users.

Before this migration:
  - `chesscom_username` (NOT NULL, UNIQUE) was the de-facto user identity.
  - The Supabase Auth scaffold existed but never connected to local users.

After this migration:
  - `supabase_user_id` (UUID-as-string, UNIQUE, NULLABLE) is the
    foreign key into Supabase Auth. Every authenticated request resolves
    to a local users row via this column.
  - `chesscom_username` becomes NULLABLE so a user can exist
    immediately after Supabase sign-up, before linking Chess.com.

Stored as VARCHAR(36) for portability across Postgres (canonical) and
SQLite (developer fallback). The string is always the UUIDv4 emitted in
the Supabase JWT `sub` claim.
"""
from alembic import op
import sqlalchemy as sa


revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add the supabase_user_id column (nullable so existing rows pass).
    op.add_column(
        'users',
        sa.Column('supabase_user_id', sa.String(length=36), nullable=True),
    )

    # 2. Unique constraint + lookup index.
    op.create_unique_constraint(
        'uq_users_supabase_user_id', 'users', ['supabase_user_id']
    )
    op.create_index(
        'ix_users_supabase_user_id',
        'users',
        ['supabase_user_id'],
        unique=False,
    )

    # 3. Relax chesscom_username to NULLABLE. A new Supabase user exists
    #    before they link their Chess.com account. The UNIQUE constraint
    #    is preserved (Postgres treats NULLs as distinct under UNIQUE).
    #    batch_alter_table is used for SQLite compatibility (silent dev
    #    fallback noted in the audit).
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column(
            'chesscom_username',
            existing_type=sa.String(),
            nullable=True,
        )


def downgrade() -> None:
    # Restore chesscom_username NOT NULL. Will fail if any row has NULL,
    # which is the intended safety net (must backfill before downgrading).
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column(
            'chesscom_username',
            existing_type=sa.String(),
            nullable=False,
        )

    op.drop_index('ix_users_supabase_user_id', table_name='users')
    op.drop_constraint(
        'uq_users_supabase_user_id', 'users', type_='unique'
    )
    op.drop_column('users', 'supabase_user_id')
