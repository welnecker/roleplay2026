import json
from pathlib import Path

from services.editorial_compiler import compile_editorial_document
from services.editorial_semantic_reconciliation import (
    parse_reconciliation,
    reconciled_step,
)
from services.editorial_transaction import prepare_pending_editorial_turn
from services.editorial_turn_engine import decide_editorial_turn
from services.editorial_runtime_impl import PilotScript, PilotState
from services.spreadsheet_story_compiler import compile_spreadsheet_story


def _row(line_id: str, order: int, instruction: str) -> dict:
    return {
        "package_id": "roleplay2026.teste",
        "script_version": "1",
        "line_id": line_id,
        "order": order,
        "instruction": instruction,
        "status": "active",
    }


def _script() -> PilotScript:
    base = {
        "package_id": "roleplay2026.teste",
        "character": {"name": "Lia", "age": 25},
        "story_goal": ["Obter a colaboração indispensável e concluir a história no local previsto."],
        "blocks": [],
    }
    document = compile_spreadsheet_story(
        base,
        [
            _row("cena", 10, "[CENA encontro] Eu encontro o usuário."),
            _row("beat_001", 20, "[BEAT] Eu inicio a conversa."),
            _row("fala_001", 30, "[FALA] Que bom encontrar você."),
            _row(
                "ponte_pedido",
                40,
                "[PONTE] Eu peço a colaboração indispensável, caso ela ainda não tenha sido oferecida.",
            ),
            _row(
                "ponte_reacao",
                50,
                "[PONTE] Eu reajo ao que o usuário declarou sem repetir o pedido.",
            ),
            _row(
                "beat_002",
                60,
                "[BEAT] Eu informo meu destino e peço a colaboração indispensável.",
            ),
            _row(
                "fala_002",
                70,
                "[FALA] Estou indo ao destino previsto, você pode colaborar?",
            ),
            _row("beat_003", 80, "[BEAT] Eu agradeço depois que o usuário aceita."),
            _row("fala_003", 90, "[FALA] Você me ajudou muito."),
            _row("fim", 100, "[FIM story_complete] Eu encerro a história."),
        ],
        script_version="1",
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


def test_ponte_satisfeita_e_pulada_e_a_reacao_assume_o_turno() -> None:
    script = _script()
    result = {
        "route": "continue",
        "evidence": "",
        "reason": "oferta já feita",
        "steps": [
            {
                "step_id": "ponte_pedido",
                "status": "satisfied",
                "evidence": "Eu colaboro com você",
                "remaining_intent": "",
                "suppress": ["pedir a colaboração novamente"],
                "reason": "o usuário já ofereceu",
            },
            {
                "step_id": "ponte_reacao",
                "status": "pending",
                "evidence": "",
                "remaining_intent": "",
                "suppress": [],
                "reason": "a reação ainda deve acontecer",
            },
            {
                "step_id": "beat_002",
                "status": "partial",
                "evidence": "Eu colaboro com você",
                "remaining_intent": "informar o destino previsto",
                "suppress": ["pedir a colaboração"],
                "reason": "o pedido já foi resolvido",
            },
        ],
    }

    turn = decide_editorial_turn(
        script,
        PilotState(node_id="beat_001"),
        "Eu colaboro com você.",
        classifier_call=_classifier(result),
    )

    assert turn.target_id == "beat_001"
    assert turn.state.facts["_bridge_step_id"] == "ponte_reacao"
    assert turn.state.facts["_bridge_step_index"] == "1"
    assert "ponte_pedido" not in turn.system_prompt


def test_beat_parcial_preserva_apenas_finalidade_pendente() -> None:
    script = _script()
    result = {
        "route": "continue",
        "evidence": "",
        "reason": "pedido antecipado",
        "steps": [
            {
                "step_id": "ponte_pedido",
                "status": "satisfied",
                "evidence": "Eu colaboro com você",
                "remaining_intent": "",
                "suppress": ["pedir colaboração"],
                "reason": "já satisfeito",
            },
            {
                "step_id": "ponte_reacao",
                "status": "satisfied",
                "evidence": "Eu colaboro com você",
                "remaining_intent": "",
                "suppress": [],
                "reason": "a oferta pode ser reconhecida no beat",
            },
            {
                "step_id": "beat_002",
                "status": "partial",
                "evidence": "Eu colaboro com você",
                "remaining_intent": "informar o destino previsto e aceitar a colaboração",
                "suppress": ["pedir a colaboração indispensável"],
                "reason": "a colaboração já foi oferecida",
            },
        ],
    }
    previous = PilotState(node_id="beat_001")
    turn = decide_editorial_turn(
        script,
        previous,
        "Eu colaboro com você.",
        classifier_call=_classifier(result),
    )
    pending = prepare_pending_editorial_turn(script, previous, turn)

    assert turn.target_id == "beat_002"
    assert pending.context.objective == "informar o destino previsto e aceitar a colaboração"
    assert pending.context.exact_speech == ""
    assert any("pedir a colaboração indispensável" in item for item in pending.context.forbidden_outcomes)
    assert "Reconciliação semântica parcial" in pending.context.response_boundary


def test_recusa_critica_entra_no_patio_antes_de_qualquer_ponte() -> None:
    script = _script()
    refusal = "Não vou colaborar com você."
    result = {
        "route": "terminal_yard",
        "evidence": refusal,
        "reason": "a recusa bloqueia a meta indispensável sem alternativa autoral",
        "steps": [
            {
                "step_id": "ponte_pedido",
                "status": "contradicted",
                "evidence": refusal,
                "remaining_intent": "",
                "suppress": ["insistir no pedido"],
                "reason": "recusa explícita",
            }
        ],
    }

    turn = decide_editorial_turn(
        script,
        PilotState(node_id="beat_001"),
        refusal,
        classifier_call=_classifier(result),
    )

    assert turn.target_id == "__generic_disagreement_warning"
    assert turn.state.facts["_runtime_phase"] == "terminal_yard"
    assert "Inicie o pátio de encerramento" in turn.system_prompt
    assert "PONTE NARRATIVA" not in turn.system_prompt


def test_recusa_a_ponte_ativa_tambem_entra_no_patio() -> None:
    script = _script()
    first = decide_editorial_turn(
        script,
        PilotState(node_id="beat_001"),
        "Ainda não ofereci nada.",
        classifier_call=_classifier(
            {
                "route": "continue",
                "evidence": "",
                "reason": "pedido pendente",
                "steps": [],
            }
        ),
    )
    assert first.state.facts["_bridge_step_id"] == "ponte_pedido"

    refusal = "Não vou colaborar com você."
    second = decide_editorial_turn(
        script,
        first.state,
        refusal,
        classifier_call=_classifier(
            {
                "route": "terminal_yard",
                "evidence": refusal,
                "reason": "a resposta à ponte bloqueia a meta indispensável",
                "steps": [
                    {
                        "step_id": "ponte_pedido",
                        "status": "contradicted",
                        "evidence": refusal,
                        "remaining_intent": "",
                        "suppress": ["insistir"],
                        "reason": "recusa explícita à ponte ativa",
                    }
                ],
            }
        ),
    )

    assert second.target_id == "__generic_disagreement_warning"
    assert second.state.facts["_runtime_phase"] == "terminal_yard"


def test_evidencia_inventada_nao_pula_etapa_nem_aciona_patio() -> None:
    result = parse_reconciliation(
        json.dumps(
            {
                "route": "terminal_yard",
                "evidence": "recusa que nunca foi dita",
                "reason": "inválida",
                "steps": [
                    {
                        "step_id": "ponte",
                        "status": "satisfied",
                        "evidence": "oferta que nunca foi dita",
                        "remaining_intent": "",
                        "suppress": [],
                        "reason": "inválida",
                    }
                ],
            }
        ),
        allowed_step_ids=["ponte"],
        user_text="Ainda não decidi.",
    )

    assert result.route == "continue"
    assert result.steps[0].status == "pending"
    assert result.steps[0].evidence == ""


def test_fala_anterior_da_personagem_nao_serve_como_evidencia_do_usuario() -> None:
    result = parse_reconciliation(
        json.dumps(
            {
                "route": "continue",
                "evidence": "",
                "reason": "",
                "steps": [
                    {
                        "step_id": "ponte",
                        "status": "satisfied",
                        "evidence": "Eu ofereço a colaboração.",
                        "remaining_intent": "",
                        "suppress": ["pedir"],
                        "reason": "",
                    }
                ],
            }
        ),
        allowed_step_ids=["ponte"],
        user_text="Ainda estou pensando.",
        history=[
            {"role": "assistant", "content": "Eu ofereço a colaboração."},
            {"role": "user", "content": "Não sei ainda."},
        ],
    )

    assert result.steps[0].status == "pending"


def test_citacao_errada_nao_reabre_beat_ativo_corretamente_satisfeito() -> None:
    result = parse_reconciliation(
        json.dumps(
            {
                "route": "continue",
                "steps": [
                    {
                        "step_id": "encontro_001",
                        "status": "satisfied",
                        "evidence": "Oi, Janio! Tô indo aí...",
                        "remaining_intent": "",
                        "suppress": [],
                        "reason": "A pergunta do usuário respondeu à apresentação.",
                    }
                ],
            }
        ),
        allowed_step_ids=["encontro_001"],
        active_response_step_ids=["encontro_001"],
        user_text="Tá indo pra praia?",
        history=[
            {"role": "assistant", "content": "Oi, Janio! Tô indo aí..."},
        ],
    )

    assert result.steps[0].status == "satisfied"
    assert result.steps[0].evidence == "Tá indo pra praia?"


def test_motor_de_reconciliacao_nao_conhece_elementos_da_historia_camilly() -> None:
    source = Path("services/editorial_semantic_reconciliation.py").read_text(
        encoding="utf-8"
    ).casefold()

    assert "carona" not in source
    assert "praia" not in source
    assert "camilly" not in source
    assert "carro" not in source
