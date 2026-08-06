from __future__ import annotations

from services.editorial_compiler import compile_editorial_document
from services.editorial_content import load_source_document
from services.editorial_progression import decide_editorial_progression_turn, prepare_editorial_script
from services.editorial_psychological_state import (
    apply_card_psychological_deltas,
    psychological_dimensions,
    render_psychological_state,
)
from services.editorial_runtime_impl import PilotScript, PilotState


def _script() -> PilotScript:
    document = load_source_document()
    return prepare_editorial_script(PilotScript(compile_editorial_document(document)))


def test_card_declara_faixas_psicologicas_visiveis() -> None:
    document = load_source_document()
    policy = document["relationship_memory"]["psychological_state"]

    assert set(policy["dimensions"]) == {"interest", "desire", "trust", "patience"}
    assert policy["engagement_deltas"]["engaged"] == {"interest": 1, "trust": 1}
    assert policy["engagement_deltas"]["hostile"]["trust"] == -4


def test_estado_inicial_de_mary_vira_orientacao_comportamental() -> None:
    document = load_source_document()
    state = PilotState(interest=5, desire=3, trust=2, patience=4)

    dimensions = {item.dimension_id: item for item in psychological_dimensions(document, state)}
    rendered = render_psychological_state(document, state)

    assert dimensions["interest"].band_id == "curious"
    assert dimensions["desire"].band_id == "awakening"
    assert dimensions["trust"].band_id == "guarded"
    assert dimensions["patience"].band_id == "cautious"
    assert "ESTADO PSICOLÓGICO ATUAL DE MARY" in rendered
    assert "protege sua vulnerabilidade" in rendered
    assert "O desejo começa a aparecer" in rendered
    assert "Interesse pelo usuário: 5" not in rendered


def test_interacao_evolui_interesse_e_confianca_uma_vez_por_turno() -> None:
    document = load_source_document()
    state = PilotState(node_id="beat_002", interest=5, trust=2)
    state.recent_engagement = ["engaged"]

    apply_card_psychological_deltas(document, state, "engaged")
    apply_card_psychological_deltas(document, state, "engaged")

    assert state.interest == 6
    assert state.trust == 3


def test_estado_psicologico_entra_no_prompt_e_no_estado_persistido() -> None:
    script = _script()
    state = PilotState(node_id="reencontro_fila_001", interest=5, trust=2)

    turn = decide_editorial_progression_turn(
        script,
        state,
        "Gostei de te encontrar de novo. Pode ficar tranquila comigo.",
    )

    assert turn.state.interest == 6
    assert turn.state.trust == 3
    assert "ESTADO PSICOLÓGICO ATUAL DE MARY" in turn.system_prompt
    assert "Mary demonstra curiosidade real" in turn.system_prompt
    assert "Mary testa reciprocidade e discrição" in turn.system_prompt
    assert "sem mencionar números" in turn.system_prompt


def test_contrato_funciona_para_outro_card_sem_conhecer_mary() -> None:
    document = {
        "psychological_state": {
            "title": "ESTADO DE LIA",
            "dimensions": {
                "trust": {
                    "label": "Confiança",
                    "bands": [
                        {
                            "band_id": "open",
                            "min": 4,
                            "max": 10,
                            "effect": "Lia fala com abertura e serenidade.",
                        }
                    ],
                }
            },
        }
    }
    state = PilotState(trust=7)

    rendered = render_psychological_state(document, state)

    assert rendered == "ESTADO DE LIA:\n- Confiança: Lia fala com abertura e serenidade."
    assert "Mary" not in rendered
