from __future__ import annotations

from dataclasses import replace
import re

from services.editorial_beat_context import BeatContext
from services.editorial_runtime_types import EditorialState


def runtime_phase(state: EditorialState) -> str:
    phase = str(state.facts.get("_runtime_phase", "canonical") or "canonical").strip()
    return phase if phase in {"canonical", "bridge", "terminal_yard", "finished"} else "canonical"


def _fact(state: EditorialState, key: str) -> str:
    return str(state.facts.get(key, "") or "").strip()


def _authored_parts(value: str) -> tuple[str, ...]:
    """Separa pensamento e fala para impedir déjà-vu literal na ponte."""

    text = str(value or "").strip()
    if not text:
        return ()
    thoughts = [
        match.strip()
        for match in re.findall(
            r"\[PENSAMENTO\](.*?)\[/PENSAMENTO\]",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if match.strip()
    ]
    audible = re.sub(
        r"\[PENSAMENTO\].*?\[/PENSAMENTO\]",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    audible = re.sub(r"^\s*\[[^\]]+\]\s*", "", audible).strip()
    return tuple(dict.fromkeys((*thoughts, *((audible,) if audible else ()))))


def adapt_context_for_runtime_phase(
    context: BeatContext,
    state: EditorialState,
) -> BeatContext:
    """Transforma o BeatContext no contrato funcional da fase vigente."""

    phase = runtime_phase(state)
    if phase == "bridge":
        target = _fact(state, "_bridge_target_beat_id")
        origin_objective = _fact(state, "_bridge_origin_objective")
        origin_canonical = _fact(state, "_bridge_origin_canonical")
        target_objective = _fact(state, "_bridge_target_objective")
        target_canonical = _fact(state, "_bridge_target_canonical")
        return replace(
            context,
            authored_thought="",
            exact_speech="",
            max_questions=0,
            forbid_new_questions=True,
            forbidden_literal_texts=tuple(
                dict.fromkeys(
                    (*_authored_parts(origin_canonical), *_authored_parts(target_canonical))
                )
            ),
            transition_status="bridge_pending",
            required_outcomes=(
                "responder genuinamente ao conteúdo mais recente do usuário",
                "acrescentar uma reação nova que não replique o beat de origem",
                "preservar integralmente para o beat de destino suas decisões, perguntas, combinações e revelações",
                "não criar pendência artificial apenas para prolongar a conversa",
            ),
            forbidden_outcomes=(
                "executar o próximo beat total ou parcialmente",
                f"repetir ou parafrasear o movimento de origem já concluído: {origin_objective}",
                f"repetir ou parafrasear a linha de origem já consumida: {origin_canonical}",
                f"executar total ou parcialmente o objetivo reservado ao destino: {target_objective}",
                f"repetir ou parafrasear a linha canônica futura: {target_canonical}",
                "reconfirmar informação que já foi confirmada no turno imediatamente anterior",
                "criar nova pergunta, promessa, dúvida ou obstáculo sem pendência real trazida pelo usuário",
                "presumir ação, aceite, recusa, desejo ou decisão do usuário",
                "avançar local, tempo ou acontecimento futuro",
            ),
            response_boundary=(
                "Ponte narrativa semanticamente vazada é inválida: permaneça entre o movimento "
                "já consumido da origem e o movimento ainda reservado ao destino "
                f"{target or 'declarado pelo runtime'}."
            ),
        )

    if phase == "terminal_yard":
        yard_id = _fact(state, "_active_yard_id")
        return replace(
            context,
            transition_status="terminal_yard_active",
            required_outcomes=(
                "reconhecer brevemente o tom atual do usuário",
                "cumprir o movimento de despedida do pátio",
                "manter o encerramento em curso",
            ),
            forbidden_outcomes=(
                "retornar ao roteiro principal",
                "abrir nova negociação de continuidade",
                "converter a ruptura em intimidade ou recompensa",
                "sair para destino diferente do pátio ou ending permitido",
            ),
            response_boundary=f"Pátio terminal ativo: {yard_id or 'declarado pelo runtime'}.",
        )

    return context


__all__ = ["adapt_context_for_runtime_phase", "runtime_phase"]
