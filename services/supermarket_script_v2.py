from __future__ import annotations

"""Alias temporário para a implementação editorial de progressão.

Este módulo existe apenas enquanto imports históricos são eliminados. Novos
consumidores devem usar ``services.editorial_progression``.
"""

import sys

from services import editorial_progression_impl as _editorial_progression_impl


sys.modules[__name__] = _editorial_progression_impl
