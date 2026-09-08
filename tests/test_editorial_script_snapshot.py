from __future__ import annotations

from services.editorial_script_snapshot import (
    clear_script_snapshot,
    load_script_snapshot,
)


class _Script:
    pass


def test_reruns_reutilizam_um_unico_carregamento() -> None:
    state: dict[str, object] = {}
    calls = 0

    def loader() -> _Script:
        nonlocal calls
        calls += 1
        return _Script()

    snapshots = [
        load_script_snapshot(
            state,
            user_id="user-1",
            package_id="roleplay2026.camilly",
            loader=loader,
            expected_type=_Script,
        )
        for _ in range(100)
    ]

    assert calls == 1
    assert all(item is snapshots[0] for item in snapshots)


def test_saida_e_reentrada_forcam_nova_leitura() -> None:
    state: dict[str, object] = {}
    calls = 0

    def loader() -> _Script:
        nonlocal calls
        calls += 1
        return _Script()

    first = load_script_snapshot(
        state,
        user_id="user-1",
        package_id="roleplay2026.camilly",
        loader=loader,
        expected_type=_Script,
    )
    clear_script_snapshot(
        state, user_id="user-1", package_id="roleplay2026.camilly"
    )
    second = load_script_snapshot(
        state,
        user_id="user-1",
        package_id="roleplay2026.camilly",
        loader=loader,
        expected_type=_Script,
    )

    assert calls == 2
    assert second is not first


def test_novo_pagamento_forca_atualizacao_sem_afetar_outro_usuario() -> None:
    state: dict[str, object] = {}
    calls = 0

    def loader() -> _Script:
        nonlocal calls
        calls += 1
        return _Script()

    first = load_script_snapshot(
        state,
        user_id="user-1",
        package_id="roleplay2026.camilly",
        loader=loader,
        expected_type=_Script,
    )
    other = load_script_snapshot(
        state,
        user_id="user-2",
        package_id="roleplay2026.camilly",
        loader=loader,
        expected_type=_Script,
    )
    refreshed = load_script_snapshot(
        state,
        user_id="user-1",
        package_id="roleplay2026.camilly",
        loader=loader,
        expected_type=_Script,
        refresh=True,
    )

    assert calls == 3
    assert refreshed is not first
    assert other is state["editorial:user-2:roleplay2026.camilly:script_snapshot"]
