from __future__ import annotations

import pytest

from services.editorial_compiler import compile_editorial_document
from services.editorial_decision_gate import (
    activate_decision_for_beat,
    evaluate_pending_decision,
    parse_acceptance,
    pending_decision_gate,
)
from services.editorial_runtime import EditorialScript, EditorialState
from services.editorial_scene_images import message_allows_beat_image
from services.spreadsheet_story_compiler import (
    SpreadsheetStoryError,
    compile_spreadsheet_story,
)


def _row(line_id: str, order: int, instruction: str) -> dict[str, object]:
    return {
        "line_id": line_id,
        "order": order,
        "instruction": instruction,
        "status": "active",
    }


def _document(*, complete: bool = True) -> dict[str, object]:
    rows = [
        _row("cena", 10, "[CENA teste] Eu começo a cena."),
        _row("beat_a", 20, "[BEAT] Eu peço uma decisão."),
        _row("fala_a", 30, "[FALA] Você aceita?"),
        _row("gate", 40, "[PÁTIO DECISÃO escolha]"),
        _row("accept", 50, "[ACEITE] {{nome}} concorda claramente em continuar."),
        _row("proceed", 60, "[PROSSEGUIR] Claro, pode continuar."),
        _row("luck", 70, "[TENTAR A SORTE] Escreva por sua conta e risco."),
        _row("warning", 80, "[AVISO] E então... vai continuar ou não?"),
    ]
    if complete:
        rows.append(_row("end_gate", 90, "[ENCERRAMENTO escolha_negada] Tudo bem. Tchau."))
    rows.extend(
        [
            _row("beat_b", 100, "[BEAT] Eu avanço para outro assunto."),
            _row("fala_b", 110, "[FALA] Seguimos."),
            _row("fim", 120, "[FIM story_complete]"),
        ]
    )
    return compile_spreadsheet_story(
        {"character": {"name": "Lia"}}, rows, script_version="2"
    )


def _script() -> EditorialScript:
    return EditorialScript(compile_editorial_document(_document()))


def test_compila_patio_no_beat_anterior_sem_criar_beat_visivel() -> None:
    script = _script()
    gate = script.beats["beat_a"]["decision_gate"]
    assert gate == {
        "decision_id": "escolha",
        "acceptance": "{{nome}} concorda claramente em continuar.",
        "suggested_response": "Claro, pode continuar.",
        "try_your_luck": "Escreva por sua conta e risco.",
        "warning": "E então... vai continuar ou não?",
        "ending_code": "escolha_negada",
        "ending_text": "Tudo bem. Tchau.",
        "max_attempts": 2,
    }
    assert "gate" not in script.beats


def test_rejeita_patio_incompleto() -> None:
    with pytest.raises(SpreadsheetStoryError, match="incompleto"):
        _document(complete=False)


def test_aliases_antigos_sao_normalizados() -> None:
    document = compile_spreadsheet_story(
        {"character": {"name": "Lia"}},
        [
            _row("cena", 10, "[CENA teste] Eu começo."),
            _row("beat", 20, "[BEAT] Eu ajo."),
            _row("thought", 30, "[PENSAMENTO INTERPRETATIVO] Meu desejo cresce."),
            _row("speech", 40, "[INTERPRETAR] Vem comigo."),
            _row("fim", 50, "[FIM story_complete]"),
        ],
        script_version="2",
    )
    beat = compile_editorial_document(document)["scene"]["beats"][0]
    assert beat["interpreted_thought"] is True
    assert beat["interpreted_speech"] is True


def test_primeiro_nao_aceite_avisa_e_aceite_seguinte_recupera() -> None:
    script = _script()
    state = activate_decision_for_beat(script, EditorialState(node_id="beat_a"), "beat_a")
    warned, outcome = evaluate_pending_decision(
        script, state, "Ah, não sei.", classifier=lambda *_: '{"result":"not_accepted"}'
    )
    assert outcome.result == "warning"
    assert warned.decision_attempts == 1
    assert warned.decision_status == "warned"

    recovered, outcome = evaluate_pending_decision(
        script,
        warned,
        "Não vou deixar você esperando; pode continuar.",
        classifier=lambda *_: '{"result":"accepted"}',
    )
    assert outcome.result == "accepted"
    assert recovered.decision_status == "accepted"
    assert recovered.finished is False


def test_segundo_nao_aceite_encerra_e_estado_retorna_integralmente() -> None:
    script = _script()
    state = activate_decision_for_beat(script, EditorialState(node_id="beat_a"), "beat_a")
    state, _ = evaluate_pending_decision(
        script, state, "Talvez.", classifier=lambda *_: "not_accepted"
    )
    state, outcome = evaluate_pending_decision(
        script, state, "Por quê?", classifier=lambda *_: "not_accepted"
    )
    restored = EditorialState.from_dict(state.to_dict())
    assert outcome.result == "terminated"
    assert restored.finished is True
    assert restored.run_status == "terminated"
    assert restored.ending_code == "escolha_negada"
    assert restored.decision_attempts == 2


def test_decisao_nao_vaza_para_outro_beat_e_nao_exibe_imagem() -> None:
    script = _script()
    state = activate_decision_for_beat(script, EditorialState(node_id="beat_a"), "beat_a")
    state.node_id = "beat_b"
    assert pending_decision_gate(script, state) is None
    assert message_allows_beat_image({"decision_message": True}) is False


def test_parser_binario_e_conservador() -> None:
    assert parse_acceptance('{"result":"accepted"}') == "accepted"
    assert parse_acceptance('{"result":"uncertain"}') == "not_accepted"
    assert parse_acceptance("resposta ambígua") == "not_accepted"