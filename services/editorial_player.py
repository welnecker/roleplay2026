from __future__ import annotations

import importlib
import sys
from types import ModuleType

from services.editorial_player_contextual_cycle import install_contextual_player_cycle
from services.editorial_script_cache import refresh_loaded_editorial_script_cache


_RUNTIME_MODULE = "services.editorial_player_runtime"


def _load_or_reload_runtime() -> ModuleType:
    """Carrega o runtime ou recarrega somente a instância ainda registrada."""

    # O classificador contextual é registrado antes da primeira importação ou
    # de qualquer hot reload do módulo executável. A camada visual não altera
    # mais widgets globais durante o bootstrap do app.
    install_contextual_player_cycle()

    loaded = sys.modules.get(_RUNTIME_MODULE)
    if loaded is None:
        return importlib.import_module(_RUNTIME_MODULE)

    refresh_loaded_editorial_script_cache(loaded)

    # O refresh pode invalidar/remover o módulo durante o hot reload do Streamlit.
    # Releia o registro oficial antes de chamar importlib.reload; uma referência
    # antiga não pode ser recarregada depois de sair de sys.modules.
    registered = sys.modules.get(_RUNTIME_MODULE)
    if registered is None:
        return importlib.import_module(_RUNTIME_MODULE)

    try:
        return importlib.reload(registered)
    except ImportError:
        # O Streamlit pode remover ou substituir o módulo entre a leitura acima
        # e a verificação interna feita por importlib.reload(). Nesse caso, não
        # tente recarregar a referência obsoleta: importe o registro atual.
        current = sys.modules.get(_RUNTIME_MODULE)
        if current is None or current is not registered:
            return importlib.import_module(_RUNTIME_MODULE)
        raise


def run_editorial_player() -> None:
    """Executa o player editorial em toda nova execução do Streamlit."""

    _load_or_reload_runtime()


__all__ = ["run_editorial_player"]
