from __future__ import annotations

from collections.abc import Callable, MutableMapping
from typing import TypeVar


ScriptT = TypeVar("ScriptT")


def script_snapshot_key(user_id: str, package_id: str) -> str:
    return f"editorial:{user_id}:{package_id}:script_snapshot"


def clear_script_snapshot(
    state: MutableMapping[str, object], *, user_id: str, package_id: str
) -> None:
    state.pop(script_snapshot_key(user_id, package_id), None)


def load_script_snapshot(
    state: MutableMapping[str, object],
    *,
    user_id: str,
    package_id: str,
    loader: Callable[[], ScriptT],
    expected_type: type[ScriptT],
    refresh: bool = False,
) -> ScriptT:
    """Lê uma vez por entrada e reutiliza o roteiro nos reruns seguintes."""

    key = script_snapshot_key(user_id, package_id)
    if refresh:
        state.pop(key, None)
    cached = state.get(key)
    if isinstance(cached, expected_type):
        return cached
    loaded = loader()
    state[key] = loaded
    return loaded


__all__ = [
    "clear_script_snapshot",
    "load_script_snapshot",
    "script_snapshot_key",
]
