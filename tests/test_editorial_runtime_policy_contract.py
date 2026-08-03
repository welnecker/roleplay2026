from __future__ import annotations

from pathlib import Path

from packages.loader import load_manifest
from services.editorial_package_loader import load_editorial_document


ROOT = Path(__file__).resolve().parents[1]
CARD_ROOT = ROOT / "installed_stories" / "casada_frustrada"
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "editorial_cards" / "encontro_no_cafe"


def test_casada_frustrada_declara_politicas_especificas_no_pacote() -> None:
    package = load_manifest(CARD_ROOT / "manifest.yaml")
    document = load_editorial_document(package)

    policy = document["organic_slack"]

    assert policy["enabled"] is True
    assert policy["excluded_beats"] == ["reencontro_fila_007"]
    assert policy["strict_canonical"]["beat_prefixes"] == ["motel_"]
    assert policy["strict_canonical"]["state_fact"] == "_strict_motel_canonical"

    updates = policy["state_updates"]["automatic_followups"]
    assert updates[0]["target_prefix"] == "retorno_casa_"
    assert updates[1]["target_id"] == "mensagens_iniciais_001"
    assert updates[1]["facts"]["active_interlocutor"] == "janio"


def test_outro_card_nao_herda_politicas_da_casada_frustrada() -> None:
    package = load_manifest(FIXTURE_ROOT / "manifest.yaml")
    document = load_editorial_document(package)

    policy = document.get("organic_slack") or {}

    assert "reencontro_fila_007" not in policy.get("excluded_beats", [])
    assert "motel_" not in (policy.get("strict_canonical") or {}).get("beat_prefixes", [])
    assert "state_updates" not in policy


def test_manifesto_carrega_politica_por_ultimo() -> None:
    package = load_manifest(CARD_ROOT / "manifest.yaml")
    extensions = package.manifest.runtime.editorial.extensions

    assert extensions[-1] == "content/extensions/runtime.yaml"
