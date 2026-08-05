# Arquitetura Beat → Ponte → Beat/Pátio

Esta é a arquitetura obrigatória para cards editoriais presentes e futuros.

## Fluxo oficial

```text
beat atual
  ↓
resposta livre do usuário
  ↓
ponte contextual
  ├── continuidade preservada → progressão declarada / próximo beat
  ├── continuidade recuperável → mesmo beat ou transição declarada
  ├── continuidade quebrada → entrada de pátio terminal
  └── ameaça grave → ending imediato
```

A personagem conduz a história. O usuário participa sem precisar inventar cenário,
conflito ou próximos acontecimentos. A liberdade do usuário permanece real porque
uma ação incompatível produz consequência: a trajetória pode terminar.

## Responsabilidades

### Beat

Declara o movimento dramático, fatos confirmados, limites, transições e próximo
beat. O beat não tenta prever todas as falas possíveis.

### Ponte

Avalia se a resposta ainda permite executar a progressão sem ignorar o usuário,
controlar suas ações ou inventar uma nova história. A ponte adapta o tom, não o
destino do card.

### Pátio

Encerra organicamente uma trajetória cuja continuidade foi destruída. O pátio não
retorna ao fluxo principal e deve possuir pelo menos dois turnos de usuário quando
for declarado como `terminal_yard`.

### Ending imediato

Usado para ameaça, coerção, violência grave ou outra condição declarada pelo card
que não comporta despedida prolongada.

## Contrato de classificação

O classificador não recebe nem escolhe IDs. Ele retorna somente uma rota e um sinal
declarado no `interaction_context` do beat.

```json
{
  "route": "continue|terminal_yard|immediate_ending",
  "signal": "sinal_exatamente_declarado",
  "reason": "justificativa contextual",
  "confidence": 0.0
}
```

O runtime converte a rota no destino declarado pelo card.

## Rupturas narrativas típicas

Cards podem declarar, conforme a cena:

- saída do local atual;
- salto de tempo ou espaço que abandona a cena;
- recusa definitiva de participação exigida pelo próximo beat;
- conhecimento prévio que destrói anonimato, segredo ou premissa;
- fuga drástica e persistente do assunto;
- pedido explícito de encerramento;
- humilhação, importunação ou exposição vexatória;
- violência, coerção ou ameaça.

Essas categorias são contextuais. Linguagem sexual pode ser terminal no primeiro
contato público e compatível em um motel após desejo e consentimento mútuos.

## Isolamento entre cards e capítulos

Cada card compila o próprio `EditorialScript`, contexto, fatos, pátios e endings.
O motor oficial não contém regras específicas de Mary, supermercado ou motel.
Novos capítulos reutilizam o mesmo motor apenas declarando seus contextos e
transições no pacote.

Nunca compartilhar estado narrativo entre cards por variável global. Continuidade
entre capítulos deve ocorrer por memórias persistidas e fatos explicitamente
importados pelo novo card.

## Integração do player

O player registra o cliente classificador por injeção explícita:

```python
configure_editorial_turn_classifier(classifier_call)
```

A API pública permanece estável:

```python
decide_editorial_turn(script, state, user_text)
```

Não substituir `editorial_runtime.decide_editorial_turn`, não alterar atributos de
módulos em tempo de execução e não depender de importação anterior para instalar a
ponte.
