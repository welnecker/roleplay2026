# Inicialização das planilhas v2

Depois de configurar os três IDs e compartilhar as planilhas com a conta de serviço, execute uma única vez:

```powershell
python scripts/initialize_v2_sheets.py
```

O comando cria ou valida:

## ROLEPLAY_ACCOUNTS_BILLING

- USERS
- STORY_CREDITS
- PAYMENT_ORDERS
- PAYMENT_EVENTS
- WEBHOOK_EVENTS

## ROLEPLAY_RUNTIME

- STORY_RUNS
- SESSIONS
- INTERACTIONS
- RUN_MEMORIES

## ROLEPLAY_EDITORIAL

- STORIES
- CHARACTERS
- BLOCKS
- BEATS
- MEMORIES

A operação é idempotente. Abas existentes com cabeçalhos corretos são preservadas. Cabeçalhos divergentes provocam erro e não são sobrescritos.
