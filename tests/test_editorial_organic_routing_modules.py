from __future__ import annotations

from pathlib import Path

from services.editorial_routing import resolve_declared_editorial_target
from services.editorial_runtime_impl import PilotScript


IMPLEMENTATION = Path("services/editorial_progression_impl.py")


def test_progressao_ativa_usa_modulos_de_turno_e_roteamento() -> None:
    source = IMPLEMENTATION.read_text(encoding="utf-8")

    assert "from services.editorial_organic_turns import" in source
    assert "from services.editorial_routing import" in source
    assert "_support._organic_slack_turn" not in source
    assert "_support._state_with_extracted_facts" not in source
    assert "_support._routing_state_for_declared_skips" not in source


def test_roteamento_declarado_resolve_cadeia_de_saltos() -> None:
    script = PilotScript(
        {
            "scene": {
                "first_beat_id": "inicio",
                "beats": [
                    {
                        "beat_id": "inicio",
                        "on_user": {"engaged": "intermediario"},
                    },
                    {
                        "beat_id": "intermediario",
                        "skip_when_facts": {"nome": "destino"},
                        "on_user": {"engaged": "destino"},
                    },
                    {
                        "beat_id": "destino",
                        "on_user": {"engaged": "destino"},
                    },
                ],
                "endings": [],
            }
        }
    )

    target, skipped = resolve_declared_editorial_target(
        script,
        "intermediario",
        {"nome": "Clara"},
    )

    assert target == "destino"
    assert skipped == ("intermediario",)
