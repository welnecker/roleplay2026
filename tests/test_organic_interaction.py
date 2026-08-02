from __future__ import annotations

from services.organic_interaction import detect_organic_signal
from services.pilot_supermarket import PilotScript, PilotState, clean_model_response, decide_turn


def _script() -> PilotScript:
    return PilotScript(
        {
            "engagement_policy": {"categories": {}},
            "scene": {
                "first_beat_id": "ask_name",
                "beats": [
                    {
                        "beat_id": "ask_name",
                        "objective": "Descobrir o nome do usuário.",
                        "units": [
                            {
                                "kind": "dialogue",
                                "anchor": "Você não disse seu nome ainda.",
                            },
                            {"kind": "wait_user"},
                        ],
                        "on_user": {"engaged": "ask_favor", "minimal": "ask_favor"},
                    },
                    {
                        "beat_id": "ask_favor",
                        "objective": "Pedir uma ajuda curta ao usuário.",
                        "units": [
                            {
                                "kind": "dialogue",
                                "anchor": "Foi muito legal te conhecer... posso te pedir só mais uma coisa?",
                            },
                            {"kind": "wait_user"},
                        ],
                        "on_user": {"engaged": "ask_number", "minimal": "ask_number"},
                    },
                    {
                        "beat_id": "ask_number",
                        "objective": "Pedir o número do usuário.",
                        "units": [
                            {
                                "kind": "dialogue",
                                "anchor": "Queria seu número.",
                            },
                            {"kind": "wait_user"},
                        ],
                        "on_user": {"engaged": "share_number", "minimal": "share_number"},
                    },
                    {
                        "beat_id": "share_number",
                        "objective": "Compartilhar o número de Mary.",
                        "units": [
                            {
                                "kind": "dialogue",
                                "anchor": "Olha... esse número vai me trazer sorte. Anota o meu também.",
                            },
                            {"kind": "wait_user"},
                        ],
                        "on_user": {"engaged": "share_number"},
                    },
                ],
                "endings": [],
            },
        }
    )


def test_nome_e_reconhecido_antes_do_proximo_beat() -> None:
    state = PilotState(node_id="ask_name")

    turn = decide_turn(
        _script(),
        state,
        "Ah... que cabeça a minha. Me chamo Janio, prazer, mas você não disse o seu.",
    )

    assert turn.target_id == "ask_name"
    assert turn.state.node_id == "ask_name"
    assert turn.state.facts["user_name"] == "Janio"
    assert turn.state.pending_next_beat_id == "ask_favor"
    assert "Janio" in turn.visible_fallback
    assert "você se chama Mary" in turn.system_prompt


def test_turno_seguinte_retoma_o_beat_pendente() -> None:
    first = decide_turn(
        _script(),
        PilotState(node_id="ask_name"),
        "Me chamo Janio. E você?",
    )

    second = decide_turn(_script(), first.state, "Prazer, Mary.")

    assert second.target_id == "ask_favor"
    assert second.state.pending_next_beat_id == ""
    assert "Foi muito legal te conhecer" in second.visible_fallback


def test_desafio_de_soletrar_usa_nome_memorizado_sem_antecipar_fala() -> None:
    state = PilotState(node_id="ask_number", facts={"user_name": "Janio"})

    turn = decide_turn(
        _script(),
        state,
        "Eu dou o número se você soletrar meu nome, rsrsrs.",
    )

    assert turn.target_id == "ask_number"
    assert turn.state.pending_next_beat_id == "share_number"
    assert "J-A-N-I-O" in turn.visible_fallback
    assert "Compartilhar o número de Mary" in turn.system_prompt
    assert "Olha... esse número vai me trazer sorte" not in turn.system_prompt
    assert "Não execute nem recite" in turn.system_prompt


def test_pergunta_direta_avanca_e_e_respondida_no_novo_beat() -> None:
    turn = decide_turn(
        _script(),
        PilotState(node_id="ask_favor"),
        "Claro, mas onde está o seu carro?",
    )

    assert turn.target_id == "ask_number"
    assert turn.state.node_id == "ask_number"
    assert turn.state.pending_next_beat_id == ""
    assert "Responda primeiro à pergunta direta" in turn.system_prompt


def test_telefone_informado_e_persistido_sem_pedir_novamente() -> None:
    facts: dict[str, str] = {}

    first = detect_organic_signal(
        "Anota aí, gata: 999711721... mas conversa comigo direito, hein?",
        facts,
    )

    assert first is not None
    assert facts["user_phone"] == "999711721"
    assert first.facts["user_phone"] == "999711721"

    second = detect_organic_signal(
        "Pede o que quiser... você virou rainha do meu castelo, gata.",
        facts,
    )

    assert second is not None
    assert "já informou o telefone 999711721" in second.instruction
    assert "não peça o número novamente" in second.instruction


def test_nome_de_mary_em_primeira_pessoa_nao_aciona_fallback() -> None:
    response = "Eu sou a Mary, muito prazer! E você, como se chama?"

    assert clean_model_response(response, "fallback") == response


def test_narracao_de_mary_em_terceira_pessoa_continua_bloqueada() -> None:
    assert clean_model_response("Mary sorri e olha para ele.", "fallback") == "fallback"


def test_detector_nao_interrompe_resposta_comum() -> None:
    assert detect_organic_signal("Pode sim", {}) is None
