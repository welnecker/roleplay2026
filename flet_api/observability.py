from __future__ import annotations

import hmac
import logging
import os
import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from threading import Lock
from time import monotonic, time
from typing import Any

try:
    import resource
except ImportError:  # pragma: no cover - Windows não oferece este módulo.
    resource = None  # type: ignore[assignment]

from fastapi import HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse


_LOGGER = logging.getLogger("roleplay2026.observability")
_SAFE_ID = re.compile(r"[^a-zA-Z0-9._:-]")
_IGNORED_PATHS = {
    "/admin/observabilidade",
    "/api/v1/admin/observability/metrics",
    "/api/v1/health",
    "/favicon.ico",
}


def _enabled() -> bool:
    return str(os.getenv("OBSERVABILITY_ENABLED", "")).strip().casefold() in {
        "1", "true", "yes", "on"
    }


def _clean_header(value: str | None, default: str = "-") -> str:
    clean = _SAFE_ID.sub("_", str(value or "").strip())[:80]
    return clean or default


def _rss_mb() -> float:
    if resource is None:
        return 0.0
    # Linux reports KiB; macOS reports bytes. Production runs on Linux/Render.
    rss = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if rss > 10_000_000:
        rss /= 1024 * 1024
    else:
        rss /= 1024
    return round(rss, 1)


@dataclass
class RouteStats:
    requests: int = 0
    errors: int = 0
    duration_total_ms: float = 0.0
    durations_ms: deque[float] = field(default_factory=lambda: deque(maxlen=2000))
    bytes_in: int = 0
    bytes_out: int = 0

    def snapshot(self, route: str) -> dict[str, Any]:
        ordered = sorted(self.durations_ms)

        def percentile(fraction: float) -> float:
            if not ordered:
                return 0.0
            return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * fraction))]

        return {
            "route": route,
            "requests": self.requests,
            "errors": self.errors,
            "error_rate": round(self.errors / self.requests * 100, 2) if self.requests else 0.0,
            "average_ms": round(self.duration_total_ms / self.requests, 1) if self.requests else 0.0,
            "p95_ms": round(percentile(0.95), 1),
            "p99_ms": round(percentile(0.99), 1),
            "bytes_in": self.bytes_in,
            "bytes_out": self.bytes_out,
        }


class MetricsStore:
    def __init__(self) -> None:
        self.started_at = time()
        self._routes: dict[str, RouteStats] = defaultdict(RouteStats)
        self._tests: dict[str, int] = defaultdict(int)
        self._recent_errors: deque[dict[str, Any]] = deque(maxlen=100)
        self._in_flight = 0
        self._lock = Lock()

    def enter(self) -> int:
        with self._lock:
            self._in_flight += 1
            return self._in_flight

    def record(
        self, *, route: str, test_id: str, virtual_user: str, status_code: int,
        duration_ms: float, bytes_in: int, bytes_out: int,
    ) -> None:
        with self._lock:
            self._in_flight = max(0, self._in_flight - 1)
            stats = self._routes[route]
            stats.requests += 1
            stats.duration_total_ms += duration_ms
            stats.durations_ms.append(duration_ms)
            stats.bytes_in += bytes_in
            stats.bytes_out += bytes_out
            self._tests[test_id] += 1
            if status_code >= 400:
                stats.errors += 1
                self._recent_errors.appendleft({
                    "at": round(time(), 3), "test_id": test_id,
                    "virtual_user": virtual_user, "route": route,
                    "status": status_code, "duration_ms": round(duration_ms, 1),
                })

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            from persistence.sheets_audit import counters_snapshot

            routes = [stats.snapshot(route) for route, stats in self._routes.items()]
            routes.sort(key=lambda item: (-item["requests"], item["route"]))
            requests = sum(item["requests"] for item in routes)
            errors = sum(item["errors"] for item in routes)
            return {
                "uptime_seconds": round(time() - self.started_at, 1),
                "rss_mb": _rss_mb(),
                "in_flight": self._in_flight,
                "requests": requests,
                "errors": errors,
                "error_rate": round(errors / requests * 100, 2) if requests else 0.0,
                "tests": dict(sorted(self._tests.items())),
                "routes": routes,
                "recent_errors": list(self._recent_errors),
                "sheets": counters_snapshot(),
            }


