import json

from services import editorial_content


class _ScriptRepository:
    def load_active_story_lines(self, package_id: str):
        assert package_id == "roleplay2026.casada_frustrada"
        return "2026.08", [
            {
                "line_id": "encontro_001_descricao",
                "order": 1,
                "instruction": "[DESCRIÇÃO] Mary entra na sala.",
                "status": "active",
                "image_id": "mary1.webp",
            },
            {
                "line_id": "encontro_001_fala",
                "order": 2,
                "instruction": "[FALA mary] Olá.",
                "status": "active",
                "image_id": "mary2.webp",
            },
        ]


class _Manifest:
    package_id = "roleplay2026.casada_frustrada"


class _Package:
    manifest = _Manifest()


def test_api_sem_patches_streamlit_compila_descricao_v2(monkeypatch) -> None:
    monkeypatch.setattr(
        editorial_content,
        "build_runtime_script_repository",
        lambda _secrets: _ScriptRepository(),
    )
    monkeypatch.setattr(
        editorial_content,
        "load_editorial_document",
        lambda _package: {
            "script_version": "base",
            "character": {"name": "Mary"},
            "blocks": [],
        },
    )

    document = editorial_content.load_effective_editorial_document({}, _Package())

    assert document["authoring_source"] == "spreadsheet_novel_frame_v2"
    assert document["blocks"][0]["entry_beat_id"] == "encontro_001"
    movement = document["blocks"][0]["beats"][0]["required_movement"]
    frame = json.loads(movement.removeprefix("NOVEL_FRAME_V2\n"))
    assert frame["image_id"] == "mary1.webp"
    assert frame["entries"][0]["image_id"] == "mary2.webp"
