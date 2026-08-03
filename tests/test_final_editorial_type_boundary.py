from __future__ import annotations

from pathlib import Path


COMPATIBILITY_BOUNDARY = {
    Path("services/editorial_runtime_impl.py"),
    Path("services/editorial_runtime_types.py"),
}
FORBIDDEN = ("PilotScript", "PilotState", "PilotTurn")


def test_tipos_pilot_ficam_restritos_a_fronteira_de_compatibilidade() -> None:
    violations: list[str] = []
    for path in Path("services").glob("*.py"):
        if path in COMPATIBILITY_BOUNDARY:
            continue
        source = path.read_text(encoding="utf-8")
        found = [name for name in FORBIDDEN if name in source]
        if found:
            violations.append(f"{path}: {', '.join(found)}")

    assert violations == []


def test_modulos_editoriais_restantes_usam_contrato_nominal() -> None:
    paths = (
        Path("services/editorial_intent.py"),
        Path("services/editorial_contact_exchange.py"),
        Path("services/editorial_partner_call.py"),
        Path("services/editorial_private_thought.py"),
        Path("services/editorial_turn_finalization.py"),
    )

    for path in paths:
        source = path.read_text(encoding="utf-8")
        assert "from services.editorial_runtime_types import" in source
        assert all(name not in source for name in FORBIDDEN)


def test_fronteira_publica_expoe_apenas_nomes_editoriais() -> None:
    public_api = Path("services/editorial_runtime.py").read_text(encoding="utf-8")
    assert all(name not in public_api for name in FORBIDDEN)
    assert "EditorialScript" in public_api
    assert "EditorialState" in public_api
    assert "EditorialTurn" in public_api
