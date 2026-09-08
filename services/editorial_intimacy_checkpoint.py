from __future__ import annotations

import json
from dataclasses import replace
from typing import Mapping

from services.editorial_runtime_types import EditorialScript, EditorialState
from services.editorial_semantic_reconciliation import (
    ReconciledStep,
    SemanticReconciliation,
)


BREAK_SIGNAL = "intimacy_correspondence_broken"


def intimate_exact_active(script: EditorialScript, state: EditorialState) -> bool:
    beat = script.beats.get(str(state.node_id or "").strip()) or {}
    return bool(beat.get("intimate_exact_speech", False))


def build_intimacy_checkpoint_prompt() -> str:
    return (
        "Você avalia somente se a mensagem mais recente do usuário mantém correspondência "
        "com uma interação íntima adulta já iniciada e consentida. Não escreva a resposta da personagem.\n"
        "Use corresponds=true para participação íntima compatível, ação declarada pelo usuário, "
        "onomatopeia coerente, pedido para continuar ou intensificar e pergunta operacional que mantenha a ação.\n"
        "Use corresponds=false para hesitação, recuo, recusa, pedido para parar ou esperar, mudança de assunto, "
        "resposta neutra, nonsense ou ausência de participação íntima.\n"
        "Retirada de consentimento nunca é infração: apenas encerra a progressão íntima.\n"
        "Use somente a mensagem atual; não presuma ações nem intenções.\n"
        "Responda exclusivamente em JSON válido: "
        '{"corresponds":true|false,"evidence":"trecho literal","reason":"..."}'
    )


def build_intimacy_checkpoint_request(user_text: str) -> str:
    return "MENSAGEM MAIS RECENTE DO USUÁRIO:\n" + str(user_text or "").strip()


def parse_intimacy_correspondence(raw: str, user_text: str) -> bool | None:
    try:
        value = json.loads(str(raw or "").strip())
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(value, Mapping) or not isinstance(value.get("corresponds"), bool):
        return None
    evidence = str(value.get("evidence", "") or "").strip()
    if evidence and evidence.casefold() not in str(user_text or "").casefold():
        return None
    return bool(value["corresponds"])


def confirm_active_intimate_step(
    result: SemanticReconciliation,
    *,
    step_id: str,
    user_text: str,
) -> SemanticReconciliation:
    steps = tuple(
        replace(
            item,
            status="satisfied",
            evidence=str(user_text or "").strip(),
            remaining_intent="",
            reason="correspondência íntima confirmada pelo checkpoint estrutural",
        )
        if item.step_id == step_id
        else item
        for item in result.steps
    )
    if not any(item.step_id == step_id for item in steps):
        steps = (
            ReconciledStep(
                step_id=step_id,
                status="satisfied",
                evidence=str(user_text or "").strip(),
                reason="correspondência íntima confirmada pelo checkpoint estrutural",
            ),
            *steps,
        )
    return SemanticReconciliation(
        steps=steps,
        route=result.route,
        evidence=result.evidence,
        reason=result.reason,
    )


__all__ = [
    "BREAK_SIGNAL",
    "build_intimacy_checkpoint_prompt",
    "build_intimacy_checkpoint_request",
    "confirm_active_intimate_step",
    "intimate_exact_active",
    "parse_intimacy_correspondence",
]
