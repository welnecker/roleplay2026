from __future__ import annotations

from flet_api import terminal_completion_policy as policy


def test_politica_legada_nao_sobrescreve_o_fechamento_nativo(monkeypatch) -> None:
    original_generate = policy.FletRunService._generate
    original_reveal = policy.FletRunService.reveal
    original_persist = policy.runs_module.persist_assistant_message

    monkeypatch.setattr(policy, "_INSTALLED", False)
    policy.install()

    assert policy._INSTALLED is True
    assert callable(getattr(policy.FletRunService, "_finish_loaded_run", None))
    assert policy.FletRunService._generate is original_generate
    assert policy.FletRunService.reveal is original_reveal
    assert policy.runs_module.persist_assistant_message is original_persist
    assert not hasattr(policy.runs_module, "finish_active_run")
