from __future__ import annotations

from persistence.sheets_read_optimization import install as install_sheets_read_optimization


# A política precisa entrar antes de o app construir os repositórios. Assim
# as tabelas operacionais já nascem com os TTLs por aba e o auditor observa
# as chamadas Google reais resultantes dessa política.
install_sheets_read_optimization()

from flet_api.app import production_app
from persistence.sheets_audit import install as install_sheets_audit


# Entrada futura e independente. Nenhum serviço de produção aponta para ela.
app = install_sheets_audit(production_app())
