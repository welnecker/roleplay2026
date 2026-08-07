from __future__ import annotations

from pathlib import Path

from packages.loader import load_manifest
from services.editorial_package_loader import (
    compile_editorial_package,
    load_editorial_document,
    merge_editorial_extension,
)
from services.editorial_progression import (
    decide_editorial_progression_turn,
    editorial_followups_after,
    state_after_editorial_followup,
)
from services.editorial_runtime import EditorialState


ROOT = Path(__file__).resolve().parents[1]
CARD_ROOT = ROOT / "installed_stories" / "casada_frustrada"
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "editorial_cards" / "encontro_no_cafe"
IMPLEMENTATION = ROOT / "services" / "editorial_progression_impl.py"


def test_casada_frustrada_declara_politicas_estruturais_no_pacote() -> None:
    package = load_manifest(CARD_ROOT / "manifest.yaml")
    document = load_editorial_document(package)

    assert document["bridge_policy"] == {"mode": "required"}
    assert "organic_slack" not in document

    policy = document["runtime_policy"]
    assert policy["strict_canonical"]["beat_prefixes"] == ["motel_"]
    assert policy["strict_canonical"]["state_fact"] == "_strict_motel_canonical"

    updates = policy["state_updates"]["automatic_followups"]
    assert updates[0]["target_prefix"] == "retorno_casa_"
    assert updates[1]["target_id"] == "mensagens_iniciais_001"
    assert updates[1]["facts"]["active_interlocutor"] == "janio"


def test_extensao_substitui_politicas_declaradas_inteiras() -> None:
    document = {
        "bridge_policy": {"mode": "disabled"},
        "runtime_policy": {"strict_canonical": {"beat_ids": ["old"]}},
    }
    merged = merge_editorial_extension(
        document,
        {
            "bridge_policy": {"mode": "required"},
            "runtime_policy": {"state_updates": {"automatic_followups": []}},
        },
    )

    assert merged["bridge_policy"] == {"mode": "required"}
    assert merged["runtime_policy"] == {"state_updates": {"automatic_followups": []}}


def test_outro_card_nao_herda_politicas_da_casada_frustrada() -> None:
    package = load_manifest(FIXTURE_ROOT / "manifest.yaml")
    document = load_editorial_document(package)

    assert "bridge_policy" not in document
    assert "runtime_policy" not in document


def test_manifesto_carrega_politica_por_ultimo() -> None:
    package = load_manifest(CARD_ROOT / "manifest.yaml")
    extensions = package.manifest.runtime.editorial.extensions
    assert extensions[-1] == "content/extensions/runtime.yaml"


def test_continuidade_estrita_e_ativada_pela_politica_do_card() -> None:
    package = load_manifest(CARD_ROOT / "manifest.yaml")
    script = compile_editorial_package(package)

    turn = decide_editorial_progression_turn(
        script,
        EditorialState(node_id="motel_006"),
        "sim... continua",
    )

    assert turn.state.facts["_strict_motel_canonical"] == "true"
    assert "CONTINUIDADE ESTRITA DO MOTEL" in turn.system_prompt


def test_card_sem_politica_nao_recebe_estado_de_continuidade_estrita() -> None:
    package = load_manifest(FIXTURE_ROOT / "manifest.yaml")
    script = compile_editorial_package(package)
    turn = decide_editorial_progression_turn(
        script,
        EditorialState(node_id="opening_001"),
        "oi",
    )
    assert "_strict_motel_canonical" not in turn.state.facts
