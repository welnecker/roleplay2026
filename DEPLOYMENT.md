# Implantação

A aplicação possui dois processos independentes:

1. `app.py` no Streamlit Community Cloud;
2. `webhook_api.py` em um serviço HTTPS separado.

Nenhum secret deve ser salvo no GitHub.

## 1. Streamlit Community Cloud

Crie ou atualize o app apontando para:

- repositório: `welnecker/roleplay2026`;
- branch: `agent/real-pix-payment` durante a homologação;
- arquivo principal: `app.py`.

Em **App settings > Secrets**, mantenha os valores já utilizados pelo projeto:

```toml
OPENROUTER_API_KEY = "..."
OPENROUTER_MODEL = "google/gemini-3-flash-preview"
ROLEPLAY_ACCOUNTS_BILLING_SPREADSHEET_ID = "..."
ROLEPLAY_RUNTIME_SPREADSHEET_ID = "..."
ROLEPLAY_EDITORIAL_SPREADSHEET_ID = "..."
MERCADO_PAGO_ACCESS_TOKEN = "..."
MERCADO_PAGO_WEBHOOK_SECRET = "..."
PAYMENT_TEST_MASTER_EMAILS = "welnecker@hotmail.com"

[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "..."
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
```

## 2. Webhook HTTPS no Render

O repositório contém `render.yaml` e `Dockerfile.webhook`.

No Render:

1. escolha **New > Blueprint**;
2. conecte o repositório `welnecker/roleplay2026`;
3. selecione a branch/commit homologado conforme o fluxo de publicação;
4. confirme o serviço `roleplay2026-webhook`;
5. preencha as variáveis secretas solicitadas.

Variáveis obrigatórias:

```text
ROLEPLAY_ACCOUNTS_BILLING_SPREADSHEET_ID
ROLEPLAY_RUNTIME_SPREADSHEET_ID
ROLEPLAY_EDITORIAL_SPREADSHEET_ID
GCP_SERVICE_ACCOUNT_JSON
MERCADO_PAGO_ACCESS_TOKEN
MERCADO_PAGO_WEBHOOK_SECRET
PAYMENT_TEST_MASTER_EMAILS
```

`GCP_SERVICE_ACCOUNT_JSON` deve receber o objeto JSON completo da conta de serviço do Google em uma única variável. Não envolva o objeto inteiro em aspas adicionais no painel do Render.

Após o deploy, valide:

```text
https://SEU-SERVICO.onrender.com/health
```

Resposta esperada:

```json
{"status":"ok"}
```

## 3. Mercado Pago

No painel da aplicação do Mercado Pago, configure Webhooks para o evento de Order usando:

```text
https://SEU-SERVICO.onrender.com/webhooks/mercado-pago
```

O secret exibido pelo Mercado Pago para validação do webhook deve ser salvo com o mesmo valor em:

```text
MERCADO_PAGO_WEBHOOK_SECRET
```

## 4. Verificação de ponta a ponta

1. Entre no app Streamlit com uma conta real.
2. Escolha uma história paga.
3. Clique em **Comprar com Pix**.
4. Gere a cobrança.
5. Faça um pagamento de teste ou use o ambiente configurado no Mercado Pago.
6. Confirme que aparecem registros nas abas:
   - `PAYMENT_ORDERS`;
   - `PAYMENT_EVENTS`;
   - `WEBHOOK_EVENTS`;
   - `STORY_CREDITS` após aprovação.
7. Volte à biblioteca e confirme que a história aparece liberada.

## Diagnóstico

- `/health` indisponível: verifique o deploy e os logs do Render.
- HTTP 401 no webhook: confira `MERCADO_PAGO_WEBHOOK_SECRET`.
- erro no Google Sheets: compartilhe a planilha com o `client_email` da conta de serviço.
- cobrança criada sem liberação: consulte `PAYMENT_EVENTS` e o status da order no Mercado Pago.

## Pagamento interno de teste

O fluxo falso não usa token sandbox nem parâmetros enviados pelo navegador. A
conta é resolvida pelo `user_id` na aba `USERS` e comparada, no servidor, com
`PAYMENT_TEST_MASTER_EMAILS`. Pagamentos desse fluxo são registrados como
`payment_mode=test_master` e `provider=test_master` antes da criação do crédito.

Antes da homologação, execute uma vez o inicializador de schemas para acrescentar
as colunas de auditoria ao final de `PAYMENT_ORDERS`. A migração é aditiva e não
reposiciona as colunas nem os dados existentes.
