from __future__ import annotations

from dataclasses import replace
import re

from services.editorial_beat_context import BeatContext
from services.editorial_runtime_types import EditorialState
from services.editorial_semantic_reconciliation import reconciled_step


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
        bridge_instruction = _fact(state, "_bridge_step_instruction")
        bridge_id = _fact(state, "_bridge_step_id")
        allow_question = _fact(state, "_bridge_allow_question") == "true"
        required = [
            "responder genuinamente ao conteúdo mais recente do usuário",
            "cumprir a finalidade da etapa autoral de ponte sem executar o beat de destino",
            "se a finalidade já tiver sido satisfeita pelo usuário, reconhecer e adaptar sem repeti-la",
            "preservar integralmente para o beat de destino seus demais acontecimentos reservados",
        ]
        if bridge_instruction:
            required.append(f"finalidade da ponte {bridge_id or 'atual'}: {bridge_instruction}")
        forbidden = [
            "executar o próximo beat total ou parcialmente",
            f"repetir ou parafrasear o movimento de origem já concluído: {origin_objective}",
            f"repetir ou parafrasear a linha de origem já consumida: {origin_canonical}",
            f"executar total ou parcialmente o objetivo reservado ao destino: {target_objective}",
            f"repetir ou parafrasear a linha canônica futura: {target_canonical}",
            "reconfirmar informação que já foi confirmada no turno imediatamente anterior",
            "presumir ação, aceite, recusa, desejo ou decisão do usuário",
            "avançar local, tempo ou acontecimento futuro",
        ]
        if not allow_question:
            forbidden.append("criar nova pergunta, promessa, dúvida ou obstáculo sem pendência real trazida pelo usuário")
        return replace(
            context,
            authored_thought="",
            exact_speech="",
            free_speech=False,
            authored_transition="",
            max_sentences=min(2, context.max_sentences or 2),
            max_questions=1 if allow_question else 0,
            forbid_new_questions=not allow_question,
            forbidden_literal_texts=tuple(
                dict.fromkeys(
                    (*_authored_parts(origin_canonical), *_authored_parts(target_canonical))
                )
            ),
            transition_status="bridge_pending",
            required_outcomes=tuple(required),
            forbidden_outcomes=tuple(forbidden),
            response_boundary=(
                "Ponte narrativa semanticamente vazada é inválida: permaneça entre o movimento "
                "já consumido da origem e o movimento ainda reservado ao destino "
                f"{target or 'declarado pelo runtime'}. Responda em no máximo duas frases curtas: "
                "uma reação direta e, somente se necessário, a retomada da única pendência atual. "
                "Não crie promessa, explicação ornamental, nova provocação ou gancho adicional."
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

    if phase == "finished":
        # Um ending é um contrato próprio. Ele não pode herdar pensamento, fala
        # exata, pergunta ou limites rígidos do último beat canônico; caso
        # contrário, a despedida fica impossível de aprovar justamente quando o
        # runtime já decidiu encerrar.
        return replace(
            context,
            objective="encerrar imediatamente a interação de forma coerente com a decisão do usuário",
            canonical_line="",
            dramatic_direction="",
            transition_status="finished",
            required_outcomes=(
                "respeitar a decisão real do usuário",
                "encerrar a interação sem convite para continuar",
            ),
            forbidden_outcomes=(
                "retomar o beat anterior",
                "insistir na finalidade recusada ou não resolvida",
                "abrir nova pergunta, negociação ou acontecimento",
            ),
            max_sentences=0,
            max_questions=0,
            response_boundary="Encerramento definitivo: produza somente a despedida final.",
            strict_response_economy=False,
            max_extra_words=0,
            authored_thought="",
            exact_speech="",
            free_speech=False,
            authored_transition="",
            forbid_new_questions=True,
            forbidden_literal_texts=(),
        )

    assessment = reconciled_step(state, context.target_beat_id)
    if assessment.status == "partial":
        suppress = tuple(
            f"repetir finalidade já satisfeita pelo usuário: {item}"
            for item in assessment.suppress
        )
        return replace(
            context,
            objective=assessment.remaining_intent or context.objective,
            exact_speech="" if assessment.suppress else context.exact_speech,
            required_outcomes=tuple(
                dict.fromkeys(
                    (
                        *context.required_outcomes,
                        f"reagir à evidência literal do usuário: {assessment.evidence}",
                        f"executar somente a finalidade ainda pendente: {assessment.remaining_intent}",
                    )
                )
            ),
            forbidden_outcomes=tuple(
                dict.fromkeys((*context.forbidden_outcomes, *suppress))
            ),
            response_boundary=(
                "Reconciliação semântica parcial: adapte a fala autoral à conversa, "
                "preserve apenas a finalidade pendente e não repita o que o usuário já resolveu."
            ),
        )
    if assessment.status == "contradicted":
        return replace(
            context,
            required_outcomes=tuple(
                dict.fromkeys(
                    (
                        *context.required_outcomes,
                        f"reagir sem insistir à declaração do usuário: {assessment.evidence}",
                    )
                )
            ),
            response_boundary=(
                "Contradição recuperável: não insista na finalidade recusada e não invente rota alternativa."
            ),
        )
    return context


__all__ = ["adapt_context_for_runtime_phase", "runtime_phase"]
