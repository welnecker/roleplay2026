# Pacote de card editorial

Cada história instalada deve ser um pacote independente. O aplicativo descobre o card pelo `manifest.yaml` e não deve conhecer personagens, cenários, arquivos ou regras específicas da história.

## Estrutura canônica

```text
installed_stories/<card_slug>/
├── manifest.yaml
├── story.yaml
└── content/
    ├── editorial.yaml
    └── extensions/
        ├── continuation.yaml
        ├── narrative.yaml
        ├── story.yaml
        ├── fixes.yaml
        └── guardrails.yaml
```

`story.yaml` permanece como entrypoint compatível do pacote. A execução editorial é declarada em `runtime.editorial` e aponta somente para arquivos dentro da própria pasta do card.

## Manifesto replicável

```yaml
format_version: 2
package_id: roleplay2026.example
version: 1.0.0
author:
  id: author_id
  name: Author
entrypoint: story.yaml
runtime:
  kind: editorial
  editorial:
    source: content/editorial.yaml
    extensions:
      - content/extensions/continuation.yaml
      - content/extensions/narrative.yaml
      - content/extensions/story.yaml
      - content/extensions/fixes.yaml
      - content/extensions/guardrails.yaml
card:
  title: Example
  subtitle: Card subtitle
  description: Card description
  genres:
    - Drama
  chapter_label: Chapter 1
  cover: ""
  character_profile:
    name: Character
    identity: Public identity shown on the card.
    personality: Public personality shown on the card.
    intention: Public intention shown on the card.
commerce:
  access: free
  price_cents: 0
  currency: BRL
  replay_policy: reuse_access
```

## Regras de independência

- Todos os arquivos usados pelo runtime ficam dentro da pasta do card.
- O app não importa módulos, personagens ou IDs exclusivos de um card.
- `package_id` identifica sessão, acesso, compra e persistência.
- Título, perfil, capa, preço e política de replay pertencem ao manifesto.
- Beats, memórias, finais e extensões pertencem ao conteúdo do pacote.
- Um novo card é instalado copiando a estrutura, alterando o manifesto e substituindo o conteúdo editorial.
