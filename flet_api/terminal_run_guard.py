from __future__ import annotations

"""Curto-circuita chamadas repetidas depois de um quadro terminal já conhecido.

O estado durável continua sendo STORY_RUNS/INTERACTIONS. Este cache existe apenas
como defesa de processo para clientes antigos, cliques duplicados ou latência:
depois que a API já devolveu ``finished=True`` para um quadro, novos ``reveal`` ou
``advance`` desse mesmo quadro não precisam reabrir o runtime nem consultar Google
Sheets.
"""

from functools import wraps
from threading import Lock
from typing import Any

from flet_api.runs import FletRunService, RunFrame


_INSTALLED = False
_CACHE: dict[tuple[str, str, str], RunFrame] = {}
_CACHE_LOCK = Lock()


def _key(user_id: str, package_id: str, frame_id: str) -> tuple[str, str, str]:
    return (
        str(user_id or "").strip(),
        str(package_id or "").strip(),
        str(frame_id or "").strip(),
    )


def _remember(user_id: str, frame: RunFrame) -> None:
    if not frame.finished:
        return
    key = _key(user_id, frame.package_id, frame.frame_id)
    if not all(key):
        return
    with _CACHE_LOCK:
        _CACHE[key] = frame


def _cached(user_id: str, package_id: str, frame_id: str) -> RunFrame | None:
    with _CACHE_LOCK:
        return _CACHE.get(_key(user_id, package_id, frame_id))


def _clear_story(user_id: str, package_id: str) -> None:
    prefix = (str(user_id or "").strip(), str(package_id or "").strip())
    with _CACHE_LOCK:
        stale = [key for key in _CACHE if key[:2] == prefix]
        for key in stale:
            _CACHE.pop(key, None)


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    cls = FletRunService
    original_open = cls.open
    original_advance = cls.advance
    original_reveal = cls.reveal
    if getattr(original_advance, "_terminal_run_guard", False):
        _INSTALLED = True
        return

    @wraps(original_open)
    def open_run(self: Any, *, account: Any, package_id: str) -> RunFrame:
        frame = original_open(self, account=account, package_id=package_id)
        if frame.finished:
            _remember(account.user_id, frame)
        else:
            # Uma nova run/replay da mesma história invalida qualquer terminal
            # lembrado do processo anterior para esse usuário/pacote.
            _clear_story(account.user_id, package_id)
        return frame

    @wraps(original_reveal)
    def reveal_run(
        self: Any,
        *,
        account: Any,
        package_id: str,
        expected_frame_id: str,
    ) -> RunFrame:
        terminal = _cached(account.user_id, package_id, expected_frame_id)
        if terminal is not None:
            return terminal
        frame = original_reveal(
            self,
            account=account,
            package_id=package_id,
            expected_frame_id=expected_frame_id,
        )
        _remember(account.user_id, frame)
        return frame

    @wraps(original_advance)
    def advance_run(
        self: Any,
        *,
        account: Any,
        package_id: str,
        expected_frame_id: str,
        revealed_entries: int,
    ) -> RunFrame:
        terminal = _cached(account.user_id, package_id, expected_frame_id)
        if terminal is not None:
            return terminal
        frame = original_advance(
            self,
            account=account,
            package_id=package_id,
            expected_frame_id=expected_frame_id,
            revealed_entries=revealed_entries,
        )
        _remember(account.user_id, frame)
        return frame

    setattr(advance_run, "_terminal_run_guard", True)
    cls.open = open_run
    cls.advance = advance_run
    cls.reveal = reveal_run
    _INSTALLED = True


__all__ = ["install"]
