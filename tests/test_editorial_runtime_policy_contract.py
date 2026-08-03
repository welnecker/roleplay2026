from __future__ import annotations

from pathlib import Path

from packages.loader import load_manifest
from services.editorial_package_loader import (
    compile_editorial_package,
    load_editorial_document,
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
        EditorialState(node_id=script.first_beat_id),
        "sim",
    )

    assert "_strict_motel_canonical" not in turn.state.facts


def test_pontes_aplicam_atualizacoes_de_estado_declaradas() -> None:
    package = load_manifest(CARD_ROOT / "manifest.yaml")
    compile_editorial_package(package)
    followups = editorial_followups_after("reencontro_fila_016")

    home_state = state_after_editorial_followup(EditorialState(), followups[0])
    message_state = state_after_editorial_followup(home_state, followups[-1])

    assert home_state.facts["alfredinho_has_voice"] == "false"
    assert message_state.facts["active_interlocutor"] == "janio"
    assert message_state.facts["alfredinho_has_voice"] == "false"


def test_runtime_nao_contem_ids_das_politicas_extraidas() -> None:
    source = IMPLEMENTATION.read_text(encoding="utf-8")

    assert "_STRICT_MOTEL_BEAT" not in source
    assert 'startswith("retorno_casa_")' not in source
    assert '== "mensagens_iniciais_001"' not in source
