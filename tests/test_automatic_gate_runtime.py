import json

from services.editorial_compiler import compile_editorial_document
from services.editorial_runtime_impl import PilotScript, PilotState
from services.editorial_turn_engine import decide_editorial_turn
from services.spreadsheet_story_compiler import compile_spreadsheet_story


def _row(line_id: str, order: int, instruction: str) -> dict:
    return {
        "package_id": "roleplay2026.camilly",
        "script_version": "101",
        "line_id": line_id,
        "order": order,
        "instruction": instruction,
        "status": "active",
    }


def _script() -> PilotScript:
    base = {
        "package_id": "roleplay2026.camilly",
        "character": {"name": "Camilly", "age": 24},
        "automatic_gate_policy": {
            "enabled": True,
            "max_redirects": 1,
        },
        "blocks": [],
    }
    document = compile_spreadsheet_story(
        base,
        [
            _row("cena", 10, "[CENA encontro] Eu encontro o usuário."),
            _row("encontro_001", 20, "[BEAT] Eu reconheço {{nome}} no carro."),
            _row("encontro_001_fala", 30, "[FALA EXATA] Oi, {{nome}}! Tô indo aí..."),
            _row("encontro_002", 40, "[BEAT] Eu conto que vou à praia e peço uma carona."),
            _row("encontro_002_fala", 50, "[FALA] Tô indo pra praia... me dá uma carona?"),
            _row(
                "encontro_003",
                60,
                "[BEAT] Somente depois que {{nome}} aceita me levar, eu agradeço a carona.",
            ),
            _row("encontro_003_fala", 70, "[FALA] Poxa... você me salvou."),
            _row("fim", 80, "[FIM story_complete] Eu encerro o teste."),
        ],
        script_version="101",
    )
    return PilotScript(compile_editorial_document(document))


def _classifier(reconciliation: dict):
    def call(system_prompt: str, _request: str) -> str:
        if "compara o que o usuário realmente declarou" in system_prompt:
            return json.dumps(reconciliation, ensure_ascii=False)
        return json.dumps(
            {
                "route": "continue",
                "signal": "",
                "reason": "compatível",
                "confidence": 0.99,
            }
        )

    return call


def _step(step_id: str, status: str, evidence: str = "") -> dict:
    return {
        "step_id": step_id,
        "status": status,
        "evidence": evidence,
        "remaining_intent": "obter uma decisão real" if status != "satisfied" else "",
        "suppress": [],
        "reason": status,
    }


def test_aceite_libera_proximo_beat_sem_ponte_escrita() -> None:
    script = _script()
    turn = decide_editorial_turn(
        script,
        PilotState(node_id="encontro_002"),
        "Bora, eu levo você.",
        classifier_call=_classifier(
            {
                "route": "continue",
                "evidence": "",
                "reason": "aceite",
                "steps": [
                    _step("encontro_002", "satisfied", "eu levo você"),
                    _step("encontro_003", "pending"),
                ],
            }
        ),
    )

    assert turn.target_id == "encontro_003"
    assert turn.state.facts.get("_runtime_phase") == "canonical"
    assert "PONTE NARRATIVA" not in turn.system_prompt


def test_fala_do_usuario_nao_pula_beat_autoral_ainda_nao_executado() -> None:
    script = _script()
    turn = decide_editorial_turn(
        script,
        PilotState(pending_next_beat_id="encontro_001"),
        "Camilly, oi!",
        classifier_call=_classifier(
            {
                "route": "continue",
                "evidence": "",
                "reason": "saudação antecipada",
                "steps": [
                    _step("encontro_001", "satisfied", "Camilly, oi!"),
                ],
            }
        ),
    )

    assert turn.target_id == "encontro_001"
    assert "Oi, {{nome}}! Tô indo aí..." in turn.system_prompt
    assert turn.state.node_id == "encontro_001"


def test_fluxo_da_abertura_avanca_ao_segundo_beat_sem_ponte_falsa() -> None:
    script = _script()
    opening = decide_editorial_turn(
        script,
        PilotState(pending_next_beat_id="encontro_001"),
        "Camilly, oi!",
        classifier_call=_classifier(
            {
                "route": "continue",
                "steps": [_step("encontro_001", "satisfied", "Camilly, oi!")],
            }
        ),
    )

    assert opening.target_id == "encontro_001"
    assert opening.state.facts.get("_runtime_phase") == "canonical"

    following = decide_editorial_turn(
        script,
        opening.state,
        "Tá indo pra praia?",
        history=[
            {"role": "assistant", "content": "Oi, Janio! Tô indo aí..."},
        ],
        classifier_call=_classifier(
            {
                "route": "continue",
                "steps": [
                    _step("encontro_001", "satisfied", "Oi, Janio! Tô indo aí..."),
                    _step("encontro_002", "pending"),
                ],
            }
        ),
    )

    assert following.target_id == "encontro_002"
    assert following.state.node_id == "encontro_002"
    assert following.state.facts.get("_runtime_phase") == "canonical"
    assert following.finished is False
    assert "PONTE NARRATIVA" not in following.system_prompt


