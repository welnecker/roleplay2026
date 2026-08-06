from __future__ import annotations

from services.editorial_beat_context import BeatContext
from services.editorial_organic_beat_rhythm import (
    build_organic_beat_frame,
    render_organic_beat_frame,
)
from services.editorial_runtime_impl import PilotState


def _context() -> BeatContext:
    return BeatContext(
        source_beat_id="encontro_acidental_001",
        target_beat_id="encontro_acidental_002",
        objective="Mary confirma se o usuário não se machucou.",
        canonical_line="Tem certeza que tá tudo bem? Não machucou?",
        dramatic_direction="Demonstrar preocupação sem prolongar.",
        user_intent="",
        transition_status="",
        required_outcomes=(),
        forbidden_outcomes=(),
        allowed_topics=(),
        confirmed_facts=(),
        unknown_facts=(),
        max_sentences=2,
        max_questions=2,
        response_boundary="",
    )


def test_frame_coloca_o_beat_no_centro_da_resposta() -> None:
    document = {
        "organic_beat_rhythm": {
            "defaults": {
                "preferred_sentences": 2,
                "max_internal_pressures": 2,
            }
        }
    }
    frame = build_organic_beat_frame(document, {}, _context(), PilotState())
    prompt = render_organic_beat_frame(frame)

    assert "Este turno existe para: Mary confirma se o usuário não se machucou." in prompt
    assert "Tem certeza que tá tudo bem? Não machucou?" in prompt
    assert "Expanda em direção ao núcleo do beat" in prompt
    assert "Não produza uma interpretação interna rica seguida de uma fala pobre" in prompt
    assert "Pare assim que o movimento obrigatório" in prompt


def test_pensamento_interno_e_exigido_em_primeira_pessoa() -> None:
    document = {
        "organic_beat_rhythm": {
            "thought_voice_rule": (
                "Todo pensamento interno de Mary deve estar em primeira pessoa, "
                "como voz íntima em eu; nunca escreva Mary pensa ou Mary sente."
            )
        }
    }
    frame = build_organic_beat_frame(document, {}, _context(), PilotState())
    prompt = render_organic_beat_frame(frame)

    assert "primeira pessoa" in prompt
    assert "voz íntima" in prompt
    assert "Mary pensa" in prompt
    assert "Mary sente" in prompt


def test_intensidade_nao_aumenta_orcamento_de_frases() -> None:
    document = {
        "organic_beat_rhythm": {
            "defaults": {"preferred_sentences": 3}
        }
    }
    state = PilotState(trust=9, desire=9)
    frame = build_organic_beat_frame(document, {}, _context(), state)

    assert frame.intensity == "charged"
    assert frame.preferred_sentences == 2


def test_override_por_beat_permanece_declarativo() -> None:
    document = {
        "organic_beat_rhythm": {
            "defaults": {
                "preferred_sentences": 2,
                "max_internal_pressures": 2,
            }
        }
    }
    target = {
        "organic_beat_rhythm": {
            "intensity": "restrained",
            "preferred_sentences": 1,
            "max_internal_pressures": 1,
            "stop_rule": "Pare imediatamente depois da pergunta.",
        }
    }
    frame = build_organic_beat_frame(document, target, _context(), PilotState())

    assert frame.intensity == "restrained"
    assert frame.preferred_sentences == 1
    assert frame.max_internal_pressures == 1
    assert frame.stop_rule == "Pare imediatamente depois da pergunta."
