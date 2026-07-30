from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from narrative_v2.models import RunCredit, StoryRun
from services import v2_run_starter


@dataclass
class FakeCredits:
    credit: RunCredit | None
    consumed: tuple[str, str] | None = None

    def get_available_credit(self, *, user_id: str, package_id: str) -> RunCredit | None:
        return self.credit

    def consume_credit(self, *, credit_id: str, run_id: str) -> RunCredit:
        self.consumed = (credit_id, run_id)
        assert self.credit is not None
        return RunCredit(
            credit_id=self.credit.credit_id,
            user_id=self.credit.user_id,
            package_id=self.credit.package_id,
            payment_id=self.credit.payment_id,
            status="consumed",
            run_id=run_id,
        )


@dataclass
class FakeRuns:
    active: StoryRun | None = None

    def get_active_run(self, *, user_id: str, package_id: str) -> StoryRun | None:
        return self.active

    def create_run(
        self,
        *,
        credit: RunCredit,
        script_version: str,
        first_block_id: str,
        first_beat_id: str,
    ) -> StoryRun:
        self.active = StoryRun(
            run_id="run_1",
            credit_id=credit.credit_id,
            user_id=credit.user_id,
            package_id=credit.package_id,
            script_version=script_version,
            current_block_id=first_block_id,
            current_beat_id=first_beat_id,
        )
        return self.active


@dataclass
class FakeRepositories:
    credits: FakeCredits
    runs: FakeRuns


def _story_root(tmp_path: Path) -> Path:
    package = tmp_path / "story"
    package.mkdir()
    (package / "manifest.yaml").write_text(
        """format_version: 1
package_id: roleplay2026.test
version: 2.0.0
author:
  id: test
  name: Test
entrypoint: story.yaml
card:
  title: Teste
  subtitle: ''
  description: Teste
  genres: [Drama]
  chapter_label: Capítulo 1
  cover: ''
commerce:
  access: paid
  price_cents: 100
  currency: BRL
""",
        encoding="utf-8",
    )
    (package / "story.yaml").write_text(
        """story:
  title: Teste
  routes:
    main:
      - order: 1
        beat: início
        content: Olá
""",
        encoding="utf-8",
    )
    (package / "blocks.yaml").write_text(
        """blocks:
  - block_id: primeiro
    order: 1
    title: Primeiro
    entry_beat_id: beat_001
""",
        encoding="utf-8",
    )
    return tmp_path


def _mock_editorial_start(monkeypatch) -> None:
    monkeypatch.setattr(
        v2_run_starter,
        "load_editorial_story_start",
        lambda secrets, package_id: ("2.0.0", "primeiro", "beat_001"),
    )


def test_cria_run_e_consume_credit(monkeypatch, tmp_path: Path) -> None:
    credit = RunCredit(
        credit_id="credit_1",
        user_id="user_1",
        package_id="roleplay2026.test",
        payment_id="pay_1",
        status="available",
    )
    repositories = FakeRepositories(FakeCredits(credit), FakeRuns())
    monkeypatch.setattr(
        v2_run_starter,
        "build_v2_narrative_repositories",
        lambda secrets: repositories,
    )
    _mock_editorial_start(monkeypatch)

    run = v2_run_starter.start_v2_run_on_first_message(
        secrets={},
        user_id="user_1",
        package_id="roleplay2026.test",
        installed_stories_root=_story_root(tmp_path),
    )

    assert run is not None
    assert run.script_version == "2.0.0"
    assert run.current_block_id == "primeiro"
    assert run.current_beat_id == "beat_001"
    assert repositories.credits.consumed == ("credit_1", "run_1")


def test_reutiliza_run_ativa_sem_consumir_outro_credito(monkeypatch, tmp_path: Path) -> None:
    active = StoryRun(
        run_id="run_existing",
        credit_id="credit_old",
        user_id="user_1",
        package_id="roleplay2026.test",
        script_version="1.0.0",
        current_block_id="primeiro",
        current_beat_id="beat_001",
    )
    credits = FakeCredits(
        RunCredit(
            credit_id="credit_new",
            user_id="user_1",
            package_id="roleplay2026.test",
            payment_id="pay_2",
            status="available",
        )
    )
    repositories = FakeRepositories(credits, FakeRuns(active))
    monkeypatch.setattr(
        v2_run_starter,
        "build_v2_narrative_repositories",
        lambda secrets: repositories,
    )
    _mock_editorial_start(monkeypatch)

    run = v2_run_starter.start_v2_run_on_first_message(
        secrets={},
        user_id="user_1",
        package_id="roleplay2026.test",
        installed_stories_root=_story_root(tmp_path),
    )

    assert run is active
    assert credits.consumed is None
