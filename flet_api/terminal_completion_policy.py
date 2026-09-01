from __future__ import annotations

"""Conclui a run somente depois da última revelação do quadro terminal.

O quadro final precisa continuar pertencendo a uma run ``active`` enquanto seus
balões/pensamentos ainda estão sendo revelados. A geração do quadro pode saber que
não existe próximo movimento, mas isso não significa que a experiência visual já
acabou.

Esta política preserva o fluxo atual de FletRunService e apenas separa dois
conceitos que antes estavam acoplados:

* ``movement.is_ending``: o quadro gerado é o último do roteiro;
* ``state.finished`` / ``STORY_RUNS.completed``: o usuário terminou de revelar o
  último quadro.

A instalação é feita antes dos guards de terminalidade em ``flet_api.asgi``.
"""

from contextvars import ContextVar
from dataclasses import replace
from functools import wraps
from typing import Any

import flet_api.runs as runs_module
from flet_api.runs import FletRunService, RunFrame
from services.editorial_content import load_editorial_package, require_editorial_package
from services.novel_frame_runtime_support import first_frame_movement
from services.novel_v2_adapter import movement_from_script
from services.paid_run_access import finish_active_run


_INSTALLED = False
_DEFER_TERMINAL_COMPLETION: ContextVar[bool] = ContextVar(
    "flet_defer_terminal_completion",
    default=False,
)


def _generation_is_terminal(script: Any, target_id: str) -> bool:
    movement = (
        first_frame_movement(script)[1]
        if not str(target_id or "").strip()
        else movement_from_script(script, target_id)
    )
    return bool(getattr(movement, "is_ending", False))


def _frame_is_terminal(service: Any, package_id: str, frame_id: str) -> bool:
    package = require_editorial_package(package_id)
    script = load_editorial_package(service.secrets, package)
    try:
        movement = movement_from_script(script, frame_id)
    except (KeyError, TypeError, ValueError):
        return False
    return bool(getattr(movement, "is_ending", False))


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    cls = FletRunService
    original_generate = cls._generate
    original_reveal = cls.reveal
    original_persist = runs_module.persist_assistant_message
    original_finish = runs_module.finish_active_run

    if getattr(original_generate, "_terminal_completion_policy", False):
        _INSTALLED = True
        return

    @wraps(original_persist)
    def persist_assistant_message(*args: Any, **kwargs: Any):
        if not _DEFER_TERMINAL_COMPLETION.get():
            return original_persist(*args, **kwargs)

        state = kwargs.get("state")
        if state is None:
            return original_persist(*args, **kwargs)
        persisted_state = state.copy()
        persisted_state.finished = False
        kwargs["state"] = persisted_state
        return original_persist(*args, **kwargs)

    @wraps(original_finish)
    def deferred_finish_active_run(*args: Any, **kwargs: Any):
        if _DEFER_TERMINAL_COMPLETION.get():
            return None
        return original_finish(*args, **kwargs)

    @wraps(original_generate)
    def generate(self: Any, **kwargs: Any):
        terminal = _generation_is_terminal(kwargs["script"], str(kwargs.get("target_id", "")))
        token = _DEFER_TERMINAL_COMPLETION.set(terminal)
        try:
            context, state, messages = original_generate(self, **kwargs)
        finally:
            _DEFER_TERMINAL_COMPLETION.reset(token)

        if terminal:
            # O quadro é terminal, mas a experiência ainda não terminou: ainda
            # existem entries a revelar. Persistência e resposta permanecem ativas.
            state.finished = False
        return context, state, messages

    @wraps(original_reveal)
    def reveal(
        self: Any,
        *,
        account: Any,
        package_id: str,
        expected_frame_id: str,
    ) -> RunFrame:
        frame = original_reveal(
            self,
            account=account,
            package_id=package_id,
            expected_frame_id=expected_frame_id,
        )
        fully_revealed = frame.entry_count <= 0 or frame.revealed_entries >= frame.entry_count
        if not fully_revealed or not _frame_is_terminal(self, package_id, expected_frame_id):
            return frame

        # Somente a última revelação do último quadro consome a terminalidade.
        finish_active_run(
            secrets=self.secrets,
            user_id=account.user_id,
            package_id=package_id,
            status="completed",
            ending_code="normal_completion",
        )
        return replace(frame, finished=True)

    setattr(generate, "_terminal_completion_policy", True)
    runs_module.persist_assistant_message = persist_assistant_message
    runs_module.finish_active_run = deferred_finish_active_run
    cls._generate = generate
    cls.reveal = reveal
    _INSTALLED = True


__all__ = ["install", "_frame_is_terminal", "_generation_is_terminal"]
