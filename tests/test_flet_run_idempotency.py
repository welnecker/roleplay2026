from __future__ import annotations

from types import SimpleNamespace

from flet_api.runs import _is_idempotent_duplicate_advance


def _script() -> SimpleNamespace:
    return SimpleNamespace(
        first_beat_id="encontro_001",
        endings={},
        beats={
            "encontro_001": {"on_user": {"engaged": "encontro_002"}},
            "encontro_002": {"on_user": {"engaged": "encontro_003"}},
            "encontro_003": {"on_user": {}},
        },
    )


def test_clique_duplicado_do_quadro_anterior_adota_quadro_ja_persistido() -> None:
    assert _is_idempotent_duplicate_advance(
        _script(),
        expected_frame_id="encontro_001",
        current_movement_id="encontro_002",
    )


def test_quadro_distante_nao_e_tratado_como_clique_duplicado() -> None:
    assert not _is_idempotent_duplicate_advance(
        _script(),
        expected_frame_id="encontro_001",
        current_movement_id="encontro_003",
    )
