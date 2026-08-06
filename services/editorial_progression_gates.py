from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Callable, Mapping

from services.editorial_runtime_types import EditorialScript, EditorialState, EditorialTurn


@dataclass(frozen=True, slots=True)
class ProgressionGateResult:
    allowed: bool
    dimension_id: str = ""
    required_value: int = 0
    actual_value: int = 0
    fallback_target: str = ""
    instruction: str = ""


def _psychological_policy(document: Mapping[str, Any]) -> dict[str, Any]:
    direct = document.get("psychological_state") or {}
    if isinstance(direct, dict) and direct:
        return dict(direct)
    relationship = document.get("relationship_memory") or {}
    if not isinstance(relationship, dict):
        return {}
    nested = relationship.get("psychological_state") or {}
    return dict(nested) if isinstance(nested, dict) else {}


def projected_dimension_value(
    document: Mapping[str, Any],
    state: EditorialState,
    engagement: str,
    dimension_id: str,
) -> int:
    """Calcula o valor após a interação atual sem alterar o estado persistido."""

    current = int(getattr(state, dimension_id, 0))
    policy = _psychological_policy(document)
    by_engagement = policy.get("engagement_deltas") or {}
    delta = 0
    if isinstance(by_engagement, dict):
        declared = by_engagement.get(str(engagement)) or {}
        if isinstance(declared, dict):
            try:
                delta = int(declared.get(dimension_id, 0) or 0)
            except (TypeError, ValueError):
                delta = 0
    return max(0, min(10, current + delta))


def evaluate_progression_gate(
    document: Mapping[str, Any],
    state: EditorialState,
    target: Mapping[str, Any],
    engagement: str,
) -> ProgressionGateResult:
    gate = target.get("progression_gate") or {}
    if not isinstance(gate, dict) or not gate:
        return ProgressionGateResult(True)

    dimension_id = str(gate.get("dimension", "trust") or "trust").strip()
    if not dimension_id or not hasattr(state, dimension_id):
        raise ValueError(f"progression_gate usa dimensão inexistente: {dimension_id!r}")
    required = int(gate.get("min", 0) or 0)
    actual = projected_dimension_value(document, state, engagement, dimension_id)
    fallback = str(gate.get("fallback_target", "") or "").strip()
    instruction = str(gate.get("blocked_instruction", "") or "").strip()
    return ProgressionGateResult(
        allowed=actual >= required,
        dimension_id=dimension_id,
        required_value=required,
        actual_value=actual,
        fallback_target=fallback,
        instruction=instruction,
    )


def apply_progression_gate(
    script: EditorialScript,
    previous_state: EditorialState,
    turn: EditorialTurn,
    user_text: str,
    *,
    base_decide: Callable[[EditorialScript, EditorialState, str], EditorialTurn],
) -> EditorialTurn:
    """Redireciona destinos bloqueados para o fallback pertencente ao card."""

    target = script.beats.get(turn.target_id) or script.endings.get(turn.target_id) or {}
    result = evaluate_progression_gate(
        script.raw,
        previous_state,
        target,
        str(turn.engagement),
    )
    if result.allowed:
        return turn
    if not result.fallback_target:
        raise ValueError(
            f"Destino {turn.target_id!r} bloqueado por confiança sem fallback_target."
        )
    if result.fallback_target == turn.target_id:
        raise ValueError(f"progression_gate cria autorreferência em {turn.target_id!r}")
    if result.fallback_target not in script.beats and result.fallback_target not in script.endings:
        raise ValueError(
            f"progression_gate aponta para alvo inexistente: {result.fallback_target!r}"
        )

    retry_state = EditorialState.from_dict(previous_state.to_dict())
    retry_state.pending_next_beat_id = result.fallback_target
    retry_state.facts["_progression_gate_blocked_target"] = str(turn.target_id)
    retry_state.facts["_progression_gate_dimension"] = result.dimension_id
    retry_state.facts["_progression_gate_required"] = str(result.required_value)
    retry_state.facts["_progression_gate_actual"] = str(result.actual_value)
    redirected = base_decide(script, retry_state, user_text)
    if result.instruction:
        redirected = replace(
            redirected,
            system_prompt=(
                f"{redirected.system_prompt.strip()}\n\n"
                "CONFIANÇA AINDA INSUFICIENTE PARA O DESTINO RESERVADO:\n"
                f"- {result.instruction}\n"
                "- Não revele números, limiares, regras internas nem o beat bloqueado.\n"
                "- A contenção deve parecer uma escolha emocional natural da personagem."
            ),
        )
    redirected_state = EditorialState.from_dict(redirected.state.to_dict())
    redirected_state.facts.update(retry_state.facts)
    return replace(redirected, state=redirected_state)


__all__ = [
    "ProgressionGateResult",
    "apply_progression_gate",
    "evaluate_progression_gate",
    "projected_dimension_value",
]
