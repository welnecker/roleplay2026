from __future__ import annotations

from services.dialogue_presentation import with_optional_thought_guidance
from services.editorial_conversational_obligation import (
    consume_pending_obligation,
    detect_conversational_obligation,
    store_pending_obligation,
)


def test_detecta_pergunta_ou_convite_sem_reter_conversa_comum() -> None:
    assert detect_conversational_obligation("Você costuma ir à piscina aos sábados?")
    assert detect_conversational_obligation("Que tal um café qualquer dia")
    assert detect_conversational_obligation("Moro no bloco B") == ""


def test_pendencia_conversacional_dura_apenas_ate_o_proximo_beat() -> None:
    facts: dict[str, str] = {}

    stored = store_pending_obligation(facts, "Topa tomar um café?")

    assert stored == "Topa tomar um café?"
    assert consume_pending_obligation(facts) == "Topa tomar um café?"
    assert consume_pending_obligation(facts) == ""


def test_orientacao_de_pensamento_traz_anseio_sem_inflar_prompt() -> None:
    prompt = with_optional_thought_guidance("BASE")

    assert "humor sobre a própria situação conjugal" in prompt
    assert "pista emocional" in prompt
    assert "não antecipe o roteiro" in prompt
    assert "no máximo duas frases curtas" in prompt
    assert len(prompt) < 1500
