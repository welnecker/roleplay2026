from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

CORE = Path(__file__).resolve().parents[1] / "tools" / "card_editor_desktop" / "core.py"
spec = importlib.util.spec_from_file_location("card_editor_core", CORE)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def _manifest() -> dict:
    return {
        "format_version": 2,
        "package_id": "roleplay2026.exemplo",
        "version": "1.2.3",
        "author": {"id": "x", "name": "Autor"},
        "entrypoint": "story.yaml",
        "runtime": {"kind": "editorial", "editorial": {"source": "content/editorial.yaml"}},
        "card": {
            "title": "Antigo",
            "subtitle": "Sub",
            "description": "Desc",
            "genres": ["Drama"],
            "chapter_label": "História completa",
            "cover": "assets/capas/capa.webp",
            "character_profile": {
                "name": "Pessoa",
                "identity": "Identidade",
                "personality": "Personalidade",
                "intention": "Intenção",
            },
        },
        "cast_customization": {
            "enabled": True,
            "members": [
                {"actor_id": "pessoa", "label": "Pessoa", "default_name": "Pessoa", "gender": "neutral"}
            ],
        },
        "commerce": {
            "access": "paid",
            "price_cents": 990,
            "currency": "BRL",
            "replay_policy": "new_purchase",
        },
    }


def test_apply_card_draft_preserves_structural_manifest_fields() -> None:
    original = _manifest()
    draft = module.CardDraft(
        title="A Prima Gótica",
        subtitle="Uma visita muda de rumo.",
        description="Nova descrição.",
        genres="Drama, Romance adulto",
        chapter_label="História completa",
        cover="assets/capas/gotica.webp",
        profile_name="Gerusa",
        profile_identity="Quem é Gerusa.",
        profile_personality="Como ela é.",
        profile_intention="O que pretende.",
        price_brl="9,90",
        replay_policy="new_purchase",
    )

    updated = module.apply_card_draft(original, draft)

    assert updated["package_id"] == original["package_id"]
    assert updated["runtime"] == original["runtime"]
    assert updated["cast_customization"] == original["cast_customization"]
    assert updated["card"]["title"] == "A Prima Gótica"
    assert updated["card"]["genres"] == ["Drama", "Romance adulto"]
    assert updated["commerce"]["access"] == "paid"
    assert updated["commerce"]["price_cents"] == 990


def test_price_parser_accepts_brazilian_format() -> None:
    assert module.parse_price_brl("R$ 9,90") == 990
    assert module.parse_price_brl("1.234,56") == 123456


def test_save_and_reload_manifest(tmp_path: Path) -> None:
    path = tmp_path / "manifest.yaml"
    module.save_manifest(path, _manifest())
    loaded = module.load_manifest(path)
    assert loaded["package_id"] == "roleplay2026.exemplo"
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["commerce"]["price_cents"] == 990