def test_abertura_nunca_cria_ponte_mesmo_se_primeiro_beat_ficar_pendente() -> None:
    script = _script()
    turn = decide_editorial_turn(
        script,
        PilotState(pending_next_beat_id="encontro_001"),
        "Camilly, oi!",
        classifier_call=_classifier(
            {
                "route": "continue",
                "evidence": "",
                "reason": "o movimento da personagem ainda precisa acontecer",
                "steps": [
                    _step("encontro_001", "pending"),
                ],
            }
        ),
    )

    assert turn.target_id == "encontro_001"
    assert turn.state.facts.get("_runtime_phase") == "canonical"
    assert turn.state.facts.get("_automatic_gate_active") is None
    assert "PONTE NARRATIVA" not in turn.system_prompt
    assert "Oi, {{nome}}! Tô indo aí..." in turn.system_prompt


def test_hesitacao_cria_uma_ponte_automatica_e_prende_o_destino() -> None:
    script = _script()
    turn = decide_editorial_turn(
        script,
        PilotState(node_id="encontro_002"),
        "Não sei, estou atrasado.",
        classifier_call=_classifier(
            {
                "route": "continue",
                "evidence": "",
                "reason": "sem decisão",
                "steps": [
                    _step("encontro_002", "partial", "Não sei"),
                    _step("encontro_003", "pending"),
                ],
            }
        ),
    )

    assert turn.target_id == "encontro_002"
    assert turn.state.pending_next_beat_id == "encontro_003"
    assert turn.state.facts["_runtime_phase"] == "bridge"
    assert turn.state.facts["_automatic_gate_active"] == "true"
    assert "uma única vez" in turn.system_prompt
    assert "sem presumir aceite" in turn.system_prompt
    assert "no máximo duas frases curtas" in turn.system_prompt
    assert "Não acrescente promessa" in turn.system_prompt


def test_aceite_depois_da_ponte_libera_o_destino() -> None:
    script = _script()
    first = decide_editorial_turn(
        script,
        PilotState(node_id="encontro_002"),
        "Talvez.",
        classifier_call=_classifier(
            {
                "route": "continue",
                "evidence": "",
                "reason": "hesitação",
                "steps": [
                    _step("encontro_002", "partial", "Talvez"),
                    _step("encontro_003", "pending"),
                ],
            }
        ),
    )
    second = decide_editorial_turn(
        script,
        first.state,
        "Tá bom, eu levo você.",
        classifier_call=_classifier(
            {
                "route": "continue",
                "evidence": "",
                "reason": "aceite após condução",
                "steps": [
                    _step("encontro_002", "satisfied", "eu levo você"),
                    _step("encontro_003", "pending"),
                ],
            }
        ),
    )

    assert second.target_id == "encontro_003"
    assert second.state.facts.get("_automatic_gate_active") is None


def test_recusa_encerra_sem_aviso_disciplinar() -> None:
    script = _script()
    turn = decide_editorial_turn(
        script,
        PilotState(node_id="encontro_002"),
        "Não vou levar você.",
        classifier_call=_classifier(
            {
                "route": "terminal_yard",
                "evidence": "Não vou levar você.",
                "reason": "recusa indispensável",
                "steps": [
                    _step("encontro_002", "contradicted", "Não vou levar você."),
                    _step("encontro_003", "pending"),
                ],
            }
        ),
    )

    assert turn.finished is True
    assert turn.engagement == "engaged"
    assert turn.ending_code == "required_outcome_refused"
    assert turn.target_id == "__required_outcome_end"
    assert "frustração narrativa, não uma infração" in turn.system_prompt
    assert "último aviso" not in turn.system_prompt


def test_segunda_indefinicao_encerra_sem_avancar() -> None:
    script = _script()
    first = decide_editorial_turn(
        script,
        PilotState(node_id="encontro_002"),
        "Não sei.",
        classifier_call=_classifier(
            {
                "route": "continue",
                "evidence": "",
                "reason": "indefinido",
                "steps": [
                    _step("encontro_002", "partial", "Não sei"),
                    _step("encontro_003", "pending"),
                ],
            }
        ),
    )
    second = decide_editorial_turn(
        script,
        first.state,
        "Vamos ver.",
        classifier_call=_classifier(
            {
                "route": "continue",
                "evidence": "",
                "reason": "continua indefinido",
                "steps": [
                    _step("encontro_002", "partial", "Vamos ver"),
                    _step("encontro_003", "pending"),
                ],
            }
        ),
    )

    assert second.finished is True
    assert second.ending_code == "required_outcome_unresolved"
    assert second.target_id == "__required_outcome_end"


def test_modo_automatico_compila_sem_ponte_autoral() -> None:
    script = _script()

    assert script.raw["automatic_gate_policy"]["enabled"] is True
    assert script.beats["encontro_002"]["authored_bridges"] == []
    assert "__required_outcome_end" in script.endings
    assert (
        script.beats["encontro_002"]["interaction_context"][
            "required_outcome_ending_target"
        ]
        == "__required_outcome_end"
    )
