# Roleplay 2026

Plataforma Streamlit para executar uma coletânea de histórias interativas independentes.

## Princípio central

O aplicativo não conhece Mary nem qualquer personagem específico. Ele carrega pacotes de histórias autocontidos. Cada pacote possui seus próprios personagens, aparências, personalidades, relações, cards, capítulos, roteiros, beats, assets e regras.

Duas histórias podem ter personagens com o mesmo nome sem compartilhar identidade, estado ou memória.

## Regras narrativas preservadas

- Uma linha de roteiro representa um movimento narrativo.
- Uma resposta executa apenas um movimento.
- O código escolhe rota, beat e ordem; o modelo não escolhe progressão.
- O movimento é consumido antes de qualquer rerun da interface.
- O prompt do roteiro é isolado e autoritário.
- Não há herança estrutural obrigatória do projeto `mary_virtual`.

## Escopo inicial

- biblioteca de histórias instaladas;
- pacotes declarativos, sem execução de Python do autor;
- múltiplos usuários simultâneos;
- múltiplas instâncias do aplicativo;
- sessões e saves isolados por usuário e história;
- persistência inicial no Google Sheets;
- integração de LLM por provider;
- pagamentos Pix pelo Mercado Pago;
- liberação de acesso por história ou produto;
- histórico de eventos narrativos;
- capítulos, roteiros e beats independentes.

## Identidade e isolamento

Toda operação persistida deve conter, conforme aplicável:

```text
user_id
package_id
package_version
story_id
save_id
session_id
chapter_id
scene_id
character_id
interaction_id
```

Nunca se deve localizar ou atualizar um registro apenas pelo nome do personagem, capítulo ou história.

## Concorrência

O Streamlit mantém apenas o estado efêmero da aba do navegador. O estado autoritativo fica na persistência compartilhada.

Regras obrigatórias:

1. IDs são UUIDs e nunca dependem do número da linha da planilha.
2. Interações, eventos e pagamentos são append-only.
3. Atualizações de estado usam `state_version` para detectar gravações concorrentes.
4. Cada requisição de pagamento e webhook possui chave idempotente.
5. Uma instância nunca guarda dados de usuário em variável global mutável.
6. Caches contêm somente dados públicos e imutáveis dos pacotes.

## Google Sheets

O Google Sheets será usado inicialmente como persistência compartilhada, por meio de uma conta de serviço.

Abas previstas:

- `USERS`
- `STORY_PACKAGES`
- `USER_ENTITLEMENTS`
- `SAVES`
- `SESSIONS`
- `INTERACTIONS`
- `STORY_EVENTS`
- `MEMORIES`
- `PAYMENT_ORDERS`
- `PAYMENT_EVENTS`
- `WEBHOOK_EVENTS`

Interações, eventos e webhooks devem ser anexados, não sobrescritos. Objetos narrativos maiores podem ser serializados em JSON enquanto o volume for compatível com a solução.

Google Sheets é adequado para a primeira versão e tráfego moderado. A camada de repositórios deve permanecer independente para permitir migração futura para PostgreSQL sem alterar o motor narrativo.

## Pagamentos

O fluxo de acesso pago será:

```text
usuário escolhe história
→ backend cria pedido interno
→ backend cria cobrança Pix no Mercado Pago
→ usuário recebe QR Code e código copia-e-cola
→ Mercado Pago envia webhook
→ backend valida e registra o evento
→ pagamento aprovado cria entitlement
→ história é liberada
```

O navegador nunca libera acesso apenas por ter exibido uma tela de sucesso. A autorização depende de um `USER_ENTITLEMENTS` ativo, produzido após confirmação do pagamento no backend.

Segredos do Mercado Pago e do Google nunca ficam dentro de pacotes de histórias ou no navegador.

## Pacote de história

```text
installed_stories/<package_id>/
├── manifest.yaml
├── story.yaml
├── cards/
├── characters/
├── chapters/
├── locations/
├── prompts/
└── assets/
```

Exemplo de manifesto:

```yaml
package:
  id: br.com.autor.historia
  name: Minha História
  version: 1.0.0
  format_version: 1

author:
  name: Nome do Autor

story:
  entrypoint: story.yaml

compatibility:
  engine_min: 0.1.0

commerce:
  access_mode: paid
  product_id: historia_completa

isolation:
  memory: strict
  saves: strict
  characters: strict
```

## Estrutura inicial

```text
roleplay2026/
├── app.py
├── config.py
├── core/
├── domain/
├── engine/
├── packages/
├── providers/
├── repositories/
├── services/
├── ui/
├── installed_stories/
└── tests/
```

## Fases

### Fase 1 — fundação

- contrato dos pacotes;
- biblioteca local;
- login por token;
- sessões isoladas;
- repositórios Google Sheets;
- player mínimo;
- provider OpenRouter.

### Fase 2 — narrativa

- capítulos;
- roteiros;
- beats;
- eventos;
- estado de cena;
- memória por história.

### Fase 3 — comércio

- catálogo pago;
- criação de cobrança Pix;
- webhook idempotente;
- entitlement por usuário e produto;
- auditoria de pagamentos.

### Fase 4 — publicação

- importação de ZIP;
- instalação por repositório;
- validação de pacote;
- painel do autor;
- galeria de histórias.

## Execução

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```
