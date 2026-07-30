# Runtime narrativo v2

## Conceitos

- **Card/pacote**: produto narrativo pago e finito.
- **Bloco**: trecho interno contínuo de uma história.
- **Beat**: unidade obrigatória de atuação. O roteiro determina o que precisa acontecer; o modelo decide como interpretar.
- **Memória permanente**: fato consolidado após um beat ou bloco e reutilizado nos blocos seguintes.
- **Crédito**: direito adquirido por Pix para iniciar uma execução.
- **Run**: execução concreta e única de um card.
- **Encerramento**: beat final, integral ou antecipado, que fecha a run e retorna à biblioteca.

## Regras do motor

1. Um beat por resposta; dois apenas quando formarem uma única reação natural.
2. No máximo uma pergunta por resposta.
3. O modelo não antecipa beats.
4. O modelo não inventa falas, ações, nudez, excitação ou decisões do usuário.
5. O usuário pode desviar, recusar ou abandonar; o roteiro não é obrigado a sobreviver.
6. Toda recusa definitiva prevista aponta para um beat de encerramento.
7. O conteúdo obrigatório do beat deve ser executado, mas nunca entregue como catálogo de frases.
8. Identidade, memória e contexto fornecem dramaticidade, gestos, ritmo e vocabulário.
9. A introdução fixa é exibida antes da primeira interação e não consome tokens.
10. A primeira mensagem consome um crédito e cria a run.

## Estrutura do pacote

```text
installed_stories/<package_id>/
├── manifest.yaml
├── introduction.md
├── character.yaml
├── blocks.yaml
├── beats.yaml
├── memories.yaml
└── assets/
```

## Planilhas coletivas

Nunca criar uma aba por usuário.

### STORY_CREDITS

`credit_id,user_id,package_id,payment_id,status,run_id,created_at,consumed_at`

### STORY_RUNS

`run_id,credit_id,user_id,package_id,script_version,current_block_id,current_beat_id,status,ending_code,state_version,permanent_memory_ids_json,started_at,ended_at,updated_at`

### INTERACTIONS

Manter a aba atual e acrescentar metadados narrativos:

`run_id,block_id,beat_id,speaker_id,user_intent,beat_consumed,input_tokens,output_tokens`

### RUN_MEMORIES

`run_memory_id,run_id,memory_id,source_beat_id,created_at`

O texto oficial da memória permanece em `memories.yaml`; a planilha guarda apenas o identificador adquirido.

## Estados

### Crédito

- `available`
- `consumed`
- `revoked`

### Run

- `active`
- `completed`
- `terminated`

### Encerramentos iniciais

- `full_completion`
- `phone_refused`
- `video_refused`
- `meeting_refused`
- `user_no_show`
- `user_abandoned`
- `user_hostile`
- `script_break`
- `user_restarted`

## Fluxo comercial

```text
Pix aprovado
→ STORY_CREDIT available
→ usuário abre o card e lê a introdução
→ primeira mensagem
→ crédito consumed
→ STORY_RUN active
→ beats e memórias
→ beat de encerramento
→ run completed ou terminated
→ retorno à biblioteca
→ nova tentativa exige novo Pix
```

## Compatibilidade

Esta primeira etapa é apenas um esqueleto. O runtime atual continua ativo até que o carregador, o motor e a persistência v2 sejam conectados explicitamente.