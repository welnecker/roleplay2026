from __future__ import annotations

from pathlib import Path

from packages.loader import load_manifest
from services.editorial_package_loader import load_editorial_document
from services.editorial_personality_triggers import (
    active_personality_triggers,
    render_personality_triggers,
)
from services.editorial_runtime_types import EditorialState


CARD_ROOT = Path(__file__).resolve().parent.parent / "installed_stories" / "casada_frustrada"


def _document() -> dict:
    package = load_manifest(CARD_ROOT / "manifest.yaml")
    return load_editorial_document(package)


def test_card_declara_gatilhos_psicologicos_de_personalidade() -> None:
    policy = _document()["relationship_memory"]["personality_triggers"]

    assert policy["max_active_triggers"] == 2
    assert "defensive_humor" in policy["triggers"]
    assert "candid_desire" in policy["triggers"]
    assert "wounded_pride" in policy["triggers"]


def test_baixa_confianca_ativa_humor_defensivo() -> None:
    state = EditorialState(trust=2, desire=3, patience=4)

    triggers = active_personality_triggers(
        _document(), state, "Conversa leve no supermercado.", "engaged"
    )

    assert [item.trigger_id for item in triggers] == ["defensive_humor"]


def test_confianca_e_desejo_altos_ativam_franqueza() -> None:
    state = EditorialState(trust=7, desire=8, patience=6)

    triggers = active_personality_triggers(
        _document(), state, "Mary admite o que sente.", "engaged"
    )

    assert [item.trigger_id for item in triggers] == ["candid_desire"]


def test_desdem_ativa_orgulho_mesmo_com_baixa_confianca() -> None:
    state = EditorialState(trust=2, desire=5, patience=3)

    triggers = active_personality_triggers(
        _document(), state, "O usuário responde com desdém.", "dismissive"
    )

    assert [item.trigger_id for item in triggers] == ["wounded_pride"]


def test_ternura_exige_contexto_e_estado_compativeis() -> None:
    state = EditorialState(trust=8, desire=5, patience=7)

    active = active_personality_triggers(
        _document(), state, "Ele fala de medo, cuidado e confiança.", "engaged"
    )
    unrelated = active_personality_triggers(
        _document(), state, "Ele pergunta sobre o corredor do mercado.", "engaged"
    )

    assert [item.trigger_id for item in active] == ["safe_tenderness"]
    assert unrelated == []


def test_prompt_nao_expoe_rotulos_internos() -> None:
    state = EditorialState(trust=2, desire=3, patience=4)
    triggers = active_personality_triggers(
        _document(), state, "Conversa leve.", "engaged"
    )

    rendered = render_personality_triggers(triggers)

    assert "PERSONALIDADE ATIVADA PELO CONTEXTO" in rendered
    assert "defensive_humor" not in rendered
    assert "não mencione gatilhos" in rendered.casefold()


def test_motor_e_reutilizavel_por_outro_card() -> None:
    document = {
        "personality_triggers": {
            "max_active_triggers": 1,
            "triggers": {
                "professional_focus": {
                    "priority": 5,
                    "when": {
                        "context_patterns": [r"\\btrabalho\\b"],
                        "dimensions": {"patience": {"min": 3, "max": 10}},
                    },
                    "effect": "Lia responde de modo objetivo e profissional.",
                }
            },
        }
    }
    state = EditorialState(patience=5)

    triggers = active_personality_triggers(
        document, state, "Vamos falar de trabalho.", "engaged"
    )

    assert [item.trigger_id for item in triggers] == ["professional_focus"]
