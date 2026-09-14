from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from flet_api.observability import install


def test_observability_is_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("OBSERVABILITY_ENABLED", raising=False)
    app = install(FastAPI())
    assert not hasattr(app.state, "observability_metrics")


def test_dashboard_collects_safe_load_test_metrics(monkeypatch) -> None:
    monkeypatch.setenv("OBSERVABILITY_ENABLED", "true")
    monkeypatch.setenv("OBSERVABILITY_ADMIN_TOKEN", "painel-seguro")
    app = FastAPI()

    @app.get("/ok")
    def ok() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(install(app))
    response = client.get(
        "/ok",
        headers={"X-Load-Test-ID": "load-001", "X-Virtual-User-ID": "user-007"},
    )
    denied = client.get("/api/v1/admin/observability/metrics")
    metrics = client.get(
        "/api/v1/admin/observability/metrics",
        headers={"X-Observability-Token": "painel-seguro"},
    )

    assert response.status_code == 200
    assert denied.status_code == 401
    assert metrics.status_code == 200
    payload = metrics.json()
    route = next(item for item in payload["routes"] if item["route"] == "GET /ok")
    assert route["requests"] == 1
    assert payload["tests"]["load-001"] == 1
    assert "painel-seguro" not in metrics.text


def test_errors_are_signalled_without_response_body(monkeypatch) -> None:
    monkeypatch.setenv("OBSERVABILITY_ENABLED", "1")
    monkeypatch.setenv("OBSERVABILITY_ADMIN_TOKEN", "token")
    app = FastAPI()

    @app.get("/failure")
    def failure() -> None:
        from fastapi import HTTPException
        raise HTTPException(status_code=409, detail="conteúdo privado")

    client = TestClient(install(app))
    client.get("/failure", headers={"X-Load-Test-ID": "unsafe id !"})
    payload = client.get(
        "/api/v1/admin/observability/metrics",
        headers={"X-Observability-Token": "token"},
    ).json()

    failure = next(item for item in payload["recent_errors"] if item["route"] == "GET /failure")
    assert failure["status"] == 409
    assert failure["test_id"] == "unsafe_id__"
    assert "conteúdo privado" not in str(payload)


def test_technical_probes_do_not_pollute_load_metrics(monkeypatch) -> None:
    monkeypatch.setenv("OBSERVABILITY_ENABLED", "true")
    monkeypatch.setenv("OBSERVABILITY_ADMIN_TOKEN", "token")
    app = FastAPI()

    @app.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(install(app))
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/favicon.ico").status_code == 404
    assert client.head("/").status_code in {404, 405}
    payload = client.get(
        "/api/v1/admin/observability/metrics",
        headers={"X-Observability-Token": "token"},
    ).json()

    assert payload["requests"] == 0
    assert payload["errors"] == 0
    assert payload["routes"] == []
