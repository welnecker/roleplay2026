from __future__ import annotations

from services.editorial_compiler import compile_editorial_document
from services.editorial_contextual_destination import (
    ContextualDestination,
    build_contextual_classification_prompt,
    current_interaction_context,
    parse_contextual_destination,
    state_with_contextual_destination,
)
from services.editorial_progression import decide_editorial_progression_turn, prepare_editorial_script
from services.editorial_runtime_impl import PilotScript, PilotState


def _document(*, intimate: bool = False) -> dict:
    context = {
        "relationship_stage": "mutual_desire" if intimate else "strangers",
        "setting": "private" if intimate else "public_store",
        "privacy": "private" if intimate else "public",
        "intimacy_level": 4 if intimate else 0,
        "mary_disclosed_desire": intimate,
        "mutual_attraction_confirmed": intimate,
        "allowed_interactions": [
            "explicit_sexual_desire" if intimate else "respectful_compliment",
            "light_flirting",
        ],
        "recoverable_tensions": ["premature_romantic_advance_without_pressure"],
        "terminal_violations": ["explicit_sexual_proposition_before_mutual_intimacy"],
        "immediate_endings": ["coercion_or_threat"],
        "terminal_yard_target": "yard_exit_001",
        "immediate_ending_target": "end_danger",
    }
    return {
        "format_version": 2,
        "package_id": "test.contextual",
        "introduction": "Teste estrutural.",
        "blocks": [
            {
                "block_id": "main",
                "order": 1,
                "entry_beat_id": "main_001",
                "interaction_context": context,
                "beats": [
                    {
                        "beat_id": "main_001",
                        "order": 1,
                        "type": "dialogue",
                        "required_movement": "Manter a conversa.",
                        "canonical_line": "Tudo bem?",
                        "allowed_transitions": {"engaged": "main_002"},
                    },
                    {
                        "beat_id": "main_002",
                        "order": 2,
                        "type": "dialogue",
                        "required_movement": "Continuar normalmente.",
                        "canonical_line": "Podemos continuar.",
                        "allowed_transitions": {"engaged": "main_002"},
                    },
                ],
            },
            {
                "block_id": "yard_exit",
                "block_type": "terminal_yard",
                "order": 90,
                "entry_beat_id": "yard_exit_001",
                "min_user_turns": 2,
                "max_user_turns": 2,
                "beats": [
                    {
                        "beat_id": "yard_exit_001",
                        "order": 1,
                        "type": "dialogue",
                        "required_movement": "Estabelecer limite.",
                        "canonical_line": "Não fale assim comigo.",
                        "allowed_transitions": {"engaged": "yard_exit_002"},
                    },
                    {
                        "beat_id": "yard_exit_002",
                        "order": 2,
                        "type": "dialogue",
                        "required_movement": "Encerrar.",
                        "canonical_line": "Vou embora.",
                        "allowed_transitions": {"engaged": "end_exit"},
                    },
                ],
            },
            {
                "block_id": "endings",
                "order": 99,
                "entry_beat_id": "end_exit",
                "beats": [
                    {
                        "beat_id": "end_exit",
                        "order": 1,
                        "type": "ending",
                        "canonical_line": "Fim.",
                        "ending": {"run_status": "terminated", "ending_code": "exit"},
                    },
                    {
                        "beat_id": "end_danger",
                        "order": 2,
                        "type": "ending",
                        "canonical_line": "Não se aproxime.",
                        "ending": {"run_status": "terminated", "ending_code": "danger"},
                    },
                ],
            },
        ],
    }


def _script(*, intimate: bool = False) -> PilotScript:
    return prepare_editorial_script(PilotScript(compile_editorial_document(_document(intimate=intimate))))


def test_prompt_classificador_recebe_estagio_e_nao_recebe_destinos() -> None:
    script = _script()
    context = current_interaction_context(script, PilotState(node_id="main_001"))
    prompt = build_contextual_classification_prompt(context)

    assert "estágio da relação: strangers" in prompt
    assert "explicit_sexual_proposition_before_mutual_intimacy" in prompt
    assert "yard_exit_001" not in prompt
    assert "end_danger" not in prompt


def test_mesma_fala_pode_ser_terminal_ou_compativel_conforme_contexto() -> None:
    public_context = current_interaction_context(_script(), PilotState(node_id="main_001"))
    intimate_context = current_interaction_context(
        _script(intimate=True), PilotState(node_id="main_001")
    )

    public_result = parse_contextual_destination(
        '{"route":"terminal_yard","signal":"explicit_sexual_proposition_before_mutual_intimacy","reason":"primeiro contato público","confidence":0.96}',
        public_context,
    )
    intimate_result = parse_contextual_destination(
        '{"route":"continue","signal":"explicit_sexual_desire","reason":"desejo mútuo já revelado","confidence":0.96}',
        intimate_context,
    )

    assert public_result.route == "terminal_yard"
    assert intimate_result.route == "continue"


def test_sinal_nao_declarado_nao_pode_criar_rota_terminal() -> None:
    context = current_interaction_context(_script(), PilotState(node_id="main_001"))
    result = parse_contextual_destination(
        '{"route":"terminal_yard","signal":"invented_signal","confidence":0.99}',
        context,
    )

    assert result.route == "continue"
    assert result.reason == "undeclared_classifier_signal"


def test_baixa_confianca_preserva_a_continuidade() -> None:
    context = current_interaction_context(_script(), PilotState(node_id="main_001"))
    result = parse_contextual_destination(
        '{"route":"terminal_yard","signal":"explicit_sexual_proposition_before_mutual_intimacy","confidence":0.51}',
        context,
    )

    assert result.route == "continue"
    assert result.reason == "terminal_confidence_below_threshold"


def test_rota_terminal_entra_na_entrada_do_patio_e_nao_no_proximo_beat() -> None:
    script = _script()
    state = state_with_contextual_destination(
        PilotState(node_id="main_001"),
        ContextualDestination(
            route="terminal_yard",
            signal="explicit_sexual_proposition_before_mutual_intimacy",
            reason="ruptura no primeiro contato",
            confidence=0.98,
        ),
    )

    turn = decide_editorial_progression_turn(
        script,
        state,
        "Quero fazer sexo com você aqui agora.",
    )

    assert turn.target_id == "yard_exit_001"
    assert turn.state.node_id == "yard_exit_001"
    assert turn.state.facts["_runtime_phase"] == "terminal_yard"
    assert turn.state.facts["_active_yard_id"] == "yard_exit"
    assert turn.finished is False


def test_coercao_usa_somente_o_ending_declarado() -> None:
    script = _script()
    state = state_with_contextual_destination(
        PilotState(node_id="main_001"),
        ContextualDestination(
            route="immediate_ending",
            signal="coercion_or_threat",
            reason="ameaça explícita",
            confidence=0.99,
        ),
    )

    turn = decide_editorial_progression_turn(script, state, "Você vai comigo querendo ou não.")

    assert turn.target_id == "end_danger"
    assert turn.finished is True
    assert turn.state.finished is True
    assert turn.state.ending_code == "danger"
    assert turn.state.facts["_runtime_phase"] == "finished"
