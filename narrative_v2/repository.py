from __future__ import annotations

from typing import Protocol

from narrative_v2.models import RunCredit, StoryRun


class RuntimeConflictError(RuntimeError):
    pass


class StoryCreditRepository(Protocol):
    """Persistência de créditos adquiridos por pagamento."""

    def create_credit(
        self,
        *,
        user_id: str,
        package_id: str,
        payment_id: str,
    ) -> RunCredit: ...

    def get_available_credit(
        self,
        *,
        user_id: str,
        package_id: str,
    ) -> RunCredit | None: ...

    def consume_credit(
        self,
        *,
        credit_id: str,
        run_id: str,
    ) -> RunCredit: ...


class StoryRunRepository(Protocol):
    """Persistência de execuções finitas de cards narrativos."""

    def create_run(
        self,
        *,
        credit: RunCredit,
        script_version: str,
        first_block_id: str,
        first_beat_id: str,
    ) -> StoryRun: ...

    def get_active_run(
        self,
        *,
        user_id: str,
        package_id: str,
    ) -> StoryRun | None: ...

    def update_run(
        self,
        *,
        run: StoryRun,
        expected_version: int,
    ) -> StoryRun: ...

    def append_run_memory(
        self,
        *,
        run_id: str,
        memory_id: str,
        source_beat_id: str,
    ) -> None: ...


class NarrativeInteractionRepository(Protocol):
    """Histórico recente e auditoria de cada beat interpretado."""

    def append_interaction(
        self,
        *,
        run_id: str,
        user_id: str,
        package_id: str,
        sequence: int,
        role: str,
        content: str,
        block_id: str,
        beat_id: str,
        speaker_id: str,
        user_intent: str = "",
        beat_consumed: bool = False,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> None: ...

    def list_recent_interactions(
        self,
        *,
        run_id: str,
        limit: int = 6,
    ) -> list[dict[str, object]]: ...
