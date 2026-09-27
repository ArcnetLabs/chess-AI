"""Model-side evaluation: fixture probes, wired to the real context assembler.

Probes use the *actual* context path (`assemble_event_context`) and the *actual*
coach fixture positions, so what is measured is what production sends — not a
hand-written prompt that flatters the system.

The provider is chosen from the same environment the app uses. With no
credentials the runner reports that clearly and still emits the assembled
prompts, so the unmeasured gap is explicit.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.services.chat.event_context import assemble_event_context
from app.services.evaluation.model_eval import Probe, Provider, run_probes

# A real middlegame position and a real endgame position, used as the "current
# situation" in probes. FENs are fixed so probes are reproducible.
MIDDLEGAME_FEN = "r1bqkb1r/pp2pppp/2n2n2/3p4/3P4/2N2N2/PP2PPPP/R1BQKB1R w KQkq - 0 7"
ENDGAME_FEN = "8/5pk1/6p1/8/8/6P1/5PK1/8 w - - 0 40"

COACH_SYSTEM_PROMPT = (
    "You are ChessRun's chess coach. Stockfish is the only source of chess truth; "
    "explain and prioritise, never invent evaluations. Use the player's own "
    "history when it is provided, and say plainly when it is not."
)


def build_probes(db: Session, user_id: int) -> List[Probe]:
    """Assemble probes from the player's real context."""
    probes: List[Probe] = []

    for name, fen, question in (
        ("endgame_position", ENDGAME_FEN, "What should I be thinking about here?"),
        ("middlegame_position", MIDDLEGAME_FEN, "How should I proceed in this position?"),
    ):
        context = assemble_event_context(db, user_id, fen=fen)
        if not context:
            logger.warning(f"model-eval probe {name}: no context assembled")
            continue
        has_history = "Nothing on record" not in context
        probes.append(
            Probe(
                name=name,
                question=question,
                context=context,
                expects_history=has_history,
                expects_uncertainty=not has_history,
                notes="context assembled by the production path",
            )
        )

    # A deliberate no-history probe: a position far outside the player's
    # experience must produce an honest "this is new", not an invented pattern.
    probes.append(
        Probe(
            name="no_history_position",
            question="Have I had trouble in positions like this before?",
            context=(
                "## Player history for this position\n"
                "Nothing on record for this kind of position yet. Coach from the "
                "engine facts alone, and say plainly that this situation is new for "
                "the player."
            ),
            expects_history=False,
            expects_uncertainty=True,
            notes="the absence path, which the coach must state rather than fill",
        )
    )
    return probes


def _provider_from_settings() -> Optional[Provider]:
    """A provider built from the app's LLM configuration, if any is set."""
    import os

    if not any(
        os.getenv(key)
        for key in ("LLM_LOCAL_API_KEY", "OPENROUTER_API_KEY", "OPENAI_API_KEY")
    ):
        return None

    def provider(system_prompt: str, user_prompt: str) -> str:
        import asyncio

        from app.services.integration.ai_client import chat_completion_with_fallback

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})
        result = asyncio.run(chat_completion_with_fallback(messages))
        if isinstance(result, dict):
            return result.get("content") or ""
        return str(result)

    return provider


def run_model_eval(db: Session, user_id: int, *, provider: Optional[Provider] = None) -> Dict:
    """Run the model-side probes for one player."""
    probes = build_probes(db, user_id)
    if not probes:
        return {"provider": "unavailable", "probes": 0, "results": [], "reason": "no probes"}

    resolved = provider if provider is not None else _provider_from_settings()
    report = run_probes(db, probes, provider=resolved, system_prompt=COACH_SYSTEM_PROMPT)
    if resolved is None:
        report["reason"] = (
            "no LLM credentials in this environment (LLM_LOCAL_API_KEY / "
            "OPENROUTER_API_KEY / OPENAI_API_KEY); prompts were assembled but not sent"
        )
    return report
