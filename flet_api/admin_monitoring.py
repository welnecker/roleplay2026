from __future__ import annotations

import hmac
import os
from datetime import datetime
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from persistence.backend_config import POSTGRES_BACKEND, operational_backend
from persistence.postgres_database import PostgresDatabase, shared_postgres_database
from services.secret_loader import load_application_secrets


_HTML = r"""<!doctype html>
<html lang="pt-BR">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Monitoramento — Entre Cenas</title>
<style>
body{font-family:system-ui;background:#101218;color:#eee;margin:0;padding:24px}
main{max-width:1500px;margin:auto}.toolbar{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
input,button{padding:10px;border-radius:8px;border:1px solid #555;background:#171a22;color:#fff}
button{cursor:pointer}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:18px 0}
.card{background:#1b1e27;border:1px solid #303543;border-radius:12px;padding:14px}.value{font-size:1.55rem;font-weight:700}
small{color:#aeb4c2}.status{margin-left:8px}.ok{color:#62d394}.bad{color:#ff6b6b}.warn{color:#ffd166}
section{background:#171a22;border:1px solid #303543;border-radius:12px;padding:16px;margin-top:18px;overflow:auto}
table{width:100%;border-collapse:collapse;min-width:900px}th,td{text-align:left;padding:8px;border-bottom:1px solid #303543;vertical-align:top}
th{color:#aeb4c2;font-size:.85rem}.run{cursor:pointer}.run:hover{background:#232735}pre{white-space:pre-wrap;max-width:560px;margin:0;font:inherit}
</style></head>
<body><main>
<h1>Painel de monitoramento</h1>
<div class="toolbar"><input id="token" type="password" placeholder="Token administrativo" size="28">
<input id="filter" placeholder="E-mail, user_id, run_id ou package_id" size="36">
<button onclick="loadAll()">Atualizar</button><span id="state"><small>aguardando autenticação</small></span></div>
<div class="grid" id="summary"></div>
<section><h2>Usuários</h2><table><thead><tr><th>ID</th><th>E-mail</th><th>Nome</th><th>Status</th><th>Cadastro</th><th>Runs</th><th>Interações</th></tr></thead><tbody id="users"></tbody></table></section>
<section><h2>Runs</h2><small>Clique em uma run para carregar as interações.</small><table><thead><tr><th>Run</th><th>Usuário</th><th>Card</th><th>Versão</th><th>Status</th><th>Quadro atual</th><th>Interações</th><th>Atualizada</th></tr></thead><tbody id="runs"></tbody></table></section>
<section><h2>Interações da run selecionada</h2><div id="selected"><small>Nenhuma run selecionada.</small></div><table><thead><tr><th>Seq.</th><th>Role</th><th>Speaker</th><th>Beat</th><th>Modelo</th><th>Latência</th><th>Conteúdo</th><th>Criada</th></tr></thead><tbody id="interactions"></tbody></table></section>
</main>
<script>
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const token=()=>document.querySelector('#token').value;
async function api(path){const r=await fetch(path,{headers:{'X-Observability-Token':token()}});const d=await r.json().catch(()=>({detail:r.statusText}));if(!r.ok)throw Error(d.detail||r.status);return d}
function query(){return encodeURIComponent(document.querySelector('#filter').value.trim())}
async function loadAll(){try{state.textContent='carregando…';const [s,u,r]=await Promise.all([api('/api/v1/admin/monitoring/summary'),api('/api/v1/admin/monitoring/users?q='+query()),api('/api/v1/admin/monitoring/runs?q='+query())]);
summary.innerHTML=Object.entries(s).filter(([k])=>k!=='backend').map(([k,v])=>`<div class="card"><small>${esc(k)}</small><div class="value">${esc(v)}</div></div>`).join('');
users.innerHTML=u.items.map(x=>`<tr><td>${esc(x.user_id)}</td><td>${esc(x.email)}</td><td>${esc(x.display_name)}</td><td>${esc(x.status)}</td><td>${esc(x.created_at)}</td><td>${esc(x.runs)}</td><td>${esc(x.interactions)}</td></tr>`).join('');
runs.innerHTML=r.items.map(x=>`<tr class="run" onclick="loadInteractions('${encodeURIComponent(x.run_id)}')"><td>${esc(x.run_id)}</td><td>${esc(x.email)}</td><td>${esc(x.package_id)}</td><td>${esc(x.script_version)}</td><td>${esc(x.status)}</td><td>${esc(x.current_beat_id)}</td><td>${esc(x.interactions)}</td><td>${esc(x.updated_at)}</td></tr>`).join('');state.innerHTML='<span class="ok">conectado · backend '+esc(s.backend)+'</span>';
}catch(e){state.innerHTML='<span class="bad">'+esc(e.message)+'</span>'}}
async function loadInteractions(id){try{const run=decodeURIComponent(id);const d=await api('/api/v1/admin/monitoring/runs/'+encodeURIComponent(run)+'/interactions');selected.innerHTML='<small>run_id: '+esc(run)+'</small>';interactions.innerHTML=d.items.map(x=>`<tr><td>${esc(x.sequence)}</td><td>${esc(x.role)}</td><td>${esc(x.speaker_id)}</td><td>${esc(x.beat_id)}</td><td>${esc(x.model)}</td><td>${esc(x.latency_ms)} ms</td><td><pre>${esc(x.content)}</pre></td><td>${esc(x.created_at)}</td></tr>`).join('')}catch(e){selected.innerHTML='<span class="bad">'+esc(e.message)+'</span>'}}
</script></body></html>"""


