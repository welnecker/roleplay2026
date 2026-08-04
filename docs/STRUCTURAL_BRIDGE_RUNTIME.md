# Ponte estrutural do runtime editorial

## Máquina de estados

O runtime editorial trabalha com três fases narrativas explícitas:

```text
CANONICAL -> BRIDGE -> CANONICAL
CANONICAL -> TERMINAL_YARD -> ENDING
```

A fonte de verdade é `facts._runtime_phase`, com os valores:

- `canonical`
- `bridge`
- `terminal_yard`

Estados antigos sem fase explícita são interpretados como `canonical`.

## Fase canônica

Na fase `canonical`, o beat atual recebe a mensagem do usuário e o runtime calcula o destino.

Quando o destino é outro beat canônico e não existe decisão já resolvida, o avanço é suspenso e uma ponte é criada.

## Fase de ponte

A ponte:

- preserva `node_id` no beat de origem;
- registra o próximo beat em `pending_next_beat_id`;
- registra `_bridge_origin_beat_id` e `_bridge_target_beat_id`;
- responde à fala atual do usuário sem executar a linha futura;
- usa fallback neutro, sem conteúdo do beat seguinte;
- não grava memórias pertencentes ao beat futuro;
- não presume aceite, recusa, ação ou desejo não declarado.

No turno seguinte, o estado de ponte é liberado e o beat pendente volta à progressão canônica.

## Decisões explícitas e saltos por fatos

Uma decisão explícita ou um salto determinístico não recebe ponte redundante.

Esses marcadores são válidos somente no beat onde foram produzidos:

- `_last_user_intent_beat_id`
- `_declared_skip_origin_beat_id`

Marcadores antigos ou pertencentes a outro beat não podem interferir em pontes futuras.

## Memória

Memórias seguem o beat realmente entregue:

```text
ponte criada -> nenhuma memória do beat futuro
beat liberado -> memória do beat aplicada uma vez
```

A lista `_active_memory_ids` é deduplicada na finalização.

## Pátios e endings

Destinos estruturais não recebem ponte intermediária:

```text
CANONICAL -> TERMINAL_YARD -> ENDING
```

O pátio mantém a interação ativa pelo número mínimo de turnos declarado e controla sua própria saída.

## Recuperação de run

O estado persistido deve ser suficiente para restaurar uma ponte após fechar e reabrir o navegador.

Uma run recuperada em `bridge` deve preservar:

- beat de origem;
- beat alvo;
- `pending_next_beat_id`;
- fase estrutural.

O próximo turno libera exatamente o alvo persistido.

## Compatibilidade

Cards com `bridge_policy` usam exclusivamente a ponte estrutural.

Cards ainda não migrados podem continuar utilizando `organic_slack` e `_organic_interstitial` como compatibilidade legada. Esses campos não são fonte de verdade para cards migrados.

## Falhas de geração

O estado narrativo só é confirmado após a resposta ser aprovada pelo avaliador.

Em falha de geração ou rejeição total:

- o beat não avança;
- a memória não é gravada;
- a linha futura não pode aparecer no fallback;
- o usuário pode repetir o turno sem corromper a progressão.
