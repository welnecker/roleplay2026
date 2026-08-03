from __future__ import annotations

"""Alias temporário para o módulo editorial concreto.

O objeto de módulo é substituído pelo runtime editorial real para que atribuições
transitórias feitas por consumidores antigos afetem os globais usados pelas
funções concretas. Este arquivo será removido após a migração dos imports.
"""

import sys

from services import editorial_runtime_impl as _editorial_runtime_impl


sys.modules[__name__] = _editorial_runtime_impl
