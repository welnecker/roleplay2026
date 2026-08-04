from __future__ import annotations

from dataclasses import replace

from services.editorial_beat_context import BeatContext
from services.editorial_runtime_types import EditorialState


def runtime_phase(state: EditorialState) -> str:
    phase = str(state.facts.get("_runtime_phase", "canonical") or "canonical").strip()
    return phase if phase in {"canonical", "bridge", "terminal_yard", "finished"} else "canonical"


def adapt_context_for_runtime_phase(
    context: BeatContext,
    state: EditorialState,
) -> BeatContext:
    """Transforma o BeatContext no contrato funcional da fase vigente."""

    phase = runtime_phase(state)
    if phase == "bridge":
        target = str(state.facts.get("_bridge_target_beat_id", "") or "").strip()
        return replace(
            context,
            transition_status="bridge_pending",
            required_outcomes=(
                "responder genuinamente ao conteúdo mais recente do usuário",
                "manter a voz e a reação emocional da personagem",
                "criar um gancho causal ou temático para o próximo movimento",
                "deixar espaço real para uma nova resposta do usuário",
            ),
            forbidden_outcomes=(
                "executar o próximo beat",
                "repetir ou parafrasear a linha canônica futura",
                "presumir ação, aceite, recusa, desejo ou decisão do usuário",
                "avançar local, tempo ou acontecimento futuro",
            ),
            response_boundary=(
                "Ponte narrativa: permaneça no beat de origem e apenas prepare "
                f"o alvo pendente {target or 'declarado pelo runtime'}."
            ),
        )

    if phase == "terminal_yard":
        yard_id = str(state.facts.get("_active_yard_id", "") or "").strip()
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
