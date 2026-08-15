from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from services.editorial_runtime_types import EditorialScript, EditorialState


DecisionClassifier = Callable[[str, str], str]


@dataclass(frozen=True, slots=True)
class DecisionOutcome:
    result: str
    response: str = ""
    ending_code: str = ""


def decision_gate_for_beat(
    script: EditorialScript, beat_id: str
) -> dict[str, Any] | None:
    gate = (script.beats.get(str(beat_id or "")) or {}).get("decision_gate")
    if not isinstance(gate, Mapping) or not str(gate.get("decision_id", "")).strip():
        return None
    return dict(gate)


def activate_decision_for_beat(
    script: EditorialScript, state: EditorialState, beat_id: str
) -> EditorialState:
    updated = EditorialState.from_dict(state.to_dict())
    gate = decision_gate_for_beat(script, beat_id)
    if gate is None:
        return updated
    decision_id = str(gate["decision_id"])
    if updated.decision_id == decision_id and updated.decision_status in {
        "pending", "warned", "accepted", "terminated"
    }:
        return updated
    if updated.decision_id != decision_id or updated.decision_status not in {"pending", "warned"}:
        updated.decision_id = decision_id
        updated.decision_beat_id = str(beat_id)
        updated.decision_attempts = 0
        updated.decision_status = "pending"
    return updated


def pending_decision_gate(
    script: EditorialScript, state: EditorialState
) -> dict[str, Any] | None:
    if state.decision_status not in {"pending", "warned"}:
        return None
    if state.decision_beat_id != state.node_id:
        return None
    gate = decision_gate_for_beat(script, state.decision_beat_id)
    if gate is None or str(gate.get("decision_id")) != state.decision_id:
        return None
    return gate


def build_acceptance_prompt() -> str:
    return (
        "Classifique somente se a mensagem do usuário satisfaz claramente o critério "
        "contextual de aceite. Aceites indiretos e frases com negação gramatical podem "
        "ser aceitos quando o sentido confirma a ação. Pergunta, hesitação, negativa, "
        "mudança de assunto ou ambiguidade são not_accepted. Responda apenas JSON: "
        '{"result":"accepted"} ou {"result":"not_accepted"}.'
    )


def build_acceptance_request(user_text: str, criterion: str) -> str:
    return json.dumps(
        {"criterion": str(criterion), "user_message": str(user_text)},
        ensure_ascii=False,
    )


def parse_acceptance(raw: str) -> str:
    try:
        payload = json.loads(str(raw or ""))
    except json.JSONDecodeError:
        match = re.search(r"\b(accepted|not_accepted)\b", str(raw or "").casefold())
        return match.group(1) if match else "not_accepted"
    result = str(payload.get("result", "") if isinstance(payload, dict) else "")
    return result if result in {"accepted", "not_accepted"} else "not_accepted"


def evaluate_pending_decision(
    script: EditorialScript,
    state: EditorialState,
    user_text: str,
    *,
    classifier: DecisionClassifier,
    input_source: str = "typed",
) -> tuple[EditorialState, DecisionOutcome]:
    gate = pending_decision_gate(script, state)
    if gate is None:
        return EditorialState.from_dict(state.to_dict()), DecisionOutcome("not_pending")

    updated = EditorialState.from_dict(state.to_dict())
    updated.input_source = str(input_source or "typed")
    raw = classifier(
        build_acceptance_prompt(),
        build_acceptance_request(user_text, str(gate["acceptance"])),
    )
    result = parse_acceptance(raw)
    if result == "accepted":
        updated.decision_status = "accepted"
        return updated, DecisionOutcome("accepted")

    updated.decision_attempts += 1
    if updated.decision_attempts < int(gate.get("max_attempts", 2) or 2):
        updated.decision_status = "warned"
        return updated, DecisionOutcome("warning", str(gate["warning"]))

    updated.decision_status = "terminated"
    updated.finished = True
    updated.run_status = "terminated"
    updated.ending_code = str(gate["ending_code"])
    return updated, DecisionOutcome(
        "terminated", str(gate["ending_text"]), str(gate["ending_code"])
    )


__all__ = [
    "DecisionOutcome",
    "activate_decision_for_beat",
    "build_acceptance_prompt",
    "build_acceptance_request",
    "decision_gate_for_beat",
    "evaluate_pending_decision",
    "parse_acceptance",
    "pending_decision_gate",
]