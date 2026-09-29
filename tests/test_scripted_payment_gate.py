from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.novel_frame_patch import compile_novel_frame_story
from services.novel_v2_adapter import payment_gate_from_script

CORE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "roteiro_editor_desktop"
    / "core.py"
)
EDITOR_DIR = CORE_PATH.parent
if str(EDITOR_DIR) not in sys.path:
    sys.path.insert(0, str(EDITOR_DIR))
spec = importlib.util.spec_from_file_location("payment_gate_editor_core", CORE_PATH)
assert spec and spec.loader
editor_core = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = editor_core
spec.loader.exec_module(editor_core)


def _base_document() -> dict:
    return {
        "format_version": 3,
        "package_id": "roleplay2026.teste",
        "script_version": "1",
        "introduction": "Abertura.",
        "character": {"name": "Mary"},
        "blocks": [],
    }


def _draft(message: str = "Quer saber como termina essa aventura?") -> str:
    return (
        "[DESCRIÇÃO] Primeiro quadro.\n"
        "[FALA mary] Começou.\n"
        f"[PAGAMENTO] {message}\n"
        "[DESCRIÇÃO] Segundo quadro.\n"
        "[FALA mary] Continuou."
    )


def test_editor_compila_pagamento_como_linha_de_controle() -> None:
    rows = editor_core.compile_rows(
        _draft(),
        package_id="roleplay2026.teste",
        script_version="200",
        frame_prefix="cena",
    )

    gate = rows[2]
    assert gate["line_id"] == "cena_001_pagamento_01"
    assert gate["instruction"] == "[PAGAMENTO] Quer saber como termina essa aventura?"
    assert gate["image_id"] == ""
    assert gate["motion_id"] == ""
    assert gate["audio_id"] == ""


def test_pagamento_precisa_ficar_entre_dois_quadros() -> None:
    with pytest.raises(editor_core.EditorError, match="próxima \[DESCRIÇÃO\]"):
        editor_core.compile_rows(
            (
                "[DESCRIÇÃO] Primeiro quadro.\n"
                "[FALA mary] Começou.\n"
                "[PAGAMENTO]\n"
                "[FALA mary] Não pode."
            ),
            package_id="roleplay2026.teste",
            script_version="200",
            frame_prefix="cena",
        )


def test_compilador_anexa_paywall_ao_quadro_anterior_sem_criar_entry() -> None:
    rows = editor_core.compile_rows(
        _draft("Continue para descobrir o final."),
        package_id="roleplay2026.teste",
        script_version="200",
        frame_prefix="cena",
    )

    document = compile_novel_frame_story(
        _base_document(),
        rows,
        script_version="200",
    )
    beats = document["blocks"][0]["beats"]
    assert [beat["beat_id"] for beat in beats] == ["cena_001", "cena_002"]

    first_payload = json.loads(
        beats[0]["required_movement"].removeprefix("NOVEL_FRAME_V2\n")
    )
    assert first_payload["payment_gate"] == {
        "message": "Continue para descobrir o final."
    }
    assert len(first_payload["entries"]) == 1
    assert first_payload["entries"][0]["actor"] == "mary"


def test_runtime_le_mensagem_do_paywall_no_quadro_atual() -> None:
    objective = "NOVEL_FRAME_V2\n" + json.dumps(
        {
            "frame_id": "cena_001",
            "entries": [],
            "payment_gate": {"message": "Só mais um passo..."},
        },
        ensure_ascii=False,
    )
    script = SimpleNamespace(
        beats={"cena_001": {"objective": objective}},
    )

    assert payment_gate_from_script(script, "cena_001") == "Só mais um passo..."
    assert payment_gate_from_script(script, "inexistente") == ""
