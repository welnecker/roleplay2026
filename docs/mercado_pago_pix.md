# Mercado Pago Pix

## Secrets

A integração procura os seguintes nomes no `secrets.toml`:

```toml
MERCADO_PAGO_ACCESS_TOKEN = "APP_USR-..."
MERCADO_PAGO_WEBHOOK_SECRET = "..."
```

Também são aceitos os aliases `MERCADOPAGO_ACCESS_TOKEN`, `MP_ACCESS_TOKEN`, `MERCADOPAGO_WEBHOOK_SECRET` e `MP_WEBHOOK_SECRET`.

As credenciais do Google Sheets continuam em `GOOGLE_SHEETS_SPREADSHEET_ID` e `[gcp_service_account]`.

## Checkout Streamlit

A página `Pagamento Pix`:

1. usa o pacote escolhido na biblioteca;
2. cria uma order em `POST /v1/orders`;
3. grava `PAYMENT_ORDERS` e `PAYMENT_EVENTS`;
4. exibe QR Code, Pix Copia e Cola e `ticket_url`;
5. permite consultar novamente a order;
6. cria `USER_ENTITLEMENTS` apenas depois da confirmação obtida diretamente da API.

## Webhook

O webhook não pode ser hospedado como uma rota comum dentro do Streamlit. Publique `webhook_api.py` em um serviço HTTP que execute:

```bash
uvicorn webhook_api:app --host 0.0.0.0 --port 8000
```

Configure no Mercado Pago a URL HTTPS:

```text
https://SEU_BACKEND/webhooks/mercado-pago
```

Selecione o tópico **Order (Mercado Pago)** / `orders`.

O endpoint:

- valida `x-signature` com HMAC-SHA256;
- registra a entrega em `WEBHOOK_EVENTS`;
- ignora entregas duplicadas pelo ID do evento;
- consulta `GET /v1/orders/{id}`;
- libera o entitlement apenas para order confirmada.

A resposta ao Mercado Pago é enviada rapidamente com HTTP 200 quando a notificação é válida.

## Teste local

```bash
python -m pytest -q
uvicorn webhook_api:app --reload
```

Abra `/health` para verificar a disponibilidade do backend. Para testar notificações reais, a URL precisa ser HTTPS e acessível pela internet.
