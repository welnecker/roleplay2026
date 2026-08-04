from __future__ import annotations

from services.editorial_compiler import compile_editorial_document
from services.editorial_content import load_source_document
from services.editorial_runtime_impl import PilotScript, PilotState
from services.editorial_progression import (
    decide_editorial_progression_turn,
    editorial_followups_after,
    prepare_editorial_script,
    state_after_editorial_followup,
)


FAREWELL_BEAT_ID = "encontro_acidental_despedida_001"


def _script() -> PilotScript:
    document = load_source_document()
    return prepare_editorial_script(PilotScript(compile_editorial_document(document)))


def test_fonte_unica_compila_sequencia_do_supermercado() -> None:
    document = load_source_document()
    script = _script()
    farewell_anchor = script.beats[FAREWELL_BEAT_ID]["units"][0]["anchor"].casefold()

    assert document["script_version"] == "1.2.0-single-source"
    assert script.first_beat_id == "encontro_acidental_001"
    assert "mora no Plaza" in script.beats["encontro_acidental_004"]["units"][0]["anchor"]
    assert "Somos vizinhos" in script.beats["encontro_acidental_005"]["units"][0]["anchor"]
    assert "eu sou a Mary" in script.beats["encontro_acidental_006"]["units"][0]["anchor"]
    assert "vou continuar minhas comprinhas" in farewell_anchor
    assert script.beats["encontro_acidental_004"]["on_user"]["engaged"] == "encontro_acidental_005"
    assert script.beats["encontro_acidental_005"]["on_user"]["engaged"] == "encontro_acidental_006"
    assert script.beats["encontro_acidental_006"]["on_user"]["engaged"] == FAREWELL_BEAT_ID


def test_telefone_ja_informado_aplica_salto_declarado_no_roteiro() -> None:
    script = _script()
    assert script.beats["reencontro_fila_013"]["skip_when_facts"] == {
        "user_phone": "reencontro_fila_014"
    }

    state = PilotState(
        node_id="reencontro_fila_012",
        facts={"user_phone": "999711721"},
    )
    turn = decide_editorial_progression_turn(
        script,
        state,
        "Sou Janio... ao seu dispor, princesa.",
    )

    assert turn.target_id == "reencontro_fila_014"
    assert turn.state.node_id == "reencontro_fila_014"
    assert turn.state.facts["user_phone"] == "999711721"
    assert turn.state.facts["_declared_skip_applied"] == "reencontro_fila_013"
    assert "Queria seu número" not in turn.visible_fallback


def test_despedida_dispara_tres_pontes_sem_turno_do_usuario() -> None:
    _script()
    followups = editorial_followups_after("reencontro_fila_016")

    assert [item["target_id"] for item in followups] == [
        "retorno_casa_001",
        "retorno_casa_002",
        "mensagens_iniciais_001",
    ]
    assert "Alfredinho" in followups[0]["text"]
    assert "Cheguei, amor" in followups[1]["text"]
    assert followups[2]["text"].rstrip().endswith("Oi?")


def test_primeira_despedida_e_caixa_usam_pontes_declaradas_no_yaml() -> None:
    _script()
    first_reencounter = editorial_followups_after(FAREWELL_BEAT_ID)
    checkout = editorial_followups_after("reencontro_fila_006")

    assert first_reencounter[0]["target_id"] == "reencontro_fila_001"
    assert "tá me seguindo" in first_reencounter[0]["text"]
    assert checkout[0]["target_id"] == "reencontro_fila_007"
    assert "me esperar" in checkout[0]["text"]


def test_estado_final_libera_usuario_somente_em_janio() -> None:
    _script()
    state = PilotState(node_id="reencontro_fila_016")
    for followup in editorial_followups_after("reencontro_fila_016"):
        state = state_after_editorial_followup(state, followup)

    assert state.node_id == "mensagens_iniciais_001"
    assert state.facts["_scene_location"] == "mensagem_privada_janio"
    assert state.facts["active_interlocutor"] == "janio"
    assert state.facts["alfredinho_has_voice"] == "false"
