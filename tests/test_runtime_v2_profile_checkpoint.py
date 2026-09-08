from __future__ import annotations

import json
from types import SimpleNamespace

from persistence.runtime_v2 import GoogleSheetsV2RuntimeRepository


class FakeTable:
    def __init__(self) -> None:
        self.replacements: list[tuple[int, dict[str, object]]] = []

    def find(self, column: str, value: str):
        assert column == "interaction_id"
        assert value == "interaction_1"
        return 7, {}

    def replace(self, row_number: int, row: dict[str, object]) -> None:
        self.replacements.append((row_number, row))


def test_perfil_e_anexado_ao_ultimo_quadro_da_run() -> None:
    repository = object.__new__(GoogleSheetsV2RuntimeRepository)
    table = FakeTable()
    repository.interactions = SimpleNamespace(table=table)
    repository._interaction_rows_for_owner = lambda **_kwargs: [  # type: ignore[method-assign]
        {
            "interaction_id": "interaction_1",
            "sequence": 3,
            "role": "assistant",
            "metadata_json": '{"novel_frame":true}',
        }
    ]

    repository.persist_run_profile(
        run_id="run_1",
        user_id="user_1",
        package_id="story_1",
        profile={
            "preferred_name": "Janio",
            "story_gender": "Como homem",
        },
    )

    assert table.replacements[0][0] == 7
    metadata = json.loads(str(table.replacements[0][1]["metadata_json"]))
    assert metadata["novel_frame"] is True
    assert metadata["immersive_profile"] == {
        "preferred_name": "Janio",
        "story_gender": "Como homem",
    }


def test_perfil_ja_persistido_nao_e_sobrescrito() -> None:
    repository = object.__new__(GoogleSheetsV2RuntimeRepository)
    table = FakeTable()
    repository.interactions = SimpleNamespace(table=table)
    repository._interaction_rows_for_owner = lambda **_kwargs: [  # type: ignore[method-assign]
        {
            "interaction_id": "interaction_1",
            "sequence": 3,
            "role": "assistant",
            "metadata_json": (
                '{"immersive_profile":{"preferred_name":"Ana",'
                '"story_gender":"Como mulher"}}'
            ),
        }
    ]

    repository.persist_run_profile(
        run_id="run_1",
        user_id="user_1",
        package_id="story_1",
        profile={
            "preferred_name": "Outro nome",
            "story_gender": "De forma neutra",
        },
    )

    assert table.replacements == []