def _authorize(request: Request) -> None:
    expected = str(os.getenv("OBSERVABILITY_ADMIN_TOKEN", "") or "")
    supplied = str(request.headers.get("X-Observability-Token", "") or "")
    if not expected:
        raise HTTPException(status_code=503, detail="Token administrativo não configurado.")
    if not hmac.compare_digest(expected, supplied):
        raise HTTPException(status_code=401, detail="Não autorizado.")


def _database() -> PostgresDatabase:
    secrets = load_application_secrets()
    if operational_backend(secrets) != POSTGRES_BACKEND:
        raise HTTPException(
            status_code=503,
            detail="O monitoramento operacional requer PERSISTENCE_BACKEND=postgres.",
        )
    return shared_postgres_database(secrets)


def _iso(value: object) -> str:
    return value.isoformat() if isinstance(value, datetime) else str(value or "")


def _limit(value: int) -> int:
    return max(1, min(int(value), 200))


def install(app: Any) -> Any:
    if getattr(app.state, "admin_monitoring_installed", False):
        return app

    @app.get("/admin/monitoramento", response_class=HTMLResponse, include_in_schema=False)
    async def dashboard() -> HTMLResponse:
        return HTMLResponse(_HTML, headers={"Cache-Control": "no-store"})

    @app.get("/api/v1/admin/monitoring/summary", include_in_schema=False)
    async def summary(request: Request) -> JSONResponse:
        _authorize(request)
        database = _database()
        with database.pool.connection() as connection:
            row = connection.execute(
                """
                SELECT
                  (SELECT count(*) FROM users),
                  (SELECT count(*) FROM users WHERE status = 'active'),
                  (SELECT count(*) FROM story_runs),
                  (SELECT count(*) FROM story_runs WHERE status = 'active'),
                  (SELECT count(*) FROM interactions),
                  (SELECT count(*) FROM runtime_sessions WHERE status = 'active'),
                  (SELECT count(*) FROM story_credits WHERE status = 'available'),
                  (SELECT count(*) FROM payment_orders WHERE payment_mode = 'test_master'),
                  (SELECT count(*) FROM payment_orders WHERE status = 'approved')
                """
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=503, detail="Não foi possível consultar o banco.")
        return JSONResponse({
            "backend": "postgres",
            "usuários": int(row[0]), "usuários ativos": int(row[1]),
            "runs": int(row[2]), "runs ativas": int(row[3]),
            "interações": int(row[4]), "sessões ativas": int(row[5]),
            "créditos disponíveis": int(row[6]), "pagamentos master": int(row[7]),
            "pagamentos aprovados": int(row[8]),
        })

    @app.get("/api/v1/admin/monitoring/users", include_in_schema=False)
    async def users(request: Request, q: str = "", limit: int = 100) -> JSONResponse:
        _authorize(request)
        database = _database()
        clean = str(q or "").strip()
        pattern = f"%{clean}%"
        with database.pool.connection() as connection:
            rows = connection.execute(
                """
                SELECT u.user_id, u.email, u.display_name, u.status, u.created_at,
                       count(DISTINCT sr.run_id), count(DISTINCT i.interaction_id)
                FROM users u
                LEFT JOIN story_runs sr ON sr.user_id = u.user_id
                LEFT JOIN interactions i ON i.user_id = u.user_id
                WHERE (%s = '' OR u.email ILIKE %s OR u.display_name ILIKE %s OR u.user_id = %s)
                GROUP BY u.user_id, u.email, u.display_name, u.status, u.created_at
                ORDER BY u.created_at DESC LIMIT %s
                """,
                (clean, pattern, pattern, clean, _limit(limit)),
            ).fetchall()
        return JSONResponse({"items": [
            {"user_id": str(r[0]), "email": str(r[1]), "display_name": str(r[2]),
             "status": str(r[3]), "created_at": _iso(r[4]), "runs": int(r[5]),
             "interactions": int(r[6])} for r in rows
        ]})

    @app.get("/api/v1/admin/monitoring/runs", include_in_schema=False)
    async def runs(request: Request, q: str = "", limit: int = 100) -> JSONResponse:
        _authorize(request)
        database = _database()
        clean = str(q or "").strip()
        pattern = f"%{clean}%"
        with database.pool.connection() as connection:
            rows = connection.execute(
                """
                SELECT sr.run_id, sr.user_id, u.email, sr.package_id, sr.script_version,
                       sr.current_block_id, sr.current_beat_id, sr.status, sr.ending_code,
                       sr.state_version, sr.started_at, sr.ended_at, sr.updated_at,
                       count(i.interaction_id)
                FROM story_runs sr
                JOIN users u ON u.user_id = sr.user_id
                LEFT JOIN interactions i ON i.run_id = sr.run_id
                WHERE (%s = '' OR u.email ILIKE %s OR u.user_id = %s
                       OR sr.package_id ILIKE %s OR sr.run_id = %s)
                GROUP BY sr.run_id, sr.user_id, u.email, sr.package_id, sr.script_version,
                         sr.current_block_id, sr.current_beat_id, sr.status, sr.ending_code,
                         sr.state_version, sr.started_at, sr.ended_at, sr.updated_at
                ORDER BY sr.updated_at DESC LIMIT %s
                """,
                (clean, pattern, clean, pattern, clean, _limit(limit)),
            ).fetchall()
        return JSONResponse({"items": [
            {"run_id": str(r[0]), "user_id": str(r[1]), "email": str(r[2]),
             "package_id": str(r[3]), "script_version": str(r[4]),
             "current_block_id": str(r[5]), "current_beat_id": str(r[6]),
             "status": str(r[7]), "ending_code": str(r[8]), "state_version": int(r[9]),
             "started_at": _iso(r[10]), "ended_at": _iso(r[11]),
             "updated_at": _iso(r[12]), "interactions": int(r[13])} for r in rows
        ]})

    @app.get("/api/v1/admin/monitoring/runs/{run_id}/interactions", include_in_schema=False)
    async def run_interactions(request: Request, run_id: str, limit: int = 200) -> JSONResponse:
        _authorize(request)
        database = _database()
        with database.pool.connection() as connection:
            rows = connection.execute(
                """
                SELECT interaction_id, session_id, run_id, user_id, package_id, sequence,
                       role, speaker_id, content, block_id, beat_id, user_intent,
                       beat_consumed, model, input_tokens, output_tokens, latency_ms,
                       created_at
                FROM interactions WHERE run_id = %s
                ORDER BY sequence ASC, role ASC LIMIT %s
                """,
                (run_id.strip(), _limit(limit)),
            ).fetchall()
        return JSONResponse({"items": [
            {"interaction_id": str(r[0]), "session_id": str(r[1]), "run_id": str(r[2]),
             "user_id": str(r[3]), "package_id": str(r[4]), "sequence": int(r[5]),
             "role": str(r[6]), "speaker_id": str(r[7]), "content": str(r[8]),
             "block_id": str(r[9]), "beat_id": str(r[10]), "user_intent": str(r[11]),
             "beat_consumed": bool(r[12]), "model": str(r[13]), "input_tokens": int(r[14]),
             "output_tokens": int(r[15]), "latency_ms": int(r[16]), "created_at": _iso(r[17])}
            for r in rows
        ]})

    app.state.admin_monitoring_installed = True
    return app


__all__ = ["install"]

