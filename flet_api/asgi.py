from __future__ import annotations

from flet_api.completed_run_restart_guard import install as install_completed_run_restart_guard
from flet_api.terminal_run_guard import install as install_terminal_run_guard
from persistence.sheets_read_optimization import install as install_sheets_read_optimization
from persistence.story_run_cache_guard import install as install_story_run_cache_guard


# A política precisa entrar antes de o app construir os repositórios. Assim
# as tabelas operacionais já nascem com os TTLs por aba e o auditor observa
# as chamadas Google reais resultantes dessa política.
install_sheets_read_optimization()
# STORY_RUNS usa cache longo quando encontra a run, mas ausência em cache não
# é autoritativa: outro fluxo pode ter criado a run depois da leitura vazia.
install_story_run_cache_guard()
# Conclusão normal é terminal: uma nova execução exige novo crédito/run_id.
# Também repara runs antigas que ficaram active apesar de state.finished=True.
install_completed_run_restart_guard()
# Depois que um quadro terminal já foi devolvido pela API, avanços repetidos
# são respondidos em memória e não reabrem o runtime/Google Sheets.
install_terminal_run_guard()

from flet_api.app import production_app
from persistence.sheets_audit import install as install_sheets_audit


# Entrada futura e independente. Nenhum serviço de produção aponta para ela.
app = install_sheets_audit(production_app())
