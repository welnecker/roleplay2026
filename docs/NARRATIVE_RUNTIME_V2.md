# Runtime narrativo v2 — modo novela contínua

## Objetivo do produto

O V2 existe para remover a principal fricção do roleplay: obrigar o usuário a inventar respostas para manter o roteiro andando.

A experiência passa a ser uma **novela interativa personalizada**. O usuário continua sendo reconhecido pelo nome e pelo contexto da run, mas a história tem uma espinha narrativa autoritativa e avança principalmente pelo botão **Avançar**.

Critério de sucesso do motor:

> O roteiro determina o que acontece. A consciência da personagem determina por que aquilo acontece. O modelo transforma isso em fala viva.

O objetivo comercial não é maximizar obediência a tags editoriais. É fazer o usuário querer clicar em **Avançar** mais uma vez, desejar uma continuação e ter vontade de rever a novela.

## Conceitos

- **Card/pacote**: produto narrativo pago e finito.
- **Cena**: contexto dramático contínuo.
- **Movimento**: unidade autoritativa da história. Declara o acontecimento obrigatório sem prescrever uma fala exata.
- **Impulso autoral**: desejo, motivação ou intenção psicológica que explica por que a personagem quer produzir aquele movimento.
- **Consciência privada**: pensamento contextual curto, formado a partir de histórico + impulso autoral + movimento atual. Nunca é exibido ao usuário.
- **Fala**: única saída visível normal do movimento. Deve soar como consequência da consciência privada, não como tradução mecânica do beat.
- **Continuidade**: fatos já consolidados que devem ser tratados como passado consumado, sem recapitulação.
- **Crédito**: direito adquirido por pagamento para iniciar uma execução.
- **Run**: execução concreta de uma novela.

## Regras do motor novela

1. O runtime, nunca o LLM, escolhe qual movimento está ativo e qual vem depois.
2. Um movimento declara **o que acontece**.
3. O impulso autoral declara **por que a personagem quer que aquilo aconteça**.
4. Antes de falar, o modelo forma silenciosamente uma consciência privada respondendo: "o que eu quero agora, por que quero isso e como isso nasce do que acabou de acontecer?".
5. A consciência privada nunca é impressa, persistida como fala ou mostrada na interface.
6. A saída visível normal é somente a fala da personagem em primeira pessoa.
7. O histórico é memória viva: cada novo movimento acrescenta somente o delta narrativo e não reabre beats anteriores.
8. Não existem `[FALA EXATA]`, `[FALA EXATA INTIMA]` ou pensamentos literais como requisito do motor novela.
9. Pensamentos antigos podem ser reaproveitados como **impulso autoral**, nunca como texto obrigatório.
10. Hesitações não encerram a run. São conflitos ou pausas dramáticas resolvidos dentro da espinha narrativa.
11. O usuário não precisa enviar fala para que a história continue.
12. O botão **Avançar** altera o estado de forma determinística e não envia uma falsa fala do usuário.
13. Se um movimento exige que o protagonista faça algo, a personagem pode conduzi-lo por comando, convite ou incentivo; o clique seguinte presume a continuidade necessária.
14. A fala não deve terminar aguardando resposta, opinião, escolha ou confirmação.
15. Movimentos futuros não entram no prompt do movimento atual.
16. O último movimento conclui a run normalmente.
17. Login, cobrança, cards, onboarding, perfis, snapshots e persistência continuam fora do escopo desta mudança e devem ser preservados.

## Contrato mínimo do roteiro

Exemplo conceitual:

```text
[CENA encontro]

[MOVIMENTO]
Eu conto que estou indo à praia e consigo uma carona com {{nome}}.

[IMPULSO]
Preciso da carona, mas também quero aproveitar a coincidência para ficar mais perto dele.

[MOVIMENTO]
Eu conto que terminei com Juninho.

[IMPULSO]
Quero que {{nome}} perceba naturalmente que estou livre, sem transformar isso numa declaração artificial.

[MOVIMENTO]
Eu revelo que fiz uma tatuagem escondida.

[IMPULSO]
Quero usar a novidade como provocação e como pretexto para aumentar a proximidade.
```

A representação definitiva na planilha poderá adotar `[IMPULSO]` depois da validação prática. Enquanto isso, o adaptador V2 pode reaproveitar unidades de pensamento interpretativo existentes como impulso autoral.

## Fluxo de execução

```text
roteiro
  ↓
movimento atual — o que acontece
  ↓
impulso autoral — por que ela quer
  ↓
histórico — o que acabou de acontecer
  ↓
consciência privada — intenção imediata
  ↓
fala curta em primeira pessoa
  ↓
[ Avançar ]
  ↓
runtime seleciona deterministicamente o próximo movimento
```

O clique em **Avançar** não é prompt engineering. É uma transição de estado do aplicativo.

## Continuidade e economia

A unidade perceptível para o usuário não é o beat. É a conversa inteira.

Portanto:

- não recapitular contexto para iniciar cada movimento;
- não repetir o nome do protagonista como vício de abertura;
- não criar justificativas já conhecidas;
- preferir uma ou duas frases curtas;
- cada frase deve acrescentar algo novo;
- quando o movimento seguinte pressupõe uma ação decorrente do anterior, essa ação é tratada como fato consumado.

Exemplo:

```text
— Para o carro aqui rapidinho. Assim eu consigo te mostrar melhor.

[Avançar]

— Pronto... agora chega mais perto. De longe você não vai ver onde o desenho termina.
```

Não deve existir uma etapa intermediária pedindo aceite ou opinião.

## Compatibilidade

O V2 é desenvolvido em paralelo. O runtime anterior continua disponível como referência funcional até que a experiência novela seja validada.

Nenhuma migração destrutiva de dados ou de roteiros deve ocorrer durante esta fase.
