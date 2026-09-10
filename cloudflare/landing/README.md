# Landing no Cloudflare Pages

Esta pasta contém os arquivos de configuração da landing estática. O HTML é
gerado a partir da mesma fonte usada pelo fallback no Render, evitando duas
versões divergentes da página.

## Configuração do projeto Pages

- Branch de produção: `agent/cloudflare-media-migration`
- Comando de build: `python scripts/build_cloudflare_landing.py`
- Diretório de saída: `cloudflare/landing/dist`
- Diretório raiz do projeto: repositório

O build usa estes endereços por padrão:

- site: `https://entrecenas-roleplay.com.br`
- app: `https://app.entrecenas-roleplay.com.br`
- mídia: `https://midia.entrecenas-roleplay.com.br`

Eles podem ser substituídos pelas variáveis `ENTRECENAS_SITE_URL`,
`ENTRECENAS_APP_URL` e `ENTRECENAS_MEDIA_URL` no Pages.

Antes do primeiro deploy público, os domínios `app` e `midia` precisam estar
ativos. Até a virada de DNS, a landing que está no Render continua atendendo o
domínio principal.
