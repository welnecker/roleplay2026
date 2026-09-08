from __future__ import annotations

from flet_api.completed_run_restart_guard import install as install_completed_run_restart_guard
from flet_api.download_routes import install as install_download_routes
from flet_api.landing_routes import install as install_landing_routes
from flet_api.story_end_card import install as install_story_end_card
from flet_api.terminal_completion_policy import install as install_terminal_completion_policy
from flet_api.terminal_run_guard import install as install_terminal_run_guard
from flet_api.web_client_routes import install as install_web_client_routes
from persistence.sheets_read_optimization import install as install_sheets_read_optimization
from persistence.story_run_cache_guard import install as install_story_run_cache_guard


# A política precisa entrar antes de o app construir os repositórios. Assim
# as tabelas operacionais já nascem com os TTLs por aba e o auditor observa
# as chamadas Google reais resultantes dessa política.
install_sheets_read_optimization()
# STORY_RUNS usa cache longo quando encontra a run, mas ausência em cache não
# é autoritativa: outro fluxo pode ter criado a run depois da leitura vazia.
install_story_run_cache_guard()
# O último quadro permanece em uma run ativa enquanto ainda existem entries a
# revelar; somente a última revelação conclui a execução/pagamento consumido.
install_terminal_completion_policy()
# Conclusão normal é terminal: uma nova execução exige novo crédito/run_id.
# Também repara runs antigas que ficaram active apesar de state.finished=True.
install_completed_run_restart_guard()
# [FIM_HISTORIA] com texto vira um quadro final autoral, sem OpenRouter. A
# instalação vem depois da política terminal para interceptar apenas esse quadro
# determinístico e concluí-lo imediatamente depois de persistir a despedida.
install_story_end_card()
# Depois que um quadro terminal já foi devolvido pela API, avanços/reveals
# repetidos são respondidos em memória e não reabrem runtime/Google Sheets.
install_terminal_run_guard()

from flet_api.app import production_app
from persistence.sheets_audit import install as install_sheets_audit


# Entrada futura e independente. Nenhum serviço de produção aponta para ela.
# As rotas públicas de download ficam isoladas das APIs autenticadas e não
# alteram os contratos do cliente Flet.
app = install_web_client_routes(
    install_landing_routes(
        install_download_routes(install_sheets_audit(production_app()))
    )
)
