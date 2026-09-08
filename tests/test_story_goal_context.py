from pathlib import Path

import yaml

from services.narrative_context import build_narrative_context, render_story_goal


def test_meta_global_e_direta_mas_nao_autoriza_antecipacao() -> None:
    document = yaml.safe_load(
        Path("installed_stories/camilly/content/editorial.yaml").read_text(encoding="utf-8")
    )

    rendered = render_story_goal(document)

    assert "META GLOBAL, PRIVADA E OBRIGATÓRIA" in rendered
    assert "Conseguir uma carona" in rendered
    assert "Seduzir progressivamente" in rendered
    assert "encontro íntimo previsto no carro" in rendered
    assert "não autoriza executar" in rendered
    assert "Nunca presuma desejo, excitação, aceite, consentimento" in rendered


def test_meta_global_entra_no_contexto_de_beat_e_de_ponte() -> None:
    document = yaml.safe_load(
        Path("installed_stories/camilly/content/editorial.yaml").read_text(encoding="utf-8")
    )

    canonical = build_narrative_context(document, [], {}, beat_id="encontro_001")
    bridge = build_narrative_context(
        document,
        [],
        {},
        beat_id="encontro_001",
        runtime_phase="bridge",
    )

    assert "META GLOBAL, PRIVADA E OBRIGATÓRIA" in canonical
    assert "META GLOBAL, PRIVADA E OBRIGATÓRIA" in bridge
