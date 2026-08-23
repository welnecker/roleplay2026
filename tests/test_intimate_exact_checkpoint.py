import json

from services.editorial_compiler import compile_editorial_document
from services.editorial_runtime_impl import PilotScript, PilotState
from services.editorial_turn_engine import decide_editorial_turn
from services.spreadsheet_story_compiler import compile_spreadsheet_story


def _row(line_id: str, order: int, instruction: str) -> dict:
    return {
        "package_id": "roleplay2026.intimidade",
        "script_version": "1",
        "line_id": line_id,
        "order": order,
        "instruction": instruction,
        "status": "active",
    }


def _script() -> PilotScript:
    document = compile_spreadsheet_story(
        {
            "package_id": "roleplay2026.intimidade",
            "character": {"name": "Camilly", "age": 24},
            "automatic_gate_policy": {"enabled": True, "max_redirects": 1},
            "blocks": [],
        },
        [
            _row("cena", 10, "[CENA carro] Estamos em intimidade consentida."),
            _row("intimo_001", 20, "[BEAT] Eu correspondo ao beijo consentido."),
            _row("fala_001", 30, "[FALA EXATA ÍNTIMA] Humm... isso, gato!"),
            _row("intimo_002", 40, "[BEAT] Eu intensifico meu próprio movimento."),
            _row("fala_002", 50, "[FALA EXATA ÍNTIMA] Não para agora..."),
            _row("fim", 60, "[FIM story_complete] Eu encerro normalmente."),
        ],
        script_version="1",
    )
    return PilotScript(compile_editorial_document(document))


def _classifier(*, corresponds: bool):
    def call(system_prompt: str, _request: str) -> str:
        if "mantém correspondência" in system_prompt:
            return json.dumps(
                {
                    "corresponds": corresponds,
                    "evidence": "",
                    "reason": "compatível" if corresponds else "clima interrompido",
                }
            )
        if "compara o que o usuário" in system_prompt:
            return json.dumps(
                {
                    "route": "continue",
                    "evidence": "",
                    "reason": "",
                    "steps": [
                        {
                            "step_id": "intimo_001",
                            "status": "pending",
                            "evidence": "",
                            "remaining_intent": "corresponder",
                            "suppress": [],
                            "reason": "",
                        },
                        {
                            "step_id": "intimo_002",
                            "status": "pending",
                            "evidence": "",
                            "remaining_intent": "intensificar",
                            "suppress": [],
                            "reason": "",
                        },
                    ],
                }
            )
        return json.dumps({"route": "continue", "signal": "", "reason": "", "confidence": 1})

    return call


def test_correspondencia_intima_libera_proximo_beat() -> None:
    turn = decide_editorial_turn(
        _script(),
        PilotState(node_id="intimo_001"),
        "Humm... continua assim!",
        classifier_call=_classifier(corresponds=True),
    )

    assert turn.target_id == "intimo_002"
    assert turn.finished is False


def test_quebra_intima_encerra_imediatamente_sem_persuasao() -> None:
    turn = decide_editorial_turn(
        _script(),
        PilotState(node_id="intimo_001"),
        "Espera, quero parar.",
        classifier_call=_classifier(corresponds=False),
    )

    assert turn.target_id == "__intimacy_break_end"
    assert turn.finished is True
    assert turn.ending_code == "intimacy_correspondence_broken"
    assert turn.visible_fallback == "Porra... você cortou meu tesão, gato. Já era!"
    assert turn.state.facts["_force_fixed_response"] == "true"
    assert "não tente persuadir" in turn.system_prompt
