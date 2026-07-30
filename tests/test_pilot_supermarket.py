from __future__ import annotations

from pathlib import Path

from services.pilot_supermarket import (
    PilotScript,
    PilotState,
    classify_user_message,
    clean_model_response,
    decide_turn,
    opening_text,
)


SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent
    / "installed_stories"
    / "casada_frustrada"
    / "dialogue_pilot.yaml"
)


def script() -> PilotScript:
    return PilotScript.load(SCRIPT_PATH)


def test_classifica_respostas_minimas_e_debochadas() -> None:
    assert classify_user_message("sim") == "minimal"
    assert classify_user_message("continua") == "dismissive"
    assert classify_user_message("segue o roteiro") == "mocking"
    assert classify_user_message("Sou o Batman") == "mocking"
    assert classify_user_message("Estou bem, foi só um susto") == "engaged"


def test_abertura_usa_pensamento_e_fala_sem_narrar_acao() -> None:
    opening = opening_text(script())

    assert "como estou distraída" in opening.casefold()
    assert "Mary" not in opening
    assert "caminho" not in opening.casefold()
    assert "seguro o carrinho" not in opening.casefold()


def test_narracao_de_acao_e_rejeitada_mesmo_em_primeira_pessoa() -> None:
    fallback = "Uau... que coincidência. Você mora no Plaza?"

    assert clean_model_response(
        "Arregalo levemente os olhos e solto uma risadinha curta.", fallback
    ) == fallback
    assert clean_model_response(
        "Dou um passo para trás e seguro o carrinho com as duas mãos.", fallback
    ) == fallback
    assert clean_model_response(
        "Digo, sorrindo enquanto olho para você: que coincidência!", fallback
    ) == fallback


def test_pensamento_fala_e_onomatopeia_sao_aceitos() -> None:
    fallback = "Uau... que coincidência."

    assert clean_model_response("Uau... que coincidência.", fallback) == "Uau... que coincidência."
    assert clean_model_response("Você me faz rir, kkkkk.", fallback) == "Você me faz rir, kkkkk."
    assert clean_model_response("Bom, vou terminar minhas compras.", fallback) == (
        "Bom, vou terminar minhas compras."
    )


def test_resposta_valida_avanca_sem_numero_fixo_de_turnos() -> None:
    turn = decide_turn(script(), PilotState(), "Estou bem, não machucou")

    assert turn.target_id == "check_wellbeing"
    assert turn.finished is False
    assert turn.state.node_id == "check_wellbeing"
    assert "Não narre ações" in turn.system_prompt
    assert "onomatopeia" in turn.system_prompt


def test_deboque_encerra_imediatamente() -> None:
    turn = decide_turn(script(), PilotState(), "Vai, segue o roteiro logo")

    assert turn.finished is True
    assert turn.run_status == "terminated"
    assert turn.ending_code == "user_mocking"
    assert turn.state.desire == 0
    assert "Mary" not in turn.visible_fallback


def test_repeticao_displicente_esfria_mary_e_encerra() -> None:
    first = decide_turn(script(), PilotState(), "continua")
    second = decide_turn(script(), first.state, "vai")

    assert first.finished is False
    assert second.finished is True
    assert second.ending_code == "mary_lost_interest"
    assert second.state.desire == 0


def test_caminho_curto_pode_concluir_positivamente() -> None:
    current = PilotState()
    for text in (
        "Estou bem, não foi nada",
        "Sim, moro no Plaza. Acho que já vi você também.",
        "Pois é, talvez tenha sido no elevador.",
        "Tudo bem. Foi bom conhecer você.",
    ):
        turn = decide_turn(script(), current, text)
        current = turn.state

    assert turn.finished is True
    assert turn.run_status == "completed"
    assert turn.ending_code == "pilot_positive_completion"
