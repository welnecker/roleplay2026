# Teste mínimo de carga e observabilidade

## Ativar no Render

Configure duas variáveis no serviço do app online e faça o deploy:

```text
OBSERVABILITY_ENABLED=true
OBSERVABILITY_ADMIN_TOKEN=<senha longa e exclusiva>
```

O painel ficará em `/admin/observabilidade`. A senha é pedida no navegador e enviada
somente no cabeçalho das consultas de métricas. Conteúdo narrativo, credenciais e tokens
de sessão não são coletados.

## Executar localmente

```powershell
py -m pip install -r requirements-load.txt
$env:LOAD_TEST_ID = "load-001"
$env:LOAD_TEST_PACKAGE_ID = "roleplay2026.degustacao"
py -m locust -f tests/load/locustfile.py --host https://entrecenas-roleplay.com.br
```

Abra `http://localhost:8089`, comece com 1 usuário e depois teste 5, 10 e 20.
Cada usuário virtual cria uma conta descartável, abre a degustação, revela as falas,
avança os quadros e consulta o catálogo. Não cria cobranças Pix.

As chamadas carregam `X-Load-Test-ID` e `X-Virtual-User-ID`. Esses identificadores
aparecem no painel e em linhas `[TRAFFIC_AUDIT]` dos logs do Render, permitindo cruzar
uma falha do Locust com o processamento interno do backend.

Sondagens técnicas (`/api/v1/health`), o próprio painel e pedidos automáticos de
`/favicon.ico` ou `HEAD` não entram nas estatísticas da carga.
