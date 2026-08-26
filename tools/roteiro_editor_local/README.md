# Editor Local de Roteiros V2

Ferramenta autoral independente do runtime comercial do Roleplay2026.

## Abrir no Windows

Dê duplo clique em:

`tools\roteiro_editor_local\ABRIR_EDITOR_ROTEIROS.bat`

O lançador usa primeiro `.venv\Scripts\python.exe`, quando existir. Caso Streamlit ou Pillow não estejam disponíveis, instala somente as dependências locais do editor.

## Fluxo

1. Informe `package_id`, `script_version`, prefixo dos quadros e atores.
2. Escreva o roteiro com `[DESCRIÇÃO]`, `[FALA ator]`, `[FALA EXATA ator]`,
   `[FALA INTERPRETADA ator]` e `[PENSAMENTO ator]`.
3. Clique em **Validar e atualizar estrutura**. O editor usa o compilador V2 oficial para gerar `line_id` e `order`.
4. Importe várias imagens para atribuí-las, em sequência, às próximas `[DESCRIÇÃO]` sem imagem.
5. Se necessário, habilite imagens em `[FALA]`/`[PENSAMENTO]` e faça uma atribuição individual.
6. Defina prefixo e primeiro número da imagem. Exemplo: `camilly` + `1` gera `camilly1.webp`, `camilly2.webp` etc.
7. Exporte para Excel/TSV/CSV ou salve o pacote completo numa pasta do PC.

## Pasta exportada

```text
pasta_escolhida/
├── roteiro.xlsx
├── roteiro.csv
├── roteiro.tsv
├── projeto_roteiro.json
└── imagens/
    ├── camilly1.webp
    ├── camilly2.webp
    └── ...
```

As imagens são convertidas para WebP, preservando a proporção, com qualidade e dimensão máxima configuráveis no editor.

## Cabeçalho oficial

A exportação contém exatamente estas sete colunas, nesta ordem:

```text
package_id
script_version
line_id
order
instruction
status
image_id
```

Não há `updated_at` na saída do editor local.

## Publicação

O editor não publica nada automaticamente. Depois da revisão:

- copie os WebP da subpasta `imagens` para `installed_stories/<historia>/assets/scenes` no GitHub;
- copie as linhas de `roteiro.xlsx`/`roteiro.tsv` para a aba `ROTEIROS` do Google Sheets.
