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
- tela de login conectável à API autenticada;
- biblioteca responsiva com capas e metadados dos cards instalados;
- capas servidas pela API como arquivos HTTP, sem Base64 no cliente;
- Pix real e pagamento interno master executados somente no servidor;
- abertura/retomada de `STORY_RUNS`, `SESSIONS` e `INTERACTIONS`;
- roteiro ativo carregado de `ROLEPLAY_RUNTIME.ROTEIROS`;
- checkpoint da revelação persistido em `INTERACTIONS.metadata_json`;
- geração do próximo quadro somente depois da revelação completa.

## Executar no desktop

```powershell
python -m pip install -r requirements.txt
python -m flet_client.main
```

Por padrão, o cliente usa a API publicada em
`https://entrecenas-roleplay.com.br`. A variável
`ROLEPLAY_FLET_API_URL` continua disponível para apontar o cliente para uma API
local ou para outro ambiente.

## Aplicativos instaláveis para Android e Windows

O cliente pode ser empacotado como aplicativo autônomo. Nesse contexto,
"autônomo" significa que o aparelho do usuário não precisa ter Python, Flet ou
o repositório instalados. O aplicativo continua precisando de internet e da API
publicada, pois login, Pix, roteiros, runs, imagens e geração narrativa seguem
protegidos no servidor.

O `pyproject.toml` da raiz define:

- produto `EntreCenas`;
- identificador Android estável `br.com.entrecenas.roleplay`;
- versão atual `0.1.5`, com número de build atribuído pela automação;
- Python embarcado 3.12;
- Android mínimo API 24 e alvo API 36;
- somente `flet`, `flet-secure-storage` e `requests` no cliente;
- exclusão de código de servidor, planilhas, stories e secrets do pacote;
- ícones próprios para Android e Windows.

### Gerar no próprio computador

No ambiente virtual da branch:

```powershell
python -m pip install uv
uv sync
```

Para gerar o APK Android no Windows:

```powershell
uv run flet build apk --yes --verbose
```

O resultado fica em `build\apk`. O Flet instala automaticamente o JDK 17 e o
Android SDK compatível caso não estejam disponíveis. O APK gerado sem uma chave
privada de produção serve para instalação e validação direta nos aparelhos de
teste.

Para gerar o aplicativo Windows:

```powershell
uv run flet build windows --yes --verbose
```

O resultado fica em `build\windows`. Esse build precisa ser executado no
Windows com o Visual Studio e a carga de trabalho **Desenvolvimento para desktop
com C++** instalados.

### Gerar pelo GitHub Actions

O workflow `Build EntreCenas Clients` pode ser executado manualmente e também
roda quando os arquivos do cliente são enviados à branch
`agent/flet-visual-client`. Ele produz, na mesma execução:

- `EntreCenas-Android-APK`;
- `EntreCenas-Windows`.

Os arquivos ficam nos artefatos da execução por 14 dias. Quando uma publicação
oficial é solicitada, o APK assinado e o pacote Windows também são anexados à
mesma release permanente do GitHub. O workflow não publica em loja, não faz
deploy e não altera planilhas ou produção.

## Executar no navegador

```powershell
flet run --web flet_client/main.py
```

Também existe uma entrada ASGI, compatível com Uvicorn:

```powershell
uvicorn flet_client.asgi:app --host 0.0.0.0 --port 8000
```

Não existem mais `DEMO_FRAME` ou `DEMO_IMAGE` no cliente. Secrets, OpenRouter,
Google Sheets e pagamentos permanecem exclusivamente no servidor.

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
- `POST /api/v1/payments/*`: cria/confere Pix ou pagamento master autorizado;
- `POST /api/v1/runs/open`: abre ou retoma a run e devolve o quadro persistido;
- `POST /api/v1/runs/reveal`: salva o checkpoint visual do quadro;
- `POST /api/v1/runs/advance`: valida o checkpoint e gera o próximo quadro.

O token é opaco, expira no servidor e pode ser revogado. Esta primeira versão
mantém as sessões em memória; reinícios do processo encerram as sessões, sem
afetar contas, entitlements ou runs persistidas. A API não expõe credenciais do
Google, Mercado Pago, OpenRouter nem conteúdo interno do runtime.

## Conectar o cliente à API

O fluxo padrão não possui mais login de prévia. Configure a URL do servidor
antes de iniciar o cliente:

```powershell
$env:ROLEPLAY_FLET_API_URL="http://127.0.0.1:8001"
python -m flet_client.main
```

O login envia e-mail e senha para `POST /api/v1/auth/login`, guarda o Bearer
somente no processo atual e carrega `GET /api/v1/catalog`. As capas usam URLs
como `/api/v1/catalog/{package_id}/cover`. O cliente nunca cria créditos ou
entitlements: ele solicita as operações ao servidor autenticado.

Para um teste local completo, a API deve rodar em outro terminal com os secrets
do servidor configurados:

```powershell
uvicorn flet_api.asgi:app --host 127.0.0.1 --port 8001
```

Sem uma API acessível, a tela permanece no login
e apresenta uma mensagem de configuração/conexão.

## Fontes autoritativas

- `ROLEPLAY_ACCOUNTS_BILLING`: `USERS`, `USER_CREDENTIALS`, `STORY_CREDITS`,
  `PAYMENT_ORDERS`, `PAYMENT_EVENTS` e `WEBHOOK_EVENTS`;
- `ROLEPLAY_RUNTIME`: `ROTEIROS`, `STORY_RUNS`, `SESSIONS` e `INTERACTIONS`.

`ROLEPLAY_EDITORIAL_SPREADSHEET_ID` é compatível, mas deixou de ser obrigatório;
quando ausente, o runtime usa o próprio `ROLEPLAY_RUNTIME` para `ROTEIROS`.
