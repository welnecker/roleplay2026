from __future__ import annotations


class RuntimeConflictError(RuntimeError):
    """Estado persistido mudou ou um recurso já foi consumido por outra operação."""
