from __future__ import annotations

from pathlib import Path

import yaml

from services.editorial_contextual_destination import build_contextual_classification_prompt
from services.editorial_interaction_context import resolve_interaction_context


def _first_contact_context():
    source = Path(
        "installed_stories/casada_frustrada/content/extensions/dynamic_endings.yaml"
    )
    raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    patch = raw["patch_beats"]["encontro_acidental_001"]["interaction_context"]
    return resolve_interaction_context(patch, {})


def test_lesao_grave_que_inviabiliza_proximo_beat_e_ruptura_terminal() -> None:
    context = _first_contact_context()

    assert "unsupported_dramatic_emergency_requiring_new_plot" in context.recoverable_tensions
    assert "sustained_dramatic_emergency_making_next_beat_impossible" in context.terminal_violations


def test_prompt_protege_integridade_dramatica_do_roteiro() -> None:
    prompt = build_contextual_classification_prompt(_first_contact_context())

    assert "não pode criar uma nova trajetória narrativa" in prompt
    assert "hospital, ambulância, médico, investigação, viagem" in prompt
    assert "torna o próximo beat impossível" in prompt
    assert "primeira sugestão recuperável" in prompt
    assert "persistência ou fato já consolidado" in prompt
