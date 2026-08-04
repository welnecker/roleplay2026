from __future__ import annotations

import pytest

from services.editorial_beat_context import build_beat_context, render_beat_context
from services.editorial_compiler import compile_editorial_document
from services.editorial_interaction_context import resolve_interaction_context
from services.editorial_runtime_impl import PilotScript, PilotState, PilotTurn


def _document() -> dict:
    return {
        "introduction": "Teste estrutural",
        "interaction_context": {
            "relationship_stage": "strangers",
            "setting": "public",
            "privacy": "public",
            "intimacy_level": 0,
            "mary_disclosed_desire": False,
            "mutual_attraction_confirmed": False,
            "allowed_interactions": ["compliment", "light_flirting"],
            "terminal_violations": ["explicit_sexual_escalation"],
            "progression": [
                {
                    "id": "desire_disclosed",
                    "when_facts": {"mary_disclosed_desire": "true"},
                    "set": {
                        "relationship_stage": "desire_disclosed",
                        "intimacy_level": 2,
                        "mary_disclosed_desire": True,
                        "allowed_interactions": ["explicit_flirting", "sexual_desire"],
                        "terminal_violations": ["coercion"],
                    },
                }
            ],
        },
        "blocks": [
            {
                "block_id": "public_meeting",
                "order": 1,
                "entry_beat_id": "public_001",
                "interaction_context": {
                    "relationship_stage": "acquaintances",
                    "allowed_interactions": ["compliment", "playful_teasing"],
                },
                "beats": [
                    {
                        "beat_id": "public_001",
                        "order": 1,
                        "type": "dialogue",
                        "required_movement": "Conversar em público.",
                        "canonical_line": "Oi.",
                        "next_beat_id": "private_001",
                        "allowed_transitions": {"engaged": "private_001"},
                    },
                ],
            },
            {
                "block_id": "private_messages",
                "order": 2,
                "entry_beat_id": "private_001",
                "interaction_context": {
                    "setting": "private_messages",
                    "privacy": "private",
                },
                "beats": [
                    {
                        "beat_id": "private_001",
                        "order": 1,
                        "type": "dialogue",
                        "required_movement": "Conversar em particular.",
                        "canonical_line": "Agora estamos a sós.",
                        "interaction_context": {
                            "mutual_attraction_confirmed": True,
                            "recoverable_tensions": ["premature_intimacy"],
                        },
                        "next_beat_id": "end_ok",
                        "allowed_transitions": {"engaged": "end_ok"},
                    },
                ],
            },
            {
                "block_id": "endings",
                "order": 99,
                "entry_beat_id": "end_ok",
                "beats": [
                    {
                        "beat_id": "end_ok",
                        "order": 1,
                        "type": "ending",
                        "canonical_line": "Fim.",
                        "ending": {"run_status": "completed", "ending_code": "ok"},
                    }
                ],
            },
        ],
    }


def test_compilador_herda_card_bloco_e_beat() -> None:
    compiled = compile_editorial_document(_document())
    script = PilotScript(compiled)

    public = script.beats["public_001"]["interaction_context"]
    assert public["relationship_stage"] == "acquaintances"
    assert public["setting"] == "public"
    assert public["privacy"] == "public"
    assert public["allowed_interactions"] == ["compliment", "playful_teasing"]

    private = script.beats["private_001"]["interaction_context"]
    assert private["relationship_stage"] == "strangers"
    assert private["setting"] == "private_messages"
    assert private["privacy"] == "private"
    assert private["mutual_attraction_confirmed"] is True
    assert private["recoverable_tensions"] == ["premature_intimacy"]


def test_progressao_so_e_ativada_por_fato_confirmado() -> None:
    compiled = compile_editorial_document(_document())
    context = compiled["scene"]["beats"][0]["interaction_context"]

    before = resolve_interaction_context(context, {})
    assert before.relationship_stage == "acquaintances"
    assert before.intimacy_level == 0
    assert before.mary_disclosed_desire is False
    assert before.terminal_violations == ("explicit_sexual_escalation",)
    assert before.applied_progressions == ()

    after = resolve_interaction_context(context, {"mary_disclosed_desire": "true"})
    assert after.relationship_stage == "desire_disclosed"
    assert after.intimacy_level == 2
    assert after.mary_disclosed_desire is True
    assert after.allowed_interactions == ("explicit_flirting", "sexual_desire")
    assert after.terminal_violations == ("coercion",)
    assert after.applied_progressions == ("desire_disclosed",)


def test_beat_context_expoe_contexto_efetivo_ao_modelo() -> None:
    script = PilotScript(compile_editorial_document(_document()))
    previous = PilotState(node_id="public_001")
    state = PilotState(
        node_id="private_001",
        facts={"mary_disclosed_desire": "true"},
    )
    turn = PilotTurn(
        engagement="engaged",
        target_id="private_001",
        visible_fallback="Agora estamos a sós.",
        system_prompt="",
        state=state,
    )

    context = build_beat_context(script, previous, turn)
    assert context.interaction_context.setting == "private_messages"
    assert context.interaction_context.privacy == "private"
    assert context.interaction_context.mutual_attraction_confirmed is True
    assert context.interaction_context.relationship_stage == "desire_disclosed"

    rendered = render_beat_context(context)
    assert "CONTEXTO RELACIONAL EFETIVO" in rendered
    assert "estágio da relação: desire_disclosed" in rendered
    assert "desejo de Mary revelado: sim" in rendered
    assert "progressões ativadas por fatos confirmados" in rendered


def test_contexto_invalido_falha_na_compilacao() -> None:
    document = _document()
    document["interaction_context"]["intimacy_level"] = 9

    with pytest.raises(ValueError, match="entre 0 e 5"):
        compile_editorial_document(document)


def test_progressao_nao_pode_alterar_campo_desconhecido() -> None:
    document = _document()
    document["interaction_context"]["progression"][0]["set"]["invented_permission"] = True

    with pytest.raises(ValueError, match="campos desconhecidos"):
        compile_editorial_document(document)
