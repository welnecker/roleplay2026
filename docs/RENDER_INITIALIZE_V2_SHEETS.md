# Inicialização das planilhas v2 pelo Render

O serviço FastAPI expõe temporariamente o endpoint administrativo:

```text
POST /admin/initialize-v2-sheets
```

## Variáveis de ambiente necessárias

Configure no serviço Render:

- `ROLEPLAY_ACCOUNTS_BILLING_SPREADSHEET_ID`
- `ROLEPLAY_RUNTIME_SPREADSHEET_ID`
- `ROLEPLAY_EDITORIAL_SPREADSHEET_ID`
- `V2_SHEETS_ADMIN_TOKEN`
- `GCP_SERVICE_ACCOUNT_JSON` ou os campos `GCP_*` já utilizados pelo serviço

Use uma chave longa e aleatória em `V2_SHEETS_ADMIN_TOKEN`.

## Execução

Envie uma requisição POST com o cabeçalho:

```text
X-Admin-Token: <valor de V2_SHEETS_ADMIN_TOKEN>
```

Exemplo PowerShell:

```powershell
$headers = @{ "X-Admin-Token" = "SUA_CHAVE" }
Invoke-RestMethod `
  -Method Post `
  -Uri "https://roleplay2026-webhook.onrender.com/admin/initialize-v2-sheets" `
  -Headers $headers
```

A operação é idempotente: abas ausentes são criadas; abas com cabeçalhos corretos são preservadas; cabeçalhos incompatíveis causam erro sem sobrescrever dados.

Após a confirmação, remova `V2_SHEETS_ADMIN_TOKEN` do Render ou remova o endpoint em uma alteração posterior.
