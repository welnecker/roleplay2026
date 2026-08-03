from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from services.editorial_engine.models import NarrativeEffect, TransitionRule
from services.editorial_runtime_types import EditorialScript, EditorialState, EditorialTurn


@dataclass(frozen=True, slots=True)
class BeatContext:
    source_beat_id: str
    target_beat_id: str
    objective: str
    canonical_line: str
    dramatic_direction: str
    user_intent: str
    transition_status: str
    required_outcomes: tuple[str, ...]
    forbidden_outcomes: tuple[str, ...]
    relevant_facts: Mapping[str, str]
    max_sentences: int
    max_questions: int
    response_boundary: str


def _dialogue_fields(beat: Mapping[str, Any]) -> tuple[str, str]:
    for unit in beat.get("units", []) or []:
        if isinstance(unit, Mapping) and unit.get("kind") == "dialogue":
            return (
                str(unit.get("anchor") or unit.get("text") or "").strip(),
                str(unit.get("instruction") or "").strip(),
            )
    return "", ""


def _selected_narrative_effect(
    source: Mapping[str, Any],
    *,
    user_intent: str,
    target_id: str,
) -> NarrativeEffect:
    rules = [
        rule
        for rule in source.get("transition_rules", ()) or ()
        if isinstance(rule, TransitionRule)
    ]
    rules.sort(key=lambda rule: -rule.priority)
    for rule in rules:
        intent_matches = not rule.condition.intent or rule.condition.intent == user_intent
        target_matches = (rule.stay and target_id == str(source.get("beat_id", ""))) or (
            not rule.stay and rule.next_beat_id == target_id
        )
        if intent_matches and target_matches:
            return rule.narrative_effect
    return NarrativeEffect()


def build_beat_context(
    script: EditorialScript,
    previous_state: EditorialState,
    turn: EditorialTurn,
) -> BeatContext:
    """Constrói o contrato narrativo universal do turno."""

    source_id = previous_state.node_id or script.first_beat_id
    target_id = turn.target_id or source_id
    source = script.beats.get(source_id) or {}
    target = script.beats.get(target_id) or source
    canonical_line, dramatic_direction = _dialogue_fields(target)
    user_intent = str(turn.state.facts.get("_last_user_intent", "") or "").strip()
    effect = _selected_narrative_effect(
        source,
        user_intent=user_intent,
        target_id=target_id,
    )
    facts = {
        str(key): str(value)
        for key, value in turn.state.facts.items()
        if not str(key).startswith("_pending_")
    }

    return BeatContext(
        source_beat_id=source_id,
        target_beat_id=target_id,
        objective=str(target.get("objective") or source.get("objective") or "").strip(),
        canonical_line=canonical_line,
        dramatic_direction=dramatic_direction,
        user_intent=user_intent,
        transition_status=effect.status,
        required_outcomes=effect.required_outcomes,
        forbidden_outcomes=effect.forbidden_outcomes,
        relevant_facts=facts,
        max_sentences=int(target.get("max_sentences", 0) or 0),
        max_questions=int(target.get("max_questions", 0) or 0),
        response_boundary=str(target.get("response_boundary", "") or "").strip(),
    )


def render_beat_context(context: BeatContext) -> str:
    lines = [
        "CONTRATO DO BEAT ATUAL:",
        f"- Beat de origem: {context.source_beat_id}",
        f"- Beat alvo: {context.target_beat_id}",
    ]
    if context.objective:
        lines.append(f"- Movimento obrigatório: {context.objective}")
    if context.canonical_line:
        lines.append(f"- Referência semântica: {context.canonical_line}")
    if context.dramatic_direction:
        lines.append(f"- Direção dramática: {context.dramatic_direction}")
    if context.user_intent:
        lines.append(f"- Intenção detectada do usuário: {context.user_intent}")
    if context.transition_status:
        lines.append(f"- Estado da transição: {context.transition_status}")
    if context.required_outcomes:
        lines.append("- Resultados obrigatórios nesta resposta:")
        lines.extend(f"  - {item}" for item in context.required_outcomes)
    if context.forbidden_outcomes:
        lines.append("- Resultados proibidos nesta resposta:")
        lines.extend(f"  - {item}" for item in context.forbidden_outcomes)
    if context.max_sentences:
        lines.append(f"- Máximo de frases: {context.max_sentences}")
    if context.max_questions:
        lines.append(f"- Máximo de perguntas: {context.max_questions}")
    if context.response_boundary:
        lines.append(f"- Limite de resposta: {context.response_boundary}")
    lines.extend(
        (
            "- Não invente detalhes concretos ausentes dos fatos confirmados.",
            "- Não antecipe acontecimentos, locais ou decisões de beats posteriores.",
            "- A referência semântica orienta o sentido; não a repita mecanicamente.",
        )
    )
    return "\n".join(lines)


__all__ = ["BeatContext", "build_beat_context", "render_beat_context"]
