from __future__ import annotations

"""Alias temporário para o auxiliar editorial de troca de contatos."""

import sys
from services import editorial_contact_exchange as _editorial_contact_exchange

sys.modules[__name__] = _editorial_contact_exchange
