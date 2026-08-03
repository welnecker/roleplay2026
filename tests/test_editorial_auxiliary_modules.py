from __future__ import annotations

from pathlib import Path


MAPPINGS = {
    "services/contact_exchange_pilot.py": "services/editorial_contact_exchange.py",
    "services/alfredinho_call_pilot.py": "services/editorial_partner_call.py",
    "services/private_thought_pilot.py": "services/editorial_private_thought.py",
    "services/supermarket_intent_pilot.py": "services/editorial_intent.py",
}


def test_auxiliares_concretos_vivem_em_modulos_editoriais() -> None:
    for legacy_path, editorial_path in MAPPINGS.items():
        legacy = Path(legacy_path).read_text(encoding="utf-8")
        editorial = Path(editorial_path).read_text(encoding="utf-8")

        assert "sys.modules[__name__]" in legacy
        assert len(editorial.splitlines()) > len(legacy.splitlines())


def test_modulos_editoriais_existem_sem_sufixo_pilot() -> None:
    for editorial_path in MAPPINGS.values():
        assert Path(editorial_path).is_file()
        assert "_pilot.py" not in editorial_path
