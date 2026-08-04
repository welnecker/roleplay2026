# Hotfix: carregamento infinito antes do login

O app construía o repositório do Google Sheets durante a montagem da tela de login.
Quando a API do Google não respondia, o Streamlit permanecia em carregamento contínuo e
nenhum formulário era exibido.

A conexão do runtime agora possui limite operacional de oito segundos. Em caso de timeout,
a exceção é tratada pelo fallback já existente no `app.py`, permitindo que a interface seja
renderizada em vez de bloquear indefinidamente.

Este hotfix é uma contenção operacional. A evolução recomendada é tornar a conexão de contas
totalmente preguiçosa, executada somente após o envio do formulário.
