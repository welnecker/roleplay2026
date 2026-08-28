# Frontend Flet do ROLEPLAY2026

Esta branch introduz um frontend paralelo. O Streamlit continua sendo a
interface funcional e nenhum fluxo de produção foi substituído.

## Estado da primeira etapa

- parser compartilhado com a gramática canônica de quadros V2;
- descrição sempre visível;
- primeiro balão visível ao abrir o quadro;
- revelação de uma fala/pensamento por clique;
- próximo quadro liberado somente depois de todas as entries;
- imagem WebP preservada com `contain`;
- trilho horizontal de balões para desktop e mobile.

## Executar no desktop

```powershell
python -m pip install -r requirements.txt
python -m flet_client.main
```

## Executar no navegador

```powershell
flet run --web flet_client/main.py
```

Também existe uma entrada ASGI, compatível com Uvicorn:

```powershell
uvicorn flet_client.asgi:app --host 0.0.0.0 --port 8000
```

O quadro atual é demonstrativo. A etapa seguinte criará a API autenticada que
entregará ao Flet os quadros persistidos pelo runtime existente. Secrets,
OpenRouter, Google Sheets e pagamentos permanecerão no servidor.
