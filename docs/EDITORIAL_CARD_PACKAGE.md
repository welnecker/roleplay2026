# Pacote editorial reproduzível

Cada história editorial deve ser descoberta pelo próprio `manifest.yaml`.

```yaml
runtime:
  kind: editorial
  editorial:
    source: editorial.yaml
    extensions: []
```

O player recebe o `selected_package_id`, resolve o pacote instalado e usa seus próprios metadados de card, versão, persistência e acesso. Nenhum título, cenário ou `package_id` de história pode ficar fixado na página do player.

Durante a migração, `pages/2_Piloto_Supermercado.py` mantém o nome legado para preservar a navegação do Streamlit, mas seu conteúdo já funciona como player editorial genérico. O arquivo será renomeado quando o roteamento da interface deixar de usar o identificador antigo.
