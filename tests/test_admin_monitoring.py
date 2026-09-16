from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from flet_api.admin_monitoring import install


def test_monitoring_dashboard_requires_configured_token(monkeypatch) -> None:
    monkeypatch.delenv("OBSERVABILITY_ADMIN_TOKEN", raising=False)
    app = install(FastAPI())
    client = TestClient(app)

    assert client.get("/admin/monitoramento").status_code == 200
    response = client.get("/api/v1/admin/monitoring/summary")
    assert response.status_code == 503


def test_monitoring_dashboard_rejects_invalid_token(monkeypatch) -> None:
    monkeypatch.setenv("OBSERVABILITY_ADMIN_TOKEN", "monitoramento-seguro")
    app = install(FastAPI())
    client = TestClient(app)

    response = client.get(
        "/api/v1/admin/monitoring/summary",
        headers={"X-Observability-Token": "errado"},
    )
    assert response.status_code == 401


def test_monitoring_dashboard_is_idempotent(monkeypatch) -> None:
    monkeypatch.setenv("OBSERVABILITY_ADMIN_TOKEN", "monitoramento-seguro")
    app = FastAPI()
    assert install(install(app)) is app
    assert app.state.admin_monitoring_installed is True


def test_master_reset_requires_explicit_confirmation(monkeypatch) -> None:
    monkeypatch.setenv("OBSERVABILITY_ADMIN_TOKEN", "monitoramento-seguro")
    app = install(FastAPI())
    client = TestClient(app)

    response = client.post(
        "/api/v1/admin/monitoring/reset-master",
        headers={"X-Observability-Token": "monitoramento-seguro"},
        json={"confirmation": "errado"},
    )
    assert response.status_code == 400

