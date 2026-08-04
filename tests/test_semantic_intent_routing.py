from __future__ import annotations

from pathlib import Path

from packages.loader import load_manifest
from services import editorial_declared_transitions
from services.editorial_package_loader import compile_editorial_package
from services.editorial_runtime import EditorialState, decide_editorial_turn
from services.editorial_semantic_intent import (
    IntentResolution,
    build_semantic_intent_prompt,
    parse_semantic_intent,
)


CARD_ROOT = Path("installed_stories/casada_frustrada")


def _script():
    return compile_editorial_package(load_manifest(CARD_ROOT / "manifest.yaml"))


def test_parser_aceita_decisao_semantica_com_evidencia() -> None:
    result = parse_semantic_intent(
        '{"intent":"accept","confidence":0.98,'
        '"evidence":"tá bom... tô esperando aqui","explicit_decision":true}',
        allowed_intents=("accept", "refuse", "postpone", "question", "unclear"),
    )

    assert result.intent == "accept"
    assert result.explicit_decision is True
    assert result.source == "semantic_model"


def test_parser_nao_inventa_aceite_sem_evidencia() -> None:
    result = parse_semantic_intent(
        '{"intent":"accept","confidence":0.99,"evidence":"",'
        '"explicit_decision":false}',
        allowed_intents=("accept", "refuse", "postpone", "question", "unclear"),
    )

    assert result.intent == "unclear"
    assert result.source == "semantic_insufficient_evidence"


def test_prompt_exige_sentido_contextual_e_nao_palavra_magica() -> None:
    beat = _script().beats["reencontro_fila_007"]
    prompt = build_semantic_intent_prompt(
        beat,
        intents=("accept", "refuse", "postpone", "question", "unclear"),
    )

    assert "Avalie o sentido no contexto" in prompt
    assert "linguagem brasileira natural, popular" in prompt
    assert "Adiamento não é recusa" in prompt
    assert "Pergunta não é aceite" in prompt


def test_fala_popular_avanca_quando_modelo_identifica_aceite(monkeypatch) -> None:
    script = _script()
    previous = EditorialState(node_id="reencontro_fila_007")

    monkeypatch.setattr(
        editorial_declared_transitions,
        "resolve_semantic_intent",
        lambda beat, classifiers, text: IntentResolution(
            intent="accept",
            confidence=0.98,
            evidence="tá bom... tô esperando aqui",
            explicit_decision=True,
            source="semantic_model",
        ),
    )

    turn = decide_editorial_turn(script, previous, "tá bom...tô esperando aqui...")

    assert turn.target_id == "reencontro_fila_008"
    assert turn.state.facts["help_to_car"] == "accepted"
    assert turn.state.facts["_last_user_intent"] == "accept"
    assert turn.state.facts["_last_user_intent_source"] == "semantic_model"
    assert turn.state.facts["_last_user_intent_evidence"] == "tá bom... tô esperando aqui"
    assert turn.state.facts["_last_user_explicit_decision"] == "true"


def test_baixa_confianca_mantem_decisao_pendente(monkeypatch) -> None:
    script = _script()
    previous = EditorialState(node_id="reencontro_fila_007")

    monkeypatch.setattr(
        editorial_declared_transitions,
        "resolve_semantic_intent",
        lambda beat, classifiers, text: IntentResolution.unclear(
            source="semantic_insufficient_evidence"
        ),
    )

    turn = decide_editorial_turn(script, previous, "sei lá... talvez")

    assert turn.target_id == "reencontro_fila_007"
    assert turn.state.facts["_last_user_intent"] == "unclear"
    assert turn.state.facts["_last_user_explicit_decision"] == "false"
