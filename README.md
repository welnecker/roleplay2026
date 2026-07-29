# Roleplay 2026

Plataforma Streamlit para uma coletânea de histórias interativas independentes.

## Princípios do motor

- Uma linha de roteiro representa um movimento narrativo.
- Uma resposta executa apenas um movimento.
- O código escolhe rota, beat e ordem; o modelo não escolhe progressão.
- O movimento é consumido antes de qualquer rerun da interface.
- Cada história é um universo isolado, com personagens, cards, capítulos, roteiros e beats próprios.
- O estado definitivo será recuperável pelo Google Sheets; `st.session_state` é apenas estado temporário de interface.

## Escopo da interface inicial

- login demonstrativo com e-mail e senha;
- biblioteca de histórias em cards;
- história de degustação liberada;
- histórias pagas bloqueadas;
- ações de iniciar, continuar e reiniciar;
- tela inicial do player;
- interfaces preparadas para Google Sheets e Mercado Pago.

## Executar localmente

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Nesta etapa, autenticação, catálogo e progresso usam repositórios demonstrativos em memória. A troca por Google Sheets poderá ser feita sem alterar a interface.
