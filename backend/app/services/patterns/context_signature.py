"""Context signatures: what "similar circumstances" means for a decision.

The point of the pattern engine is to recognise *"this player tends to make this
kind of decision when this kind of position occurs"* rather than *"this player
made the same move wrong three times"*. Two blunders in unrelated positions are
not a pattern, so events are grouped by the situation that produced them, not by
their label alone.

A signature is coarse on purpose: it must be stable enough that a player reaches
it repeatedly across games, and specific enough to describe a real situation.
Everything in it is a stored, deterministic feature of the move:

    phase | material band | ahead/behind | simplified | pawn structure | trigger

``structure`` is the stored pawn-skeleton key, which live data shows recurring
across dozens of games for a real player — exactly the repetition a pattern needs.
"""

from __future__ import annotations

from typing import Dict, Optional

# Ordinal ordering of material bands, so "ahead" and "behind" are distinct
# situations rather than one "clear material" bucket.
_BAND_ORDER = ("level", "slight", "clear", "decisive")


def material_state(features: Optional[Dict]) -> str:
    """Band + sign, e.g. ``ahead_slight`` / ``behind_clear`` / ``level``."""
    if not features:
        return "unknown"
    band = features.get("material_band")
    if band not in _BAND_ORDER:
        return "unknown"
    if band == "level":
        return "level"
    balance = features.get("material_balance")
    if not isinstance(balance, (int, float)):
        return band
    return f"{'ahead' if balance > 0 else 'behind'}_{band}"


def structure_bucket(features: Optional[Dict], structure_key: Optional[str]) -> str:
    """Pawn-structure bucket: the stored skeleton key, or a fallback marker."""
    if structure_key:
        return structure_key[:12]
    if features and features.get("simplified"):
        return "simplified"
    return "unknown"


def context_signature(
    *,
    phase: Optional[str],
    features: Optional[Dict],
    structure_key: Optional[str],
    has_opponent_trigger: bool,
) -> str:
    """Signature of the situation in which a decision was made.

    Deliberately excludes the event type: two different mistakes made in the same
    kind of position are the interesting signal, and the caller groups by
    ``(event_type, signature)`` when it wants type-specific patterns.

    The pawn structure is **not** part of the key. Measured on a real account,
    including it produced near-unique signatures — 4,302 decisions pooled into
    groups of eight or fewer, so nothing could ever reach a sample threshold.
    Groups must be broad enough to recur; the specific structures a player keeps
    reaching are reported as evidence instead (see the detector's ``structures``).
    """
    parts = [
        phase or "unknown",
        material_state(features),
        "simplified" if (features or {}).get("simplified") else "complex",
        "triggered" if has_opponent_trigger else "self-initiated",
    ]
    return "|".join(parts)


def describe_context(signature: str) -> str:
    """Plain-language description of a signature, for coach-facing text.

    Kept free of engine vocabulary: these strings surface in the app, and the
    product rule is that a player reads chess ideas, not centipawns.
    """
    parts = signature.split("|")
    if len(parts) != 4:
        return "in a recurring situation"

    phase, material, complexity, trigger = parts
    phase_text = {
        "opening": "in the opening",
        "middlegame": "in the middlegame",
        "endgame": "in the endgame",
    }.get(phase, "in the game")

    material_text = {
        "level": "with level material",
        "ahead_slight": "a little ahead",
        "ahead_clear": "clearly ahead",
        "ahead_decisive": "winning on material",
        "behind_slight": "a little behind",
        "behind_clear": "clearly behind",
        "behind_decisive": "lost on material",
    }.get(material, "with unclear material")

    complexity_text = (
        "in a simplified position" if complexity == "simplified" else "in a busy position"
    )
    trigger_text = (
        "right after the opponent's move created a threat"
        if trigger == "triggered"
        else "when you were free to choose a plan"
    )
    return f"{phase_text} {material_text}, {complexity_text}, {trigger_text}"
