"""Entrada do aplicativo instalável EntreCenas.

O backend, os secrets e as fontes autoritativas continuam no servidor. Este
módulo existe apenas como entrada estável para ``flet build``.
"""

import flet as ft

from flet_client.main import main


if __name__ == "__main__":
    ft.run(main)
