from services.editorial_compiler import compile_editorial_document
from services.editorial_phase_contract import adapt_context_for_runtime_phase
from services.editorial_beat_context import build_beat_context
from services.editorial_progression import (
    decide_editorial_progression_turn,
    prepare_editorial_script,
)
from services.editorial_runtime_impl import PilotScript, PilotState
from services.spreadsheet_story_compiler import compile_spreadsheet_story


def _row(line_id: str, order: int, instruction: str) -> dict:
    return {
        "package_id": "roleplay2026.camilly",
        "script_version": "100",
        "line_id": line_id,
        "order": order,
        "instruction": instruction,
        "status": "active",
    }


def _script() -> PilotScript:
    base = {
        "package_id": "roleplay2026.camilly",
        "character": {"name": "Camilly", "age": 24},
        "blocks": [],
    }
    document = compile_spreadsheet_story(
        base,
        [
            _row("cena", 10, "[CENA encontro] Eu encontro o usuário no carro."),
            _row("encontro_001", 20, "[BEAT] Eu conto que estou indo à praia."),
            _row("encontro_001_fala", 30, "[FALA] Tô indo pra praia."),
            _row(
                "encontro_001_pedido",
                40,
                "[PONTE] Eu peço uma carona, caso ela ainda não tenha sido oferecida.",
            ),
            _row(
                "encontro_001_reacao",
                50,
                "[PONTE] Eu reajo à resposta sem presumir que a carona foi aceita.",
            ),
            _row("encontro_002", 60, "[BEAT] Eu continuo a conversa."),
            _row("encontro_002_fala", 70, "[FALA] Que bom continuar falando com você."),
            _row("fim", 80, "[FIM story_complete] Eu encerro a história."),
        ],
        script_version="100",
    )
    return prepare_editorial_script(PilotScript(compile_editorial_document(document)))


def test_duas_pontes_sao_turnos_sequenciais_com_cursor_proprio() -> None:
    script = _script()
    first = decide_editorial_progression_turn(
        script,
        PilotState(node_id="encontro_001"),
        "Você quer uma carona?",
    )

    assert first.target_id == "encontro_001"
    assert first.state.pending_next_beat_id == "encontro_002"
    assert first.state.facts["_bridge_step_id"] == "encontro_001_pedido"
    assert first.state.facts["_bridge_step_index"] == "0"
    assert first.state.facts["_bridge_allow_question"] == "true"
    assert "já tiver satisfeito a finalidade" in first.system_prompt

    second = decide_editorial_progression_turn(script, first.state, "Claro, pode entrar.")

    assert second.target_id == "encontro_001"
    assert second.state.pending_next_beat_id == "encontro_002"
    assert second.state.facts["_bridge_step_id"] == "encontro_001_reacao"
    assert second.state.facts["_bridge_step_index"] == "1"
    assert second.state.facts["_bridge_allow_question"] == "false"

    third = decide_editorial_progression_turn(script, second.state, "Tudo certo.")

    assert third.target_id == "encontro_002"
    assert third.state.node_id == "encontro_002"
    assert third.state.facts["_runtime_phase"] == "canonical"
    assert "_bridge_step_id" not in third.state.facts


def test_ponte_de_pedido_pode_criar_uma_pergunta_sem_ser_rejeitada() -> None:
    script = _script()
    turn = decide_editorial_progression_turn(
        script,
        PilotState(node_id="encontro_001"),
        "Vai para onde?",
    )
    context = adapt_context_for_runtime_phase(
        build_beat_context(script, PilotState(node_id="encontro_001"), turn),
        turn.state,
    )

    assert context.max_questions == 1
    assert context.forbid_new_questions is False
    assert any("finalidade da ponte encontro_001_pedido" in item for item in context.required_outcomes)


def test_ponte_automatica_preserva_pergunta_da_pendencia_real() -> None:
    base = {
        "package_id": "roleplay2026.generica",
        "character": {"name": "Ana", "age": 24},
        "automatic_gate_policy": {"enabled": True, "max_redirects": 1},
        "blocks": [],
    }
    document = compile_spreadsheet_story(
        base,
        [
            _row("cena_auto", 10, "[CENA carro] Eu converso dentro do carro."),
            _row("pedido_001", 20, "[BEAT] Eu peço que o usuário pare o carro e aguardo sua decisão."),
            _row("pedido_001_fala", 30, "[FALA] Para um pouco ali para eu te mostrar melhor."),
            _row("pedido_002", 40, "[BEAT] Depois que ele aceita, eu continuo."),
            _row("pedido_002_fala", 50, "[FALA] Agora posso mostrar."),
            _row("fim_auto", 60, "[FIM story_complete] Eu encerro."),
        ],
        script_version="100",
    )
    script = prepare_editorial_script(PilotScript(compile_editorial_document(document)))
    turn = decide_editorial_progression_turn(
        script,
        PilotState(node_id="pedido_001"),
        "Agora? Aqui mesmo?",
    )
    context = adapt_context_for_runtime_phase(
        build_beat_context(script, PilotState(node_id="pedido_001"), turn),
        turn.state,
    )

    assert turn.state.facts["_bridge_allow_question"] == "true"
    assert context.forbid_new_questions is False
    assert context.max_questions == 1
    assert any("mesma pendência real" in item for item in context.required_outcomes)
