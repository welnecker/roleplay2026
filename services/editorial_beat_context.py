from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from services.editorial_engine.models import NarrativeEffect, TransitionRule
from services.editorial_interaction_context import (
    ResolvedInteractionContext,
    resolve_interaction_context,
)
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
    allowed_topics: tuple[str, ...]
    confirmed_facts: tuple[str, ...]
    unknown_facts: tuple[str, ...]
    max_sentences: int
    max_questions: int
    response_boundary: str
    strict_response_economy: bool = False
    max_extra_words: int = 0
    authored_thought: str = ""
    exact_speech: str = ""
    free_speech: bool = False
    interpreted_speech: bool = False
    interpreted_thought: bool = False
    authored_transition: str = ""
    forbidden_literal_texts: tuple[str, ...] = ()
    forbid_new_questions: bool = False
    character_name: str = "Mary"
    interaction_context: ResolvedInteractionContext = field(
        default_factory=ResolvedInteractionContext
    )


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        item = value.strip()
        return (item,) if item else ()
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _dialogue_fields(beat: Mapping[str, Any]) -> tuple[str, str]:
    for unit in beat.get("units", []) or []:
        if isinstance(unit, Mapping) and unit.get("kind") == "dialogue":
            return (
                str(unit.get("anchor") or unit.get("text") or "").strip(),
                str(unit.get("instruction") or "").strip(),
            )
    return "", ""


def _fact_is_true(facts: Mapping[str, Any], name: str) -> bool:
    return bool(str(facts.get(str(name), "") or "").strip())


def _selected_fact_variant(
    beat: Mapping[str, Any],
    facts: Mapping[str, Any],
) -> Mapping[str, Any]:
    constraints = beat.get("constraints") or {}
    if not isinstance(constraints, Mapping):
        constraints = {}
    variants = beat.get("fact_variants") or constraints.get("fact_variants") or ()
    if not isinstance(variants, (list, tuple)):
        return {}
    for variant in variants:
        if not isinstance(variant, Mapping):
            continue
        required = _string_tuple(variant.get("when_all_facts"))
        absent = _string_tuple(variant.get("when_no_facts"))
        if required and not all(_fact_is_true(facts, name) for name in required):
            continue
        if absent and any(_fact_is_true(facts, name) for name in absent):
            continue
        return variant
    return {}


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


def _declared_tuple(
    source: Mapping[str, Any],
    target: Mapping[str, Any],
    field: str,
    *,
    legacy_field: str = "",
) -> tuple[str, ...]:
    target_constraints = target.get("constraints") or {}
    source_constraints = source.get("constraints") or {}
    if not isinstance(target_constraints, Mapping):
        target_constraints = {}
    if not isinstance(source_constraints, Mapping):
        source_constraints = {}
    values = (
        _string_tuple(target.get(field))
        or _string_tuple(target_constraints.get(field))
        or _string_tuple(source.get(field))
        or _string_tuple(source_constraints.get(field))
    )
    if values or not legacy_field:
        return values
    return (
        _string_tuple(target.get(legacy_field))
        or _string_tuple(target_constraints.get(legacy_field))
        or _string_tuple(source.get(legacy_field))
        or _string_tuple(source_constraints.get(legacy_field))
    )


def _state_facts(state: EditorialState) -> tuple[str, ...]:
    facts: list[str] = []
    for key, value in state.facts.items():
        name = str(key).strip()
        text = str(value).strip()
        if not name or not text:
            continue
        if name == "_scene_location":
            facts.append(f"local da cena: {text}")
        elif not name.startswith("_"):
            facts.append(f"{name}: {text}")
    return tuple(facts)


