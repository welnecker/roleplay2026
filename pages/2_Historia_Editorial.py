from __future__ import annotations

from pathlib import Path


# Fachada transitória: o endereço público do player já é genérico, enquanto a
# implementação é movida gradualmente para fora do arquivo legado.
_legacy_player = Path(__file__).with_name("2_Piloto_Supermercado.py")
exec(
    compile(
        _legacy_player.read_text(encoding="utf-8"),
        str(_legacy_player),
        "exec",
    ),
    globals(),
    globals(),
)
