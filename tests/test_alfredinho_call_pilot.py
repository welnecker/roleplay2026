from __future__ import annotations

from services.editorial_partner_call import (
    ALFREDINHO_CALL_VERSION,
    apply_alfredinho_call_overrides,
    decide_alfredinho_call_turn,
    prepare_alfredinho_call_script,
)
from services.editorial_runtime_impl import PilotScript, PilotState


def _script() -> PilotScript:
    return PilotScript(
        {
            "engagement_policy": {"categories": {}},
            "scene": {
                "first_beat_id": "reencontro_fila_016",
                "beats": [
                    {
                        "beat_id": "reencontro_fila_016",
                        "objective": "Ligar para o marido.",
                        "units": [{"kind": "dialogue", "anchor": "Alô, Alfredinho?"}],
                        "on_user": {"engaged": "retorno_casa_001"},
                    },
                    {
                        "beat_id": "retorno_casa_001",
                        "objective": "Explicar o atraso.",
                        "units": [
                            {
                                "kind": "dialogue",
                                "anchor": "Alfredinho, meu bem... acredita que a fila emperrou?",
                            }
                        ],
                        "on_user": {
                            "engaged": "retorno_casa_002",
                            "minimal": "retorno_casa_002",
                        },
                    },
                    {
                        "beat_id": "retorno_casa_002",
                        "objective": "Chegar em casa.",
                        "units": [
                            {
                                "kind": "dialogue",
                                "anchor": "Cheguei, amor... quer uma cerveja?",
                            }
                        ],
                        "on_user": {"engaged": "retorno_casa_003"},
                    },
                    {
                        "beat_id": "retorno_casa_003",
                        "objective": "Pensar no contato.",
                        "units": [{"kind": "dialogue", "anchor": "Preciso mandar um oi."}],
                        "on_user": {"engaged": "retorno_casa_003"},
                    },
                ],
                "endings": [],
            },
        }
    )


def test_documento_publicado_separa_ligacao_da_chegada() -> None:
    document = {
        "script_version": "1.0.2-contact-exchange",
        "blocks": [
            {
                "beats": [
                    {"beat_id": "retorno_casa_001"},
                    {"beat_id": "retorno_casa_002"},
                ]
            }
        ],
    }

    updated = apply_alfredinho_call_overrides(document)
    beats = updated["blocks"][0]["beats"]

    assert updated["script_version"] == ALFREDINHO_CALL_VERSION
    assert "carro" in beats[0]["required_movement"].casefold()
    assert "cheguei" not in beats[0]["canonical_line"].casefold()
    assert beats[1]["canonical_line"] == "Cheguei, amor. Quer uma cerveja?"


def test_pergunta_de_alfredinho_mantem_ligacao_aberta() -> None:
    turn = decide_alfredinho_call_turn(
        _script(),
        PilotState(node_id="retorno_casa_001"),
        "Tá bom... comprou minhas cervejas?",
    )

    assert turn.target_id == "retorno_casa_001"
    assert turn.state.facts["alfredinho_call_active"] == "true"
    assert turn.state.facts["alfredinho_call_closed"] == "false"
    assert turn.state.facts["_scene_location"] == "carro_em_deslocamento"
    assert "não diga 'cheguei'" in turn.system_prompt.casefold()


def test_encerramento_da_ligacao_nao_antecipa_chegada() -> None:
    turn = decide_alfredinho_call_turn(
        _script(),
        PilotState(node_id="retorno_casa_001"),
        "Tá bom, vem com cuidado. Beijo.",
    )

    assert turn.target_id == "retorno_casa_001"
    assert turn.state.facts["alfredinho_call_closed"] == "true"
    assert turn.state.facts["_scene_location"] == "carro_em_deslocamento"
    assert "cheguei" not in turn.visible_fallback.casefold()
    assert "cerveja" not in turn.visible_fallback.casefold()


def test_turno_seguinte_apos_desligar_libera_chegada() -> None:
    state = PilotState(node_id="retorno_casa_001")
    state.facts["alfredinho_call_closed"] = "true"
    state.facts["alfredinho_call_active"] = "true"

    turn = decide_alfredinho_call_turn(
        _script(),
        state,
        "Já cheguei também.",
    )

    assert turn.target_id == "retorno_casa_002"
    assert turn.state.facts["alfredinho_call_active"] == "false"
    assert turn.state.facts["_scene_location"] == "casa_de_mary"
    assert "cheguei" in turn.visible_fallback.casefold()


def test_script_carregado_remove_chegada_do_beat_da_ligacao() -> None:
    script = prepare_alfredinho_call_script(_script())
    call_anchor = script.beats["retorno_casa_001"]["units"][0]["anchor"]
    arrival_anchor = script.beats["retorno_casa_002"]["units"][0]["anchor"]

    assert "cheguei" not in call_anchor.casefold()
    assert "cheguei" in arrival_anchor.casefold()