def build_beat_context(
    script: EditorialScript,
    previous_state: EditorialState,
    turn: EditorialTurn,
) -> BeatContext:
    """Constrói contrato factual e relacional a partir de dados declarados."""

    source_id = previous_state.node_id or script.first_beat_id
    target_id = turn.target_id or source_id
    source = script.beats.get(source_id) or {}
    target = script.beats.get(target_id) or source
    canonical_line, dramatic_direction = _dialogue_fields(target)
    objective = str(target.get("objective") or source.get("objective") or "").strip()
    variant = _selected_fact_variant(target, turn.state.facts)
    if variant:
        objective = str(variant.get("required_movement") or objective).strip()
        canonical_line = str(variant.get("canonical_line") or canonical_line).strip()
        dramatic_direction = str(
            variant.get("dramatic_direction") or dramatic_direction
        ).strip()
    user_intent = str(turn.state.facts.get("_last_user_intent", "") or "").strip()
    effect = _selected_narrative_effect(source, user_intent=user_intent, target_id=target_id)
    declared_confirmed = _declared_tuple(source, target, "confirmed_facts")
    interaction_context = resolve_interaction_context(
        target.get("interaction_context") or source.get("interaction_context") or {},
        turn.state.facts,
    )
    exact_speech = str(target.get("exact_speech", "") or "").strip()
    free_speech = bool(target.get("free_speech", False))
    required_outcomes = effect.required_outcomes
    if canonical_line and not exact_speech and not free_speech:
        required_outcomes = tuple(
            dict.fromkeys(
                (
                    *required_outcomes,
                    "reagir brevemente ao sentido do conteúdo mais recente do usuário antes ou junto da fala autoral adaptada",
                    "preservar reconhecivelmente a fala autoral e completar todas as finalidades pendentes do movimento obrigatório",
                )
            )
        )
    return BeatContext(
        source_beat_id=source_id,
        target_beat_id=target_id,
        objective=objective,
        canonical_line=canonical_line,
        dramatic_direction=dramatic_direction,
        user_intent=user_intent,
        transition_status=effect.status,
        required_outcomes=required_outcomes,
        forbidden_outcomes=effect.forbidden_outcomes,
        allowed_topics=_declared_tuple(source, target, "allowed_topics", legacy_field="fact_scope"),
        confirmed_facts=tuple(dict.fromkeys((*declared_confirmed, *_state_facts(turn.state)))),
        unknown_facts=_declared_tuple(source, target, "unknown_facts"),
        max_sentences=int(target.get("max_sentences", 0) or 0),
        max_questions=int(target.get("max_questions", 0) or 0),
        response_boundary=str(target.get("response_boundary", "") or "").strip(),
        strict_response_economy=bool(
            target.get("strict_response_economy", False)
        ),
        max_extra_words=max(0, int(target.get("max_extra_words", 0) or 0)),
        authored_thought=str(target.get("authored_thought", "") or "").strip(),
        exact_speech=exact_speech,
        free_speech=free_speech,
        interpreted_speech=bool(target.get("interpreted_speech", False)),
        interpreted_thought=bool(target.get("interpreted_thought", False)),
        authored_transition=str(
            target.get("authored_transition", "") or ""
        ).strip(),
        character_name=str(
            (script.raw.get("character") or {}).get("name", "Mary")
            or "Mary"
        ),
        interaction_context=interaction_context,
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

    relational = context.interaction_context
    lines.extend(
        (
            "- CONTEXTO RELACIONAL EFETIVO:",
            f"  - estágio da relação: {relational.relationship_stage}",
            f"  - ambiente: {relational.setting}",
            f"  - privacidade: {relational.privacy}",
            f"  - nível de intimidade: {relational.intimacy_level}",
            f"  - desejo de {context.character_name} revelado: {'sim' if relational.mary_disclosed_desire else 'não'}",
            f"  - atração mútua confirmada: {'sim' if relational.mutual_attraction_confirmed else 'não'}",
        )
    )
    if relational.allowed_interactions:
        lines.append("  - interações compatíveis declaradas:")
        lines.extend(f"    - {item}" for item in relational.allowed_interactions)
    if relational.recoverable_tensions:
        lines.append("  - tensões recuperáveis declaradas:")
        lines.extend(f"    - {item}" for item in relational.recoverable_tensions)
    if relational.terminal_violations:
        lines.append("  - rupturas terminais declaradas para este contexto:")
        lines.extend(f"    - {item}" for item in relational.terminal_violations)
    if relational.immediate_endings:
        lines.append("  - violações de encerramento imediato:")
        lines.extend(f"    - {item}" for item in relational.immediate_endings)
    if relational.applied_progressions:
        lines.append("  - progressões ativadas por fatos confirmados:")
        lines.extend(f"    - {item}" for item in relational.applied_progressions)

    lines.append("- FATOS CONFIRMADOS — podem ser afirmados:")
    lines.extend(f"  - {item}" for item in context.confirmed_facts) if context.confirmed_facts else lines.append("  - nenhum fato adicional confirmado")
    lines.append("- FATOS DESCONHECIDOS — não podem ser concretizados:")
    lines.extend(f"  - {item}" for item in context.unknown_facts) if context.unknown_facts else lines.append("  - nenhum declarado")
    if context.allowed_topics:
        lines.append("- ASSUNTOS PERMITIDOS — delimitam o tema, não criam fatos:")
        lines.extend(f"  - {item}" for item in context.allowed_topics)
    if context.max_sentences:
        lines.append(f"- Máximo de frases: {context.max_sentences}")
    if context.max_questions:
        lines.append(f"- Máximo de perguntas: {context.max_questions}")
    if context.response_boundary:
        lines.append(f"- Limite de resposta: {context.response_boundary}")
    if context.strict_response_economy:
        lines.append(
            "- Economia de estilo: seja breve e evite somente conteúdo sem função narrativa. "
            "Esta orientação não impede reagir ao usuário nem acrescentar pergunta, pedido ou "
            "complemento necessário para realizar o movimento obrigatório do beat."
        )
        if context.max_extra_words:
            lines.append(
                f"- Referência de concisão: prefira até {context.max_extra_words} palavras adicionais, "
                "mas ultrapasse esse valor quando necessário para responder ao usuário e cumprir o beat."
            )
    if context.free_speech:
        lines.append(
            "- Fala livre autoral: concretize a direção dramática com liberdade de redação, "
            "respeitando os fatos e o máximo de frases, sem limite relativo de palavras."
        )
    elif context.interpreted_speech:
        lines.extend(
            (
                "- Fala interpretada: use a fala autoral como núcleo obrigatório e reconhecível, mas desenvolva uma atuação intensa, humana e particular.",
                "- Incorpore concretamente a psicologia, o desejo, o estado corporal próprio e o estágio relacional vigentes; não produza resposta tímida, neutra ou apenas protocolar.",
                "- Expresse iniciativa, tensão, prazer, humor, vulnerabilidade ou lascívia compatíveis com o beat, sem inventar reação ou consentimento do usuário.",
            )
        )
    elif context.canonical_line and not context.exact_speech:
        lines.extend(
            (
                "- Fala autoral adaptável: preserve de forma reconhecível o sentido, o vocabulário "
                "central e o tom da referência semântica; não precisa reproduzi-la literalmente.",
                "- Antes ou junto da fala autoral, reaja brevemente ao conteúdo mais recente do "
                "usuário quando houver algo pertinente a responder.",
                "- Complete na mesma resposta todas as finalidades ainda pendentes do movimento "
                "obrigatório, inclusive perguntas ou pedidos que não estejam escritos na referência.",
                "- A adaptação não pode abrir assunto independente, antecipar outro beat nem "
                "presumir resposta, decisão ou ação do usuário.",
            )
        )
    if context.authored_thought and context.interpreted_thought:
        lines.append(
            "- Pensamento interpretado obrigatório — preserve reconhecivelmente este núcleo psicológico e desenvolva-o em primeira pessoa, sem antecipar beats nem atribuir estados ao usuário: "
            + context.authored_thought
        )
    elif context.authored_thought:
        lines.append(
            "- Pensamento autoral obrigatório — reproduza literalmente dentro de [PENSAMENTO]: "
            + context.authored_thought
        )
    if context.authored_transition:
        lines.append(
            "- Salto temporal autoral obrigatório — escreva literalmente uma única vez, "
            "na primeira linha da resposta, antes de pensamento e fala: "
            + context.authored_transition
        )
    if context.exact_speech:
        lines.append(
            "- Fala autoral exata obrigatória — reproduza literalmente na parte audível: "
            + context.exact_speech
        )
        lines.append(
            "- A fala exata é fechada: não escreva nenhuma palavra audível antes ou depois dela."
        )
    lines.extend(
        (
            "- O contexto relacional descreve o estágio vigente; não presume consentimento nem decisão do usuário.",
            "- Somente fatos declarados podem ativar progressões de intimidade ou abertura.",
            "- Não presuma aceite, recusa ou qualquer decisão que o usuário não tenha declarado explicitamente.",
            "- Não avance para outro beat, local ou acontecimento sem autorização da decisão de transição.",
            "- Não antecipe acontecimentos, locais ou decisões de beats posteriores.",
            "- A referência semântica orienta o sentido; somente campos declarados como autorais obrigatórios exigem reprodução literal.",
        )
    )
    return "\n".join(lines)


__all__ = ["BeatContext", "build_beat_context", "render_beat_context"]
