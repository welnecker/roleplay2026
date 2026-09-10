# Organização do bucket `entrecenas-media`

Os objetos devem usar chaves estáveis e independentes do servidor Render:

- `stories/<package_id>/cover/<arquivo>` para capas do catálogo;
- `stories/<package_id>/scenes/<arquivo>` para imagens das interações.

Depois de enviar todos os objetos, configure no serviço Render:

```text
ENTRECENAS_MEDIA_URL=https://midia.entrecenas-roleplay.com.br
```

Sem essa variável, a API mantém automaticamente o fallback para os arquivos
locais. Isso permite validar o upload antes de transferir o tráfego de mídia.

```text
brand/entrecenas-icone.svg
landing/entrecenas-reel.mp4
landing/entrecenas-reel-poster.webp
stories/<package_id>/cover/capa.webp
stories/<package_id>/scenes/<arquivo>.webp
stories/<package_id>/microvideos/<quadro-ou-line-id>.mp4
```

O domínio público previsto é `https://midia.entrecenas-roleplay.com.br`.

- `brand/` e `landing/`: cache longo, com nomes versionados quando o conteúdo mudar.
- `cover/` e `scenes/`: usar `package_id` para impedir mistura entre histórias.
- `microvideos/`: usar o identificador estável do quadro ou da linha do roteiro.
- uploads e exclusões devem ocorrer por credencial S3 no backend ou na rotina de publicação; nenhuma chave secreta deve chegar ao navegador.
