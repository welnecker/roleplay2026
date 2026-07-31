from __future__ import annotations

from services.organic_interaction import detect_organic_signal
from services.pilot_supermarket import PilotScript, PilotState, decide_turn


def _script() -> PilotScript:
    return PilotScript(
        {
            "engagement_policy": {"categories": {}},
            "scene": {
                "first_beat_id": "ask_name",
                "beats": [
                    {
                        "beat_id": "ask_name",
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


def test_desafio_de_soletrar_usa_nome_memorizado() -> None:
    state = PilotState(node_id="ask_number", facts={"user_name": "Janio"})

    turn = decide_turn(
        _script(),
        state,
        "Eu dou o número se você soletrar meu nome, rsrsrs.",
    )

    assert turn.target_id == "ask_number"
    assert turn.state.pending_next_beat_id == "share_number"
    assert "J-A-N-I-O" in turn.visible_fallback
    assert "Olha... esse número vai me trazer sorte" in turn.system_prompt


def test_detector_nao_interrompe_resposta_comum() -> None:
    assert detect_organic_signal("Pode sim", {}) is None
