from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from services.editorial_runtime_types import EditorialScript, EditorialState


_RESULT_KEY = "_semantic_reconciliation"
_ROUTE_KEY = "_semantic_reconciliation_route"
_CRITICAL_SIGNAL = "explicit_departure_or_refusal_that_abandons_the_story"
_STATUSES = {"pending", "partial", "satisfied", "contradicted"}


@dataclass(frozen=True, slots=True)
class ReconciledStep:
    step_id: str
    status: str = "pending"
    evidence: str = ""
    remaining_intent: str = ""
    suppress: tuple[str, ...] = ()
    reason: str = ""


@dataclass(frozen=True, slots=True)
class SemanticReconciliation:
    steps: tuple[ReconciledStep, ...] = ()
    route: str = "continue"
    evidence: str = ""
    reason: str = ""


def _plain(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(char for char in text if not unicodedata.combining(char)).casefold()


def _dialogue(beat: Mapping[str, Any]) -> tuple[str, str]:
    for unit in beat.get("units", []) or []:
        if isinstance(unit, Mapping) and str(unit.get("kind", "")) == "dialogue":
            return (
                str(unit.get("anchor") or unit.get("text") or "").strip(),
                str(unit.get("instruction") or "").strip(),
            )
    return "", ""


def _normal_target(script: EditorialScript, state: EditorialState) -> str:
    current_id = state.node_id or script.first_beat_id
    beat = script.beats.get(current_id) or {}
    transitions = beat.get("on_user") or {}
    return str(transitions.get("engaged") or beat.get("terminal_transition") or "")


def _authored_bridges(beat: Mapping[str, Any], *, start: int = 0) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for index, item in enumerate(beat.get("authored_bridges", []) or []):
        if index < start or not isinstance(item, Mapping):
            continue
        instruction = str(item.get("instruction", "") or "").strip()
        if instruction:
            result.append(
                {
                    "step_id": str(item.get("bridge_id", "") or f"bridge_{index + 1}"),
                    "kind": "bridge",
                    "purpose": instruction,
                    "canonical": "",
                    "index": str(index),
                }
            )
    return result


def _beat_step(beat_id: str, beat: Mapping[str, Any], *, kind: str = "beat") -> dict[str, str]:
    canonical, direction = _dialogue(beat)
    return {
        "step_id": str(beat_id),
        "kind": kind,
        "purpose": str(beat.get("objective", "") or "").strip(),
        "canonical": canonical,
        "direction": direction,
    }


def immediate_reconciliation_steps(
    script: EditorialScript,
    state: EditorialState,
) -> list[dict[str, str]]:
    """Expõe somente pontes restantes e o próximo beat, nunca o roteiro inteiro."""

    current_id = state.node_id or script.first_beat_id
    current = script.beats.get(current_id) or {}
    steps: list[dict[str, str]] = []
    if str(state.facts.get("_runtime_phase", "") or "") == "bridge":
        index = int(state.facts.get("_bridge_step_index", "-1") or -1)
        active = _authored_bridges(current, start=index)
        active = [item for item in active if int(item.get("index", "-1") or -1) == index]
        if active:
            active[0]["kind"] = "active_bridge_response"
            steps.append(active[0])
        if not active:
            origin_id = str(state.facts.get("_bridge_origin_beat_id", "") or "").strip()
            origin = script.beats.get(origin_id) or {}
            if origin:
                steps.append(_beat_step(origin_id, origin, kind="active_automatic_gate_response"))
        steps.extend(_authored_bridges(current, start=index + 1))
        target_id = str(state.facts.get("_bridge_target_beat_id", "") or "").strip()
    else:
        # A abertura deixa o primeiro beat pendente sem tê-lo consumido.
        if not state.node_id and state.pending_next_beat_id:
            target_id = state.pending_next_beat_id
        else:
            if state.node_id and current:
                steps.append(_beat_step(current_id, current, kind="active_beat_response"))
            steps.extend(_authored_bridges(current))
            target_id = state.pending_next_beat_id or _normal_target(script, state)

    target = script.beats.get(str(target_id or "")) or {}
    if target:
        steps.append(_beat_step(str(target_id), target))
    return steps


def build_reconciliation_prompt(
    script: EditorialScript,
    state: EditorialState,
) -> str:
    steps = immediate_reconciliation_steps(script, state)
    goals = script.raw.get("story_goal") or []
    if isinstance(goals, str):
        goals = [goals]
    payload = {"story_goal": [str(item) for item in goals], "steps": steps}
    return (
        "Você compara o que o usuário realmente declarou com as finalidades narrativas imediatas.\n"
        "Não escreva a resposta da personagem. Não complete lacunas e não presuma consentimento.\n"
        "Avalie semanticamente, não por palavras isoladas. Use somente evidência literal do usuário.\n"
        "Para cada step_id, escolha exatamente um status:\n"
        "- pending: a finalidade ainda precisa ser executada;\n"
        "- partial: parte foi satisfeita, mas remaining_intent ainda precisa ser executado;\n"
        "- satisfied: toda a finalidade já foi satisfeita e deve ser pulada ou adaptada;\n"
        "- contradicted: o usuário recusou ou tornou a finalidade incompatível.\n"
        "Em suppress, liste somente pedidos, perguntas ou afirmações que se tornariam redundantes.\n"
        "Para kind active_beat_response ou active_automatic_gate_response, avalie se a resposta do usuário resolve o checkpoint aberto pelo movimento: reação pertinente resolve uma apresentação; resposta pertinente resolve uma pergunta; aceite ou iniciativa equivalente resolve uma solicitação indispensável. Dúvida, hesitação ou ausência de decisão mantém pending ou partial.\n"
        "Use route terminal_yard apenas quando a mensagem mais recente recusar explicitamente um objetivo indispensável, sem rota autoral alternativa, bloqueando a meta da história.\n"
        "Recusa opcional, dúvida, pergunta, provocação ou desvio recuperável mantém route continue.\n"
        "Responda exclusivamente em JSON válido:\n"
        '{"route":"continue|terminal_yard","evidence":"trecho literal","reason":"...",'
        '"steps":[{"step_id":"...","status":"pending|partial|satisfied|contradicted",'
        '"evidence":"trecho literal","remaining_intent":"...","suppress":["..."],"reason":"..."}]}\n\n'
        "CONTRATO IMEDIATO:\n" + json.dumps(payload, ensure_ascii=False)
    )


def build_reconciliation_request(
    user_text: str,
    history: Sequence[Mapping[str, str]] = (),
) -> str:
    recent = [
        {"role": str(item.get("role", "")), "content": str(item.get("content", ""))}
        for item in history[-8:]
        if str(item.get("content", "")).strip()
    ]
    return (
        "HISTÓRICO RECENTE:\n"
        + json.dumps(recent, ensure_ascii=False)
        + "\n\nMENSAGEM MAIS RECENTE DO USUÁRIO:\n"
        + str(user_text or "").strip()
    )


def _evidence_is_literal(evidence: str, corpus: str) -> bool:
    clean = _plain(evidence).strip()
    return bool(clean and clean in _plain(corpus))


def parse_reconciliation(
    raw: str,
    *,
    allowed_step_ids: Iterable[str],
    user_text: str,
    history: Sequence[Mapping[str, str]] = (),
) -> SemanticReconciliation:
    allowed = {str(item).strip() for item in allowed_step_ids if str(item).strip()}
    corpus = "\n".join(
        [
            *(
                str(item.get("content", ""))
                for item in history[-8:]
                if str(item.get("role", "")).strip() == "user"
            ),
            str(user_text or ""),
        ]
    )
    try:
        value = json.loads(str(raw or "").strip())
    except (TypeError, ValueError, json.JSONDecodeError):
        return SemanticReconciliation(reason="invalid_reconciliation_json")
    if not isinstance(value, Mapping):
        return SemanticReconciliation(reason="invalid_reconciliation_payload")

    steps: list[ReconciledStep] = []
    seen: set[str] = set()
    for item in value.get("steps", []) or []:
        if not isinstance(item, Mapping):
            continue
        step_id = str(item.get("step_id", "") or "").strip()
        status = str(item.get("status", "pending") or "pending").strip()
        evidence = str(item.get("evidence", "") or "").strip()
        if step_id not in allowed or step_id in seen or status not in _STATUSES:
            continue
        seen.add(step_id)
        if status != "pending" and not _evidence_is_literal(evidence, corpus):
            status = "pending"
            evidence = ""
        suppress = item.get("suppress") or []
        if not isinstance(suppress, list):
            suppress = []
        steps.append(
            ReconciledStep(
                step_id=step_id,
                status=status,
                evidence=evidence,
                remaining_intent=str(item.get("remaining_intent", "") or "").strip(),
                suppress=tuple(str(part).strip() for part in suppress if str(part).strip()),
                reason=str(item.get("reason", "") or "").strip(),
            )
        )
    for step_id in allowed - seen:
        steps.append(ReconciledStep(step_id=step_id))

    route = str(value.get("route", "continue") or "continue").strip()
    route_evidence = str(value.get("evidence", "") or "").strip()
    if route != "terminal_yard" or not _evidence_is_literal(route_evidence, user_text):
        route = "continue"
        route_evidence = ""
    return SemanticReconciliation(
        steps=tuple(steps),
        route=route,
        evidence=route_evidence,
        reason=str(value.get("reason", "") or "").strip(),
    )


def state_with_reconciliation(
    state: EditorialState,
    result: SemanticReconciliation,
) -> EditorialState:
    updated = EditorialState.from_dict(state.to_dict())
    updated.facts[_RESULT_KEY] = json.dumps(
        [
            {
                "step_id": item.step_id,
                "status": item.status,
                "evidence": item.evidence,
                "remaining_intent": item.remaining_intent,
                "suppress": list(item.suppress),
                "reason": item.reason,
            }
            for item in result.steps
        ],
        ensure_ascii=False,
    )
    updated.facts[_ROUTE_KEY] = result.route
    updated.facts["_semantic_reconciliation_evidence"] = result.evidence
    updated.facts["_semantic_reconciliation_reason"] = result.reason
    return updated


def reconciled_step(state: EditorialState, step_id: str) -> ReconciledStep:
    try:
        values = json.loads(str(state.facts.get(_RESULT_KEY, "[]") or "[]"))
    except (TypeError, ValueError, json.JSONDecodeError):
        values = []
    for item in values if isinstance(values, list) else []:
        if isinstance(item, Mapping) and str(item.get("step_id", "")) == str(step_id):
            return ReconciledStep(
                step_id=str(step_id),
                status=str(item.get("status", "pending") or "pending"),
                evidence=str(item.get("evidence", "") or ""),
                remaining_intent=str(item.get("remaining_intent", "") or ""),
                suppress=tuple(str(part) for part in item.get("suppress", []) or []),
                reason=str(item.get("reason", "") or ""),
            )
    return ReconciledStep(step_id=str(step_id))


def reconciliation_terminal_destination(state: EditorialState) -> tuple[bool, str, str]:
    terminal = str(state.facts.get(_ROUTE_KEY, "continue") or "continue") == "terminal_yard"
    return (
        terminal,
        _CRITICAL_SIGNAL if terminal else "",
        str(state.facts.get("_semantic_reconciliation_reason", "") or ""),
    )


__all__ = [
    "ReconciledStep",
    "SemanticReconciliation",
    "build_reconciliation_prompt",
    "build_reconciliation_request",
    "immediate_reconciliation_steps",
    "parse_reconciliation",
    "reconciled_step",
    "reconciliation_terminal_destination",
    "state_with_reconciliation",
]
