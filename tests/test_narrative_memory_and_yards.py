from __future__ import annotations

from services.editorial_compiler import compile_editorial_document
from services.editorial_content import load_source_document
from services.narrative_context import build_narrative_context, memory_catalog
from services.pilot_supermarket import PilotScript, PilotState
from services.supermarket_script_v2 import (
    decide_supermarket_script_v2_turn,
    prepare_supermarket_script_v2,
)


def _script() -> PilotScript:
    document = load_source_document()
    return prepare_supermarket_script_v2(PilotScript(compile_editorial_document(document)))


def test_ficha_e_memorias_entram_no_contexto_do_modelo() -> None:
    document = load_source_document()
    catalog = memory_catalog(document)

    assert "met_at_supermarket" in catalog
    context = build_narrative_context(
        document,
        ["met_at_supermarket", "discovered_neighbors"],
        {"user_name": "Janio"},
    )

    assert "IDENTIDADE ESTÁVEL DE MARY" in context
    assert "25 anos" in context
    assert "PERSONALIDADE ESTÁVEL" in context
    assert "ESTILO DE FALA" in context
    assert "Mary e Janio se conheceram" in context
    assert "condomínio Plaza" in context


def test_beat_concluido_declara_memoria_pendente_e_prompt_recebe_passado() -> None:
    script = _script()
    state = PilotState(
        node_id="mensagens_iniciais_002",
        facts={
            "user_name": "Janio",
            "_active_memory_ids": "met_at_supermarket,first_private_messages",
        },
    )

    turn = decide_supermarket_script_v2_turn(script, state, "Pode falar, Mary.")

    assert turn.target_id == "mensagens_iniciais_003"
    assert "Mary e Janio se conheceram" in turn.system_prompt
    assert "Mary iniciou uma conversa privada" in turn.system_prompt
    assert turn.state.facts["_pending_memory_writes"] == "mary_confessed_attraction"
    assert "mary_confessed_attraction" in turn.state.facts["_active_memory_ids"]


def test_recusa_no_caixa_entra_no_patio_sem_encerrar_abruptamente() -> None:
    script = _script()
    state = PilotState(node_id="reencontro_fila_007")

    turn = decide_supermarket_script_v2_turn(
        script,
        state,
        "Desculpa, não posso esperar. Tenho um compromisso.",
    )

    assert turn.target_id == "yard_help_refused_001"
    assert turn.finished is False
    assert turn.state.finished is False
    assert turn.state.run_status == "active"
    assert turn.state.facts["help_to_car"] == "refused"
    assert turn.state.facts["_pending_memory_writes"] == "help_refused_at_checkout"


def test_fim_natural_entra_no_patio_de_proximo_capitulo() -> None:
    script = _script()
    state = PilotState(node_id="video_025")

    turn = decide_supermarket_script_v2_turn(script, state, "Boa noite, Mary.")

    assert turn.target_id == "yard_chapter_complete_001"
    assert turn.finished is False
    assert "não quero que isso seja a última vez" in turn.visible_fallback


def test_patio_tem_dois_movimentos_antes_do_ending() -> None:
    document = load_source_document()
    yards = {
        str(block.get("block_id")): block
        for block in document["blocks"]
        if str(block.get("block_type", "")) == "terminal_yard"
    }

    assert set(yards) == {"yard_help_refused", "yard_chapter_complete"}
    for yard in yards.values():
        dialogue_beats = [
            beat
            for beat in yard["beats"]
            if str(beat.get("type", "dialogue")) == "dialogue"
        ]
        assert len(dialogue_beats) >= 2
        assert int(yard["min_user_turns"]) >= 2
