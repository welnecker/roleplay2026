from __future__ import annotations

from services.pilot_supermarket import PilotState
from services.supermarket_script_v2 import (
    CAR_BRIDGE,
    FIRST_PRIVATE_MESSAGE,
    HOME_BRIDGE,
    SUPERMARKET_SCRIPT_V2_VERSION,
    apply_supermarket_script_v2_overrides,
    automatic_followups_after,
    state_after_automatic_followup,
)


def _document() -> dict:
    return {
        "script_version": "old",
        "blocks": [
            {"block_id": "encontro_acidental", "beats": []},
            {"block_id": "reencontro_fila", "beats": []},
            {"block_id": "retorno_casa", "beats": []},
            {"block_id": "mensagens_iniciais", "beats": []},
        ],
    }


def test_publica_nova_sequencia_do_supermercado() -> None:
    result = apply_supermarket_script_v2_overrides(_document())
    blocks = {item["block_id"]: item for item in result["blocks"]}
    encounter = blocks["encontro_acidental"]["beats"]
    queue = blocks["reencontro_fila"]["beats"]

    assert result["script_version"] == SUPERMARKET_SCRIPT_V2_VERSION
    assert len(encounter) == 6
    assert encounter[-1]["beat_id"] == "encontro_acidental_006"
    assert encounter[-1]["canonical_line"].startswith("Vou continuar minhas comprinhas")
    assert len(queue) == 16
    assert queue[5]["beat_id"] == "reencontro_fila_006"
    assert queue[6]["beat_id"] == "reencontro_fila_007"
    assert queue[-1]["beat_id"] == "reencontro_fila_016"


def test_despedida_dispara_tres_pontes_sem_turno_do_usuario() -> None:
    followups = automatic_followups_after("reencontro_fila_016")

    assert [item["target_id"] for item in followups] == [
        "retorno_casa_001",
        "retorno_casa_002",
        "mensagens_iniciais_001",
    ]
    assert followups[0]["text"] == CAR_BRIDGE
    assert followups[1]["text"] == HOME_BRIDGE
    assert followups[2]["text"] == FIRST_PRIVATE_MESSAGE
    assert "Alô... Alfredinho?" in followups[0]["text"]
    assert "Oi?" in followups[2]["text"]


def test_primeira_despedida_e_caixa_tambem_usam_ponte() -> None:
    first_reencounter = automatic_followups_after("encontro_acidental_006")
    checkout = automatic_followups_after("reencontro_fila_006")

    assert first_reencounter[0]["target_id"] == "reencontro_fila_001"
    assert checkout[0]["target_id"] == "reencontro_fila_007"
    assert "me esperar" in checkout[0]["text"]


def test_estado_final_libera_usuario_somente_em_janio() -> None:
    state = PilotState(node_id="reencontro_fila_016")
    for followup in automatic_followups_after("reencontro_fila_016"):
        state = state_after_automatic_followup(state, followup)

    assert state.node_id == "mensagens_iniciais_001"
    assert state.facts["_scene_location"] == "mensagem_privada_janio"
    assert state.facts["active_interlocutor"] == "janio"
    assert state.facts["alfredinho_has_voice"] == "false"
    assert state.facts["_automatic_bridge"] == "completed"
