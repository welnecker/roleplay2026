from dataclasses import replace

from services.editorial_beat_context import BeatContext
from services.editorial_phase_contract import adapt_context_for_runtime_phase, runtime_phase
from services.editorial_runtime_impl import PilotState


def _context() -> BeatContext:
    return BeatContext(
        source_beat_id="beat_001",
        target_beat_id="beat_001",
        objective="responder",
        canonical_line="Oi.",
        dramatic_direction="natural",
        user_intent="engaged",
        transition_status="",
        required_outcomes=(),
        forbidden_outcomes=(),
        allowed_topics=(),
        confirmed_facts=(),
        unknown_facts=(),
        max_sentences=3,
        max_questions=1,
        response_boundary="",
    )


def test_ponte_recebe_contrato_funcional_especifico() -> None:
    original = _context()
    original = replace(
        original,
        authored_thought="Já gostei dele.",
        exact_speech="Oi, Nilo.",
    )
    state = PilotState(
        facts={
            "_runtime_phase": "bridge",
            "_bridge_target_beat_id": "beat_002",
            "_bridge_origin_canonical": (
                "[PENSAMENTO]\nJá gostei dele.\n[/PENSAMENTO]\n\nOi, Nilo."
            ),
            "_bridge_target_canonical": (
                "[PENSAMENTO]\nQuero provocá-lo.\n[/PENSAMENTO]\n\nChegue mais perto."
            ),
        }
    )

    context = adapt_context_for_runtime_phase(original, state)

    assert runtime_phase(state) == "bridge"
    assert context.transition_status == "bridge_pending"
    assert any("responder genuinamente" in item for item in context.required_outcomes)
    assert any("executar o próximo beat" in item for item in context.forbidden_outcomes)
    assert "beat_002" in context.response_boundary
    assert context.authored_thought == ""
    assert context.exact_speech == ""
    assert context.forbidden_literal_texts == (
        "Já gostei dele.",
        "Oi, Nilo.",
        "Quero provocá-lo.",
        "Chegue mais perto.",
    )


def test_patio_proibe_retorno_ao_fluxo_principal() -> None:
    state = PilotState(
        facts={
            "_runtime_phase": "terminal_yard",
            "_active_yard_id": "yard_exit",
        }
    )

    context = adapt_context_for_runtime_phase(_context(), state)

    assert context.transition_status == "terminal_yard_active"
    assert any("retornar ao roteiro principal" in item for item in context.forbidden_outcomes)
    assert "yard_exit" in context.response_boundary


def test_fase_ausente_preserva_contrato_canonico() -> None:
    original = _context()
    adapted = adapt_context_for_runtime_phase(original, PilotState())

    assert adapted == original
    assert runtime_phase(PilotState()) == "canonical"
