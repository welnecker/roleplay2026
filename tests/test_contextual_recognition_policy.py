from __future__ import annotations

from pathlib import Path

import yaml

from services.editorial_contextual_destination import build_contextual_classification_prompt
from services.editorial_interaction_context import resolve_interaction_context


ROOT = Path(__file__).resolve().parents[1]
POLICY = (
    ROOT
    / "installed_stories"
    / "casada_frustrada"
    / "content"
    / "extensions"
    / "dynamic_endings.yaml"
)


def _first_contact_context():
    raw = yaml.safe_load(POLICY.read_text(encoding="utf-8"))
    context = raw["patch_beats"]["encontro_acidental_001"]["interaction_context"]
    return resolve_interaction_context(context, {})


def test_reconhecimento_casual_em_local_compartilhado_nao_e_ruptura() -> None:
    context = _first_contact_context()

    assert "recognition_from_shared_residence" in context.allowed_interactions
    assert "answer_to_character_requested_identification" in context.allowed_interactions
    assert "casual_prior_sighting" in context.allowed_interactions
    assert "prior_acquaintance_or_knowledge_breaking_anonymity_or_secrecy" not in context.terminal_violations
    assert "invasive_private_knowledge_breaking_secrecy" in context.terminal_violations


def test_prompt_exige_clarificacao_antes_de_encerrar_por_conhecimento_ambiguo() -> None:
    prompt = build_contextual_classification_prompt(_first_contact_context())

    assert "responde diretamente a uma pergunta feita pela personagem" in prompt
    assert "reconhecimento casual decorrente de local compartilhado" in prompt
    assert "conhecimento privado, invasivo" in prompt
    assert "prefira continuidade ou clarificação" in prompt