_DASHBOARD = """<!doctype html><html lang=\"pt-BR\"><head><meta charset=\"utf-8\">
<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>Observabilidade — EntreCenas</title>
<style>body{font-family:system-ui;background:#101218;color:#eee;margin:0;padding:24px}main{max-width:1200px;margin:auto}
.bar{display:flex;gap:12px;flex-wrap:wrap}.card{background:#1b1e27;border:1px solid #303543;border-radius:12px;padding:16px;min-width:150px}
.value{font-size:1.7rem;font-weight:700}.ok{color:#62d394}.warn{color:#ffd166}.bad{color:#ff6b6b}table{width:100%;border-collapse:collapse;margin-top:20px}
th,td{text-align:left;padding:9px;border-bottom:1px solid #303543}input,button{padding:10px;border-radius:8px;border:1px solid #555;background:#171a22;color:#fff}small{color:#aeb4c2}</style></head>
<body><main><h1>Painel de observabilidade</h1><p><input id=token type=password placeholder=\"Token do painel\"> <button onclick=\"start()\">Conectar</button> <small id=state>aguardando token</small></p>
<div class=bar id=summary></div><table><thead><tr><th>Rota</th><th>Req.</th><th>Erros</th><th>Média</th><th>p95</th><th>p99</th><th>Tráfego</th></tr></thead><tbody id=routes></tbody></table>
<h2>Google Sheets</h2><table><thead><tr><th>Aba</th><th>Leituras</th><th>Escritas</th><th>Cache hits</th><th>Cache misses</th><th>429</th><th>Fallbacks</th></tr></thead><tbody id=sheets></tbody></table>
<h2>Erros recentes</h2><table><thead><tr><th>Teste</th><th>Usuário virtual</th><th>Rota</th><th>Status</th><th>Tempo</th></tr></thead><tbody id=errors></tbody></table></main>
<script>let timer;const f=n=>new Intl.NumberFormat('pt-BR').format(n), mb=n=>(n/1048576).toFixed(2)+' MB';
async function load(){const token=document.querySelector('#token').value;try{const r=await fetch('/api/v1/admin/observability/metrics',{headers:{'X-Observability-Token':token}});if(!r.ok)throw Error(r.status);const d=await r.json();
state.textContent='atualização a cada 2 segundos';const cls=d.error_rate>=5?'bad':d.error_rate>=1?'warn':'ok';summary.innerHTML=`<div class=card><small>Requisições</small><div class=value>${f(d.requests)}</div></div><div class=card><small>Em andamento</small><div class=value>${d.in_flight}</div></div><div class=card><small>Erros</small><div class=\"value ${cls}\">${d.error_rate}%</div></div><div class=card><small>RAM máxima</small><div class=value>${d.rss_mb} MB</div></div>`;
routes.innerHTML=d.routes.map(x=>`<tr><td>${x.route}</td><td>${f(x.requests)}</td><td>${x.errors} (${x.error_rate}%)</td><td>${x.average_ms} ms</td><td>${x.p95_ms} ms</td><td>${x.p99_ms} ms</td><td>${mb(x.bytes_in+x.bytes_out)}</td></tr>`).join('');
sheets.innerHTML=Object.entries(d.sheets).map(([name,x])=>`<tr><td>${name}</td><td>${x.google_reads||0}</td><td>${x.google_writes||0}</td><td>${x.cache_hits||0}</td><td>${x.cache_misses||0}</td><td class=${(x.quota_429||0)>0?'bad':''}>${x.quota_429||0}</td><td>${x.stale_fallbacks||0}</td></tr>`).join('');
errors.innerHTML=d.recent_errors.map(x=>`<tr><td>${x.test_id}</td><td>${x.virtual_user}</td><td>${x.route}</td><td class=bad>${x.status}</td><td>${x.duration_ms} ms</td></tr>`).join('');}catch(e){state.textContent='acesso recusado ou painel indisponível';clearInterval(timer)}}
function start(){clearInterval(timer);load();timer=setInterval(load,2000)}</script></body></html>"""


def install(app: Any) -> Any:
    if not _enabled() or getattr(app.state, "observability_installed", False):
        return app

    store = MetricsStore()
    app.state.observability_metrics = store

    @app.middleware("http")
    async def observability_middleware(request: Request, call_next: Any) -> Any:
        if request.url.path in _IGNORED_PATHS:
            return await call_next(request)
        started = monotonic()
        test_id = _clean_header(request.headers.get("X-Load-Test-ID"), "ordinary")
        virtual_user = _clean_header(request.headers.get("X-Virtual-User-ID"))
        route = f"{request.method} {request.url.path}"
        bytes_in = int(request.headers.get("content-length", "0") or 0)
        store.enter()
        response = None
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration_ms = max(0.0, (monotonic() - started) * 1000)
            bytes_out = int(response.headers.get("content-length", "0") or 0) if response else 0
            store.record(route=route, test_id=test_id, virtual_user=virtual_user,
                         status_code=status_code, duration_ms=duration_ms,
                         bytes_in=bytes_in, bytes_out=bytes_out)
            _LOGGER.warning(
                "[TRAFFIC_AUDIT] test=%s virtual_user=%s route=%s status=%d duration_ms=%.1f bytes_in=%d bytes_out=%d",
                test_id, virtual_user, route, status_code, duration_ms, bytes_in, bytes_out,
            )

    def authorize(request: Request) -> None:
        expected = str(os.getenv("OBSERVABILITY_ADMIN_TOKEN", ""))
        supplied = str(request.headers.get("X-Observability-Token", ""))
        if not expected:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                                detail="Token do painel não configurado.")
        if not hmac.compare_digest(expected, supplied):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autorizado.")

    @app.get("/admin/observabilidade", response_class=HTMLResponse, include_in_schema=False)
    async def dashboard() -> HTMLResponse:
        return HTMLResponse(_DASHBOARD, headers={"Cache-Control": "no-store"})

    @app.get("/api/v1/admin/observability/metrics", include_in_schema=False)
    async def metrics(request: Request) -> JSONResponse:
        authorize(request)
        return JSONResponse(store.snapshot(), headers={"Cache-Control": "no-store"})

    app.state.observability_installed = True
    _LOGGER.warning("[TRAFFIC_AUDIT] enabled=true sensitive_payloads=false")
    return app
