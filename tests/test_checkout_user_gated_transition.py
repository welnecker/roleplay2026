from __future__ import annotations

from pathlib import Path

from packages.loader import load_manifest
from services.editorial_package_loader import load_editorial_document


ROOT = Path(__file__).resolve().parents[1]
CARD_ROOT = ROOT / "installed_stories" / "casada_frustrada"


def _beat(document: dict, beat_id: str) -> dict:
    for block in document.get("blocks", []):
        for beat in block.get("beats", []):
            if beat.get("beat_id") == beat_id:
                return beat
    raise AssertionError(f"Beat não encontrado: {beat_id}")


def test_caixa_devolve_turno_ao_usuario_antes_da_passagem_temporal() -> None:
    package = load_manifest(CARD_ROOT / "manifest.yaml")
    document = load_editorial_document(package)

    aviso = _beat(document, "reencontro_fila_006")
    pedido = _beat(document, "reencontro_fila_007")

    assert aviso.get("automatic_followups") == []
    assert aviso["next_beat_id"] == "reencontro_fila_007"
    assert "devolver obrigatoriamente o turno ao usuário" in aviso["dramatic_direction"]

    assert pedido["canonical_line"].startswith(
        "[MINUTOS DEPOIS — SUPERMERCADO CAIXA]\n\n"
    )
    assert "Passou rapidinho pelo caixa" in pedido["canonical_line"]
    assert "depois de uma resposta do usuário" in pedido["dramatic_direction"]
