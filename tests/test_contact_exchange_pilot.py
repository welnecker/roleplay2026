from __future__ import annotations

from services.editorial_contact_exchange import (
    MARY_PHONE_NUMBER,
    apply_contact_exchange_overrides,
    decide_contact_exchange_turn,
    prepare_contact_exchange_script,
)
from services.editorial_runtime_impl import PilotScript, PilotState


def _script() -> PilotScript:
    return PilotScript(
        {
            "engagement_policy": {"categories": {}},
            "scene": {
                "first_beat_id": "reencontro_fila_014",
                "beats": [
                    {
                        "beat_id": "reencontro_fila_014",
                        "objective": "Trocar números.",
                        "units": [
                            {
                                "kind": "dialogue",
                                "anchor": "Olha... esse número vai me trazer sorte... Anota o meu também.",
                            }
                        ],
                        "on_user": {"engaged": "reencontro_fila_015"},
                    },
                    {
                        "beat_id": "reencontro_fila_015",
                        "objective": "Despedir.",
                        "units": [{"kind": "dialogue", "anchor": "Perfeito... então... tchau."}],
                        "on_user": {"engaged": "reencontro_fila_015"},
                    },
                ],
                "endings": [],
            },
        }
    )


def test_documento_publicado_entrega_numero_de_mary() -> None:
    document = {
        "script_version": "1.0.0",
        "blocks": [
            {
                "beats": [
                    {
                        "beat_id": "reencontro_fila_014",
                        "canonical_line": "Anota o meu também.",
                    }
                ]
            }
        ],
    }

    updated = apply_contact_exchange_overrides(document)
    beat = updated["blocks"][0]["beats"][0]

    assert updated["script_version"] == "1.0.2-contact-exchange"
    assert MARY_PHONE_NUMBER in beat["canonical_line"]
    assert "anota o meu também" not in beat["canonical_line"].casefold()


def test_script_carregado_entrega_numero_de_mary() -> None:
    script = prepare_contact_exchange_script(_script())
    anchor = script.beats["reencontro_fila_014"]["units"][0]["anchor"]

    assert MARY_PHONE_NUMBER in anchor


def test_pedido_para_dizer_numero_nao_pula_para_despedida() -> None:
    turn = decide_contact_exchange_turn(
        _script(),
        PilotState(node_id="reencontro_fila_014"),
        "Pode dizer, vou anotar agora.",
    )

    assert turn.target_id == "reencontro_fila_014"
    assert MARY_PHONE_NUMBER in turn.visible_fallback
    assert turn.state.facts["mary_phone_shared"] == "true"
    assert "tchau" not in turn.visible_fallback.casefold()
