from __future__ import annotations

from services.editorial_compiler import compile_editorial_document
from services.editorial_content import load_source_document
from services.editorial_runtime_impl import PilotScript, PilotState
from services.editorial_progression import (
    decide_editorial_progression_turn,
    prepare_editorial_script,
)


def _script() -> PilotScript:
    document = load_source_document()
    return prepare_editorial_script(PilotScript(compile_editorial_document(document)))


def test_opa_apos_primeira_mensagem_executa_beat_integrado_sem_ponte() -> None:
    script = _script()
    state = PilotState(
        node_id="mensagens_iniciais_001",
        interest=5,
        desire=3,
        patience=4,
        facts={"active_interlocutor": "janio"},
    )

    turn = decide_editorial_progression_turn(script, state, "Opa...")

    assert turn.finished is False
    assert turn.target_id == "mensagens_iniciais_002"
    assert turn.state.node_id == "mensagens_iniciais_002"
    assert turn.state.pending_next_beat_id == ""
    assert turn.state.facts.get("_runtime_phase") != "bridge"
    assert "PONTE NARRATIVA" not in turn.system_prompt
    assert "não consegui esperar" in turn.visible_fallback.casefold()


def test_bloco_inicial_de_mensagens_nao_cria_pontes_semanticas() -> None:
    script = _script()

    for number in range(2, 11):
        beat_id = f"mensagens_iniciais_{number:03d}"
        assert script.beats[beat_id]["response_boundary"] == "integrated_canonical"


def test_confirmacao_da_quimica_executa_carencia_uma_unica_vez() -> None:
    script = _script()
    state = PilotState(
        node_id="mensagens_iniciais_007",
        interest=5,
        desire=3,
        patience=4,
        facts={
            "active_interlocutor": "janio",
            "user_name": "Janio",
            "mary_confessed_attraction": "true",
        },
    )

    turn = decide_editorial_progression_turn(
        script,
        state,
        "Rolou, e isso me assusta. Como você vai administrar isso?",
    )

    assert turn.finished is False
    assert turn.target_id == "mensagens_iniciais_008"
    assert turn.state.node_id == "mensagens_iniciais_008"
    assert turn.state.pending_next_beat_id == ""
    assert turn.state.facts.get("_runtime_phase") != "bridge"
    assert "PONTE NARRATIVA" not in turn.system_prompt
    assert "carente" in turn.visible_fallback.casefold()
    assert turn.visible_fallback.casefold().count("carente") == 1


def test_apresentacao_devolve_turno_antes_da_despedida() -> None:
    script = _script()
    presentation = script.beats["encontro_acidental_006"]
    farewell = script.beats["encontro_acidental_despedida_001"]
    presentation_anchor = presentation["units"][0]["anchor"].casefold()
    farewell_anchor = farewell["units"][0]["anchor"].casefold()

    assert presentation["on_user"]["engaged"] == "encontro_acidental_despedida_001"
    assert presentation.get("automatic_followups", []) == []
    assert "tchau" not in presentation_anchor
    assert "mary" in presentation_anchor
    assert "tchau" in farewell_anchor
    assert farewell["on_user"]["engaged"] == "reencontro_fila_001"
    assert farewell["automatic_followups"][0]["target_id"] == "reencontro_fila_001"


def test_bloco_da_chamada_de_video_nao_cria_pontes_semanticas() -> None:
    script = _script()

    for number in range(1, 26):
        beat_id = f"video_{number:03d}"
        assert script.beats[beat_id]["response_boundary"] == "integrated_canonical"


def test_confirmacao_do_enquadramento_executa_elogio_uma_unica_vez() -> None:
    script = _script()
    state = PilotState(
        node_id="video_002",
        interest=5,
        desire=3,
        patience=4,
        facts={
            "active_interlocutor": "janio",
            "user_name": "Janio",
            "first_video_call": "true",
        },
    )

    turn = decide_editorial_progression_turn(
        script,
        state,
        "Tô vendo você inteira... linda!",
    )

    assert turn.finished is False
    assert turn.target_id == "video_003"
    assert turn.state.node_id == "video_003"
    assert turn.state.pending_next_beat_id == ""
    assert turn.state.facts.get("_runtime_phase") != "bridge"
    assert "PONTE NARRATIVA" not in turn.system_prompt
    assert "gato" in turn.visible_fallback.casefold()
    assert turn.visible_fallback.casefold().count("gato") == 1


def test_camisa_retirada_executa_reacao_de_desejo_sem_ponte() -> None:
    script = _script()
    state = PilotState(
        node_id="video_005",
        interest=5,
        desire=3,
        patience=4,
        facts={
            "active_interlocutor": "janio",
            "user_name": "Janio",
            "first_video_call": "true",
        },
    )

    turn = decide_editorial_progression_turn(
        script,
        state,
        "Pronto... satisfeita?",
    )

    assert turn.finished is False
    assert turn.target_id == "video_006"
    assert turn.state.node_id == "video_006"
    assert turn.state.pending_next_beat_id == ""
    assert turn.state.facts.get("_runtime_phase") != "bridge"
    assert "PONTE NARRATIVA" not in turn.system_prompt
    assert "delícia" in turn.visible_fallback.casefold()
    assert turn.visible_fallback.casefold().count("delícia") == 1


def test_calca_retirada_executa_reacao_ao_volume_sem_ponte() -> None:
    script = _script()
    state = PilotState(
        node_id="video_011",
        interest=5,
        desire=3,
        patience=4,
        facts={
            "active_interlocutor": "janio",
            "user_name": "Janio",
            "first_video_call": "true",
        },
    )

    turn = decide_editorial_progression_turn(
        script,
        state,
        "Pronto... satisfeita?",
    )

    assert turn.finished is False
    assert turn.target_id == "video_012"
    assert turn.state.node_id == "video_012"
    assert turn.state.pending_next_beat_id == ""
    assert turn.state.facts.get("_runtime_phase") != "bridge"
    assert "PONTE NARRATIVA" not in turn.system_prompt
    assert "volume" in turn.visible_fallback.casefold()
    assert turn.visible_fallback.casefold().count("volume") == 1


def test_continuacao_executavel_segue_ate_a_historia_completa() -> None:
    script = _script()

    assert script.beats["mensagens_iniciais_001"]["on_user"]["engaged"] == "mensagens_iniciais_002"
    assert script.beats["mensagens_iniciais_001"]["on_user"]["minimal"] == "mensagens_iniciais_002"
    assert "video_025" in script.beats
    assert script.beats["video_025"]["on_user"]["engaged"] == "late_night_bridge_001"
    assert script.beats["late_night_008"]["on_user"]["engaged"] == "morning_bridge_001"
    assert script.beats["motel_039"]["on_user"]["engaged"] == "yard_motel_farewell_001"
    assert script.beats["yard_motel_farewell_004"]["on_user"]["engaged"] == "end_full_story"
