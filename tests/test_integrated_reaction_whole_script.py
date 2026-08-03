from __future__ import annotations

from services.organic_interaction import detect_organic_signal
from services.editorial_runtime_impl import PilotScript, PilotState
from services.editorial_progression import decide_supermarket_script_v2_turn


def _script() -> PilotScript:
    return PilotScript(
        {
            "organic_slack": {"enabled": True},
            "engagement_policy": {"categories": {}},
            "scene": {
                "first_beat_id": "video_003",
                "beats": [
                    {
                        "beat_id": "video_003",
                        "objective": "Mary elogia o usuário durante a chamada.",
                        "units": [
                            {
                                "kind": "dialogue",
                                "anchor": "Agora podemos nos ver... mesmo por vídeo. Hummm... você é um gato...",
                            }
                        ],
                        "on_user": {"engaged": "video_004", "minimal": "video_004"},
                    },
                    {
                        "beat_id": "video_004",
                        "objective": "Mary pede um favor.",
                        "units": [
                            {
                                "kind": "dialogue",
                                "anchor": "Me faz um favorzinho? Tô pedindo com beicinho... olha...",
                            }
                        ],
                        "on_user": {"engaged": "video_005", "minimal": "video_005"},
                    },
                    {
                        "beat_id": "video_005",
                        "objective": "Mary faz o pedido.",
                        "units": [{"kind": "dialogue", "anchor": "Tira a camisa?"}],
                        "on_user": {"engaged": "video_005"},
                    },
                ],
                "endings": [],
            },
        }
    )


def test_provocacao_sexual_vira_reacao_integrada() -> None:
    signal = detect_organic_signal(
        "Para... estou perdendo o controle... imagino seu corpo cheio de tesão."
    )

    assert signal is not None
    assert signal.kind == "integrated_reaction"
    assert "linha canônica" in signal.instruction
    assert "mesma mensagem" in signal.instruction


def test_reacao_integrada_avanca_e_entrega_o_beat_na_mesma_resposta() -> None:
    turn = decide_supermarket_script_v2_turn(
        _script(),
        PilotState(node_id="video_003"),
        "Você é linda... esse corpo está me deixando louco de desejo.",
    )

    assert turn.target_id == "video_004"
    assert turn.state.pending_next_beat_id == ""
    assert turn.state.interstitial_turns == 0
    assert turn.state.facts["_organic_interstitial"] == "false"
    assert "REAÇÃO ORGÂNICA NECESSÁRIA" in turn.system_prompt
    assert "Me faz um favorzinho" in turn.system_prompt
    assert "mesma mensagem" in turn.system_prompt


def test_preocupacao_real_continua_com_folga_exclusiva() -> None:
    turn = decide_supermarket_script_v2_turn(
        _script(),
        PilotState(node_id="video_003"),
        "Eu quero, mas é perigoso... não quero morrer, né?",
    )

    assert turn.target_id == "video_003"
    assert turn.state.pending_next_beat_id == "video_004"
    assert turn.state.interstitial_turns == 1
    assert turn.state.facts["_organic_interstitial"] == "true"
    assert "TURNO ORGÂNICO INTERMEDIÁRIO" in turn.system_prompt


def test_comentario_louca_continua_com_folga_exclusiva() -> None:
    signal = detect_organic_signal("Tchau, Mary... você é louca mesmo.")

    assert signal is not None
    assert signal.kind == "free_reaction"
