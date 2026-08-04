from __future__ import annotations

from services.editorial_compiler import compile_editorial_document
from services.editorial_content import load_source_document
from services.editorial_runtime_impl import PilotScript
from services.editorial_progression import (
    editorial_followups_after,
    prepare_editorial_script,
)


FAREWELL_BEAT_ID = "encontro_acidental_despedida_001"


def _load() -> None:
    raw = load_source_document()
    script = PilotScript(compile_editorial_document(raw))
    prepare_editorial_script(script)


def test_reencontro_exibe_passagem_de_tempo_e_local() -> None:
    _load()
    bridge = editorial_followups_after(FAREWELL_BEAT_ID)[0]

    assert bridge["text"].startswith("[ALGUM TEMPO DEPOIS — SUPERMERCADO FILA]")
    assert "Olha você de novo" in bridge["text"]


def test_pontes_finais_tambem_exibem_mudanca_de_cena() -> None:
    _load()
    bridges = editorial_followups_after("reencontro_fila_016")

    assert all(item["text"].startswith("[ALGUM TEMPO DEPOIS — ") for item in bridges)
    assert "CARRO MARY SOZINHA" in bridges[0]["text"]
    assert "CASA DE MARY" in bridges[1]["text"]
    assert "MENSAGEM PRIVADA JANIO" in bridges[2]["text"]
    assert bridges[2]["text"].rstrip().endswith("Oi?")
