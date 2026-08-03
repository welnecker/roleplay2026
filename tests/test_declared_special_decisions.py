from __future__ import annotations

from pathlib import Path

from packages.loader import load_manifest
from services.editorial_package_loader import compile_editorial_package
from services.editorial_progression import decide_editorial_progression_turn
from services.editorial_runtime import EditorialState


ROOT = Path(__file__).resolve().parents[1]
CARD_ROOT = ROOT / "installed_stories" / "casada_frustrada"
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "editorial_cards" / "encontro_no_cafe"
CORE = ROOT / "services" / "editorial_progression_impl.py"


def _card_script():
    return compile_editorial_package(load_manifest(CARD_ROOT / "manifest.yaml"))


def test_aceite_declarado_avanca_e_aplica_fatos() -> None:
    turn = decide_editorial_progression_turn(
        _card_script(),
        EditorialState(node_id="reencontro_fila_007"),
        "Espero sim... não tô com pressa hoje.",
    )

    assert turn.target_id == "reencontro_fila_008"
    assert turn.state.facts["_last_user_intent"] == "accept"
    assert turn.state.facts["help_to_car"] == "accepted"
    assert turn.state.facts["_scene_location"] == "estacionamento_caminho"


def test_recusa_declarada_redireciona_para_patío() -> None:
    turn = decide_editorial_progression_turn(
        _card_script(),
        EditorialState(node_id="reencontro_fila_007"),
        "Não posso esperar, preciso ir.",
    )

    assert turn.target_id == "yard_help_refused_001"
    assert turn.finished is False
    assert turn.state.facts["_last_user_intent"] == "refuse"
    assert turn.state.facts["help_to_car"] == "refused"


def test_resposta_ambigua_repete_sem_avancar() -> None:
    turn = decide_editorial_progression_turn(
        _card_script(),
        EditorialState(node_id="reencontro_fila_007"),
        "Talvez...",
    )

    assert turn.target_id == "reencontro_fila_007"
    assert turn.state.facts["_last_user_intent"] == "unclear"
    assert turn.state.pending_next_beat_id == ""


def test_card_sem_decisao_especial_usa_fluxo_normal() -> None:
    script = compile_editorial_package(load_manifest(FIXTURE_ROOT / "manifest.yaml"))
    turn = decide_editorial_progression_turn(
        script,
        EditorialState(node_id="cafe_001"),
        "Claro, pode sentar.",
    )

    assert turn.target_id == "cafe_002"
    assert "help_to_car" not in turn.state.facts


def test_nucleo_nao_conhece_ids_ou_fatos_da_historia() -> None:
    source = CORE.read_text(encoding="utf-8")

    for forbidden in (
        "reencontro_fila_007",
        "yard_help_refused_001",
        "help_to_car",
        "supermercado_caixa",
        "estacionamento_caminho",
    ):
        assert forbidden not in source
    assert "decide_declared_special_turn" in source
