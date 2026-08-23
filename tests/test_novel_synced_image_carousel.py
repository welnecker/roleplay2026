from __future__ import annotations

import json

from services import novel_frame_patch
from services import novel_synced_image_carousel as synced


def _base_document() -> dict[str, object]:
    frame = {
        "frame_id": "encontro_004",
        "description": "Camilly entra no carro.",
        "entries": [
            {
                "kind": "fala",
                "actor": "camilly",
                "instruction": "Então, como anda a vida?",
                "line_id": "encontro_004_camilly_fala_01",
            },
            {
                "kind": "pensamento",
                "actor": "camilly",
                "instruction": "Eu observo a reação dele.",
                "line_id": "encontro_004_camilly_pensamento_01",
            },
            {
                "kind": "fala",
                "actor": "camilly",
                "instruction": "Você ficou me devendo um ensaio.",
                "line_id": "encontro_004_camilly_fala_02",
            },
        ],
    }
    return {
        "blocks": [
            {
                "beats": [
                    {
                        "beat_id": "encontro_004",
                        "required_movement": novel_frame_patch._FRAME_PREFIX
                        + json.dumps(frame, ensure_ascii=False),
                    }
                ]
            }
        ]
    }


def _frame_from(document: dict[str, object]) -> dict[str, object]:
    beat = document["blocks"][0]["beats"][0]
    movement = beat["required_movement"]
    return json.loads(movement[len(novel_frame_patch._FRAME_PREFIX) :])


def test_legacy_document_is_exact_noop_without_image_id() -> None:
    document = _base_document()
    rows = [
        {
            "line_id": "encontro_004_descricao",
            "instruction": "[DESCRIÇÃO] Camilly entra no carro.",
            "status": "active",
        },
        {
            "line_id": "encontro_004_camilly_fala_01",
            "instruction": "[FALA camilly] Então, como anda a vida?",
            "status": "active",
        },
    ]

    result = synced.enrich_compiled_document_with_image_ids(document, rows)

    assert result is document
    assert "image_id" not in _frame_from(result)


def test_optional_image_id_is_attached_to_exact_authorial_line() -> None:
    document = _base_document()
    rows = [
        {
            "line_id": "encontro_004_descricao",
            "instruction": "[DESCRIÇÃO] Camilly entra no carro.",
            "status": "active",
            "image_id": "camilly04.webp",
        },
        {
            "line_id": "encontro_004_camilly_fala_01",
            "instruction": "[FALA camilly] Então, como anda a vida?",
            "status": "active",
            "image_id": "",
        },
        {
            "line_id": "encontro_004_camilly_pensamento_01",
            "instruction": "[PENSAMENTO camilly] Eu observo a reação dele.",
            "status": "active",
            "image_id": "camilly05.webp",
        },
    ]

    result = synced.enrich_compiled_document_with_image_ids(document, rows)
    frame = _frame_from(result)

    assert frame["image_id"] == "camilly04.webp"
    assert "image_id" not in frame["entries"][0]
    assert frame["entries"][1]["image_id"] == "camilly05.webp"
    assert "image_id" not in frame["entries"][2]


def test_balloon_without_image_reuses_last_valid_image() -> None:
    frame = {
        "image_id": "camilly04.webp",
        "entries": [
            {},
            {"image_id": "camilly05.webp"},
            {},
            {"image_id": ""},
        ],
    }

    base, images = synced.image_sequence_for_frame(frame)

    assert base == "camilly04.webp"
    assert images == (
        "camilly04.webp",
        "camilly05.webp",
        "camilly05.webp",
        "camilly05.webp",
    )


def test_first_balloon_can_inherit_image_from_previous_frame_on_resume() -> None:
    frame = {
        "entries": [
            {},
            {"image_id": "camilly06.webp"},
            {},
        ],
    }

    base, images = synced.image_sequence_for_frame(
        frame,
        inherited_image_id="camilly05.webp",
    )

    assert base == "camilly05.webp"
    assert images == (
        "camilly05.webp",
        "camilly06.webp",
        "camilly06.webp",
    )


def test_mobile_and_desktop_share_same_visible_balloon_sequence(monkeypatch) -> None:
    frame = _frame_from(_base_document())
    frame["image_id"] = "camilly04.webp"
    frame["entries"][1]["image_id"] = "camilly05.webp"
    content = """[QUADRO encontro_004]
[DESCRIÇÃO]
Camilly entra no carro.
[FALA camilly]
Então, como anda a vida?
[PENSAMENTO camilly]
Eu observo a reação dele.
[FALA camilly]
Você ficou me devendo um ensaio.
[/QUADRO]"""

    monkeypatch.setattr(synced, "set_current_frame", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(synced, "reveal_index", lambda _frame_id, count: count)
    monkeypatch.setattr(synced, "_previous_explicit_image_id", lambda _frame_id: "")
    monkeypatch.setattr(synced, "_image_for_id", lambda *_args, **_kwargs: None)

    html = synced._combined_html(
        content,
        character_name="Camilly",
        package_id="roleplay2026.camilly",
        frame=frame,
        legacy_image=None,
    )

    assert html is not None
    assert 'class="sync-mobile-track"' in html
    assert html.count('class="sync-slide"') == 3
    assert 'class="sync-desktop"' in html
    assert html.count('class="sync-dot"') == 3
    assert "data-sync-prev" in html
    assert "data-sync-next" in html


def test_frame_without_explicit_image_id_uses_legacy_renderer(monkeypatch) -> None:
    frame = _frame_from(_base_document())
    content = """[QUADRO encontro_004]
[FALA camilly]
Então, como anda a vida?
[/QUADRO]"""

    monkeypatch.setattr(synced, "set_current_frame", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(synced, "reveal_index", lambda _frame_id, count: count)
    monkeypatch.setattr(synced, "_previous_explicit_image_id", lambda _frame_id: "")

    html = synced._combined_html(
        content,
        character_name="Camilly",
        package_id="roleplay2026.camilly",
        frame=frame,
        legacy_image=None,
    )

    assert html is None
