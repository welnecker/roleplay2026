from pathlib import Path

import yaml


BRIDGE_SOURCE = Path("services/editorial_bridge.py")
PHASE_SOURCE = Path("services/editorial_phase_contract.py")
PARKING_EXTENSION = Path(
    "installed_stories/casada_frustrada/content/extensions/parking_dialogue.yaml"
)


def test_bridge_contract_separates_consumed_origin_from_reserved_target() -> None:
    source = BRIDGE_SOURCE.read_text(encoding="utf-8")

    assert "MOVIMENTO DE ORIGEM JÁ CONCLUÍDO — PROIBIDO REPETIR" in source
    assert "LINHA DE ORIGEM JÁ CONSUMIDA — PROIBIDO PARAFRASEAR" in source
    assert "OBJETIVO FUTURO RESERVADO AO DESTINO — PROIBIDO EXECUTAR" in source
    assert "não é uma segunda versão do beat anterior nem uma prévia do seguinte" in source


def test_bridge_phase_exposes_both_semantic_boundaries_to_evaluation() -> None:
    source = PHASE_SOURCE.read_text(encoding="utf-8")

    assert "repetir ou parafrasear o movimento de origem já concluído" in source
    assert "executar total ou parcialmente o objetivo reservado ao destino" in source
    assert "criar nova pergunta, promessa, dúvida ou obstáculo sem pendência real" in source
    assert "bridge_pending" in source


def test_bridge_state_clears_semantic_boundary_facts_after_release() -> None:
    source = BRIDGE_SOURCE.read_text(encoding="utf-8")

    for key in (
        "_BRIDGE_ORIGIN_OBJECTIVE_KEY",
        "_BRIDGE_ORIGIN_CANONICAL_KEY",
        "_BRIDGE_TARGET_OBJECTIVE_KEY",
        "_BRIDGE_TARGET_CANONICAL_KEY",
    ):
        assert source.count(key) >= 3


def test_parking_closing_has_no_unconditional_artificial_pending_beat() -> None:
    payload = yaml.safe_load(PARKING_EXTENSION.read_text(encoding="utf-8"))
    patches = payload["patch_beats"]
    appended = payload["append_blocks"]

    assert "next_beat_id" not in patches.get("reencontro_fila_014", {})
    assert all(
        block.get("block_id") != "antes_despedida_conversa"
        for block in appended
    )


def test_conclusive_closing_beats_are_declared_indivisible() -> None:
    payload = yaml.safe_load(PARKING_EXTENSION.read_text(encoding="utf-8"))
    patches = payload["patch_beats"]

    assert patches["reencontro_fila_015"]["response_boundary"] == "integrated_canonical"
    assert patches["reencontro_fila_016"]["response_boundary"] == "integrated_canonical"
