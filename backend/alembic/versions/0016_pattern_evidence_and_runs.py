"""pattern evidence, context signatures, run history and occurrence links

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-27

Makes patterns auditable and context-aware:

* ``player_patterns`` gains the evidence payload detectors used to compute and
  discard, the context signature a pattern describes, the opportunity count that
  turns a raw count into a rate, and the detector identity that produced it.
* ``pattern_occurrences`` links back to the move and event it came from, so a
  claim can be walked back to the engine evaluation behind it.
* ``pattern_runs`` records each detection run (previously patterns were upserted
  in place with no history, so nothing could be compared over time).
"""

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("player_patterns", sa.Column("evidence", sa.JSON(), nullable=True))
    op.add_column(
        "player_patterns", sa.Column("context_signature", sa.String(length=160), nullable=True)
    )
    op.add_column("player_patterns", sa.Column("opportunity_count", sa.Integer(), nullable=True))
    op.add_column("player_patterns", sa.Column("occurrence_rate", sa.Float(), nullable=True))
    op.add_column("player_patterns", sa.Column("detector_id", sa.String(length=40), nullable=True))
    op.add_column("player_patterns", sa.Column("detector_version", sa.Integer(), nullable=True))
    op.create_index(
        "ix_player_patterns_context_signature", "player_patterns", ["context_signature"]
    )

    op.add_column("pattern_occurrences", sa.Column("move_id", sa.Integer(), nullable=True))
    op.add_column("pattern_occurrences", sa.Column("event_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_pattern_occurrences_move_id",
        "pattern_occurrences",
        "game_moves",
        ["move_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_pattern_occurrences_event_id",
        "pattern_occurrences",
        "chess_events",
        ["event_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_pattern_occurrences_move_id", "pattern_occurrences", ["move_id"])
    op.create_index("ix_pattern_occurrences_event_id", "pattern_occurrences", ["event_id"])

    op.create_table(
        "pattern_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ran_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("detector_version", sa.String(length=40), nullable=False),
        sa.Column("games_considered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("decisions_considered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("patterns_detected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("strengths_detected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("summary", sa.JSON(), nullable=True),
    )
    op.create_index("ix_pattern_runs_user_ran_at", "pattern_runs", ["user_id", "ran_at"])


def downgrade() -> None:
    op.drop_table("pattern_runs")
    op.drop_index("ix_pattern_occurrences_event_id", table_name="pattern_occurrences")
    op.drop_index("ix_pattern_occurrences_move_id", table_name="pattern_occurrences")
    op.drop_constraint("fk_pattern_occurrences_event_id", "pattern_occurrences", type_="foreignkey")
    op.drop_constraint("fk_pattern_occurrences_move_id", "pattern_occurrences", type_="foreignkey")
    op.drop_column("pattern_occurrences", "event_id")
    op.drop_column("pattern_occurrences", "move_id")
    op.drop_index("ix_player_patterns_context_signature", table_name="player_patterns")
    for column in (
        "detector_version",
        "detector_id",
        "occurrence_rate",
        "opportunity_count",
        "context_signature",
        "evidence",
    ):
        op.drop_column("player_patterns", column)
