"""behavioural hypotheses on profile snapshots

Revision ID: 0018
Revises: 0017
Create Date: 2026-09-28

Adds ``player_profiles.behavioural_hypotheses``: measured tendencies about *when*
this player's decisions go wrong, each compared against their own baseline and
carrying the pattern ids that fired in exactly those situations.

Stored on the snapshot rather than recomputed per request for the same reason the
rest of the snapshot is: it is a measurement with a timestamp, and a coach answer
must be explainable against the snapshot it was built from.

Additive and nullable — existing snapshots simply have no hypotheses until rebuilt.
"""

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "player_profiles",
        sa.Column("behavioural_hypotheses", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("player_profiles", "behavioural_hypotheses")
