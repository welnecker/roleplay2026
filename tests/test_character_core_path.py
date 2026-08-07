from __future__ import annotations

from services.editorial_compiler import compile_editorial_document
from services.editorial_content import load_source_document
from services.editorial_progression import decide_editorial_progression_turn, prepare_editorial_script
from services.editorial_runtime_impl import PilotScript, PilotState
from services.narrative_context import build_narrative_context


def _script() -> PilotScript:
    document = load_source_document()
    return prepare_editorial_script(PilotScript(compile_editorial_document(document)))


def test_character_core_substitui_ficha_fragmentada_no_prompt() -> None:
    document = load_source_document()

    assert document["character_core"]["summary"]
    context = build_narrative_context(document, [], {})

    assert "NÚCLEO VIVO E AUTORITATIVO DE MARY" in context
    assert "corpo escultural e curvilíneo" in context
    assert "não pretende divórcio" in context
    assert "não se apaixona pelo usuário" in context
    assert "REGRAS DO PENSAMENTO INTERNO" in context
    assert "COMO ESTE NÚCLEO ORIENTA OS BEATS" in context
    assert "COMO ESTE NÚCLEO ORIENTA AS PONTES" in context
    assert "IDENTIDADE ESTÁVEL DE MARY" not in context
    assert "PERSONALIDADE ESTÁVEL" not in context


def test_beat_canonico_recebe_o_mesmo_character_core() -> None:
    script = _script()
    state = PilotState(node_id="encontro_acidental_001")

    turn = decide_editorial_progression_turn(script, state, "Tudo bem.")

    assert "NÚCLEO VIVO E AUTORITATIVO DE MARY" in turn.system_prompt
    assert "o beat define o que acontece" in turn.system_prompt.casefold()
    assert "não se apaixona pelo usuário" in turn.system_prompt


def test_ponte_recebe_o_mesmo_character_core_sem_criar_outra_personagem() -> None:
    script = _script()
    state = PilotState(node_id="encontro_acidental_001")

    turn = decide_editorial_progression_turn(
        script,
        state,
        "Relaxa, não aconteceu nada. Você também está bem depois desse encontrão?",
    )

    assert turn.state.facts.get("_runtime_phase") == "bridge"
    assert "FASE ESTRUTURAL: PONTE NARRATIVA" in turn.system_prompt
    assert "NÚCLEO VIVO E AUTORITATIVO DE MARY" in turn.system_prompt
    assert "improvisar a reação ao usuário a partir deste mesmo núcleo psicológico" in turn.system_prompt
    assert "Beats e pontes são caminhos diferentes do mesmo personagem" in turn.system_prompt


def test_character_core_remove_carencia_romantizada_do_caminho_autoritativo() -> None:
    document = load_source_document()
    context = build_narrative_context(document, [], {})

    assert "carência afetiva e sexual" not in context
    assert "não procura salvação emocional" in context
    assert "sem culpa automática" in context
    assert "farra secreta" in context
