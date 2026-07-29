# roleplay2026

Motor de roleplay narrativo construído do zero.

## Princípios

- Uma linha de roteiro representa um movimento narrativo.
- Uma resposta executa apenas um movimento.
- O código escolhe rota, beat e ordem; o modelo não escolhe progressão.
- O movimento é consumido antes de qualquer rerun da interface.
- Não há monkey patch, wrapper de integração ou herança do projeto anterior.
- O prompt do roteiro é isolado e autoritário.

## Primeira meta

Validar o ciclo mínimo:

1. selecionar a menor ordem ainda não consumida;
2. gerar uma resposta para esse movimento;
3. consumir a ordem;
4. permanecer no beat enquanto houver movimentos;
5. avançar somente quando o beat terminar.
