# Runtime narrativo v2 — modo novela contínua

## Objetivo do produto

O V2 existe para remover a principal fricção do roleplay: obrigar o usuário a inventar respostas para manter o roteiro andando.

A experiência passa a ser uma **novela interativa personalizada**. O usuário continua sendo reconhecido pelo nome e pelo contexto da run, mas a história tem uma espinha narrativa autoritativa e avança principalmente pelo botão **Avançar**.

Critério de sucesso do motor:

> O roteiro determina o que acontece. O modelo determina como aquilo ganha vida.

O objetivo comercial não é maximizar obediência a tags editoriais. É fazer o usuário querer clicar em **Avançar** mais uma vez, desejar uma continuação e ter vontade de rever a novela.

## Conceitos

- **Card/pacote**: produto narrativo pago e finito.
- **Cena**: contexto dramático contínuo, como encontro, carro, praia ou outro ambiente narrativo.
- **Movimento**: unidade autoritativa da história. Declara o acontecimento obrigatório sem prescrever uma fala exata.
- **Dramatização**: texto produzido pelo LLM para dar vida ao movimento atual.
- **Continuidade**: fatos já consolidados que o modelo pode reutilizar sem consultar movimentos futuros.
- **Crédito**: direito adquirido por pagamento para iniciar uma execução.
- **Run**: execução concreta de uma novela.

## Regras do motor novela

1. O runtime, nunca o LLM, escolhe qual movimento está ativo e qual vem depois.
2. O LLM recebe somente o movimento atual, o perfil da personagem e a continuidade necessária.
3. Um movimento declara **o que acontece**; o modelo decide ações, pausas, reações, ritmo e diálogo necessários para dramatizá-lo.
4. Não existem `[FALA EXATA]`, `[FALA EXATA INTIMA]` ou pensamentos literais como requisito do motor novela.
5. O roteiro pode declarar pensamentos, emoções e hesitações como intenção dramática, não como texto que precisa ser copiado.
6. Hesitações não encerram a run. São conflitos ou pausas dramáticas que se resolvem dentro da espinha narrativa.
7. O usuário não precisa enviar uma fala para que a história continue.
8. O botão **Avançar** altera o estado de forma determinística e não envia uma falsa mensagem do usuário ao modelo.
9. Movimentos futuros não entram no prompt do movimento atual.
10. O último movimento conclui a run normalmente.
11. Escolhas ocasionais poderão existir depois, mas devem alterar tom ou percurso local sem transformar o roteiro em uma árvore combinatória impossível de manter.
12. Login, cobrança, cards, onboarding, perfis, snapshots e persistência continuam fora do escopo desta mudança e devem ser preservados.

## Contrato mínimo do roteiro

Exemplo conceitual:

```text
[CENA encontro]

[MOVIMENTO]
Ao reconhecer {{nome}} no carro, eu me surpreendo positivamente e caminho até ele.
Conto que estou indo à praia e aproveito a coincidência para conseguir uma carona.
A cena transmite espontaneidade, intimidade prévia e satisfação pelo encontro.

[MOVIMENTO]
{{nome}} hesita por alguns segundos antes de aceitar.
Eu percebo a hesitação, transformo a situação em brincadeira e o clima volta a ficar leve.

[TRANSIÇÃO]
Alguns minutos depois, já no trânsito em direção à praia.
```

A implementação Python correspondente usa `MovementDefinition`. A representação definitiva na planilha será definida depois que o motor mínimo estiver validado.

## Fluxo de execução

```text
roteiro
  ↓
movimento atual
  ↓
runtime monta contexto compacto
  ↓
LLM dramatiza somente o movimento atual
  ↓
cena exibida
  ↓
[ Avançar ]
  ↓
runtime seleciona deterministicamente o próximo movimento
```

O clique em **Avançar** não é prompt engineering. É uma transição de estado do aplicativo.

## Prompt do dramatizador

O contexto enviado ao modelo deve conter apenas o necessário:

```text
PERSONAGEM
PROTAGONISTA
CONTINUIDADE
CENA
MOVIMENTO ATUAL
DIREÇÃO DRAMÁTICA opcional
TRANSIÇÃO opcional
```

Não enviar movimentos futuros para "ajudar" o modelo. Isso evita antecipações e reduz tokens.

## Compatibilidade

O V2 é desenvolvido em paralelo. O runtime atual continua disponível como referência funcional até que o fluxo novela passe nos testes e seja conectado explicitamente à interface.

Nenhuma migração destrutiva de dados ou de roteiros deve ocorrer durante esta fase.
