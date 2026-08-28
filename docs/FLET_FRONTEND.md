# Frontend Flet do ROLEPLAY2026

Esta branch introduz um frontend paralelo. O Streamlit continua sendo a
interface funcional e nenhum fluxo de produção foi substituído.

## Estado da primeira etapa

- parser compartilhado com a gramática canônica de quadros V2;
- descrição sempre visível;
- primeiro balão visível ao abrir o quadro;
- revelação de uma fala/pensamento por clique;
- próximo quadro liberado somente depois de todas as entries;
- imagem WebP preservada com `contain`;
- trilho horizontal de balões para desktop e mobile.
- tela de login em modo de prévia local claramente identificado;
- biblioteca responsiva com capas e metadados dos cards instalados;
- adaptação das capas em data URL para bytes no Flet desktop;
- navegação da biblioteca para o quadro demonstrativo.

## Executar no desktop

```powershell
python -m pip install -r requirements.txt
python -m flet_client.main
```

## Executar no navegador

```powershell
flet run --web flet_client/main.py
```

Também existe uma entrada ASGI, compatível com Uvicorn:

```powershell
uvicorn flet_client.asgi:app --host 0.0.0.0 --port 8000
```

O quadro atual é demonstrativo. A etapa seguinte criará a API autenticada que
entregará ao Flet os quadros persistidos pelo runtime existente. Secrets,
OpenRouter, Google Sheets e pagamentos permanecerão no servidor.

## API autenticada inicial

A API do cliente é independente da entrada de webhooks e pode ser executada,
em ambiente devidamente configurado, com:

```powershell
uvicorn flet_api.asgi:app --host 0.0.0.0 --port 8001
```

Contrato inicial:

- `POST /api/v1/auth/login`: autentica na base autoritativa e cria sessão;
- `GET /api/v1/auth/me`: revalida a identidade da sessão;
- `POST /api/v1/auth/logout`: revoga a sessão atual;
- `GET /api/v1/catalog`: retorna cards reais como `free`, `owned` ou `locked`.

O token é opaco, expira no servidor e pode ser revogado. Esta primeira versão
mantém as sessões em memória; reinícios do processo encerram as sessões, sem
afetar contas, entitlements ou runs persistidas. A API não expõe credenciais do
Google, Mercado Pago, OpenRouter nem conteúdo interno do runtime.

Enquanto o cliente ainda não está apontado para essa API, `python -m
flet_client.main` apresenta login e biblioteca em modo de prévia local. Os
campos de login não são enviados e os botões de demonstração não concedem
entitlements. Essa separação evita confundir a validação visual com acesso real.
