from __future__ import annotations

from pathlib import Path

import streamlit as st

from packages.loader import discover_packages
from persistence.accounts import GoogleSheetsAccountRepository
from platform_core.runtime_routing import player_page_for
from ui_components_legacy import CARD_CSS, render_story_card
from ui_components_legacy import (
    _install_sidebar_end_policy,
    _paid_access_resolver,
    _redirect_pending_checkout,
)


_INSTALLED_STORIES_ROOT = Path(__file__).resolve().parent / "installed_stories"


def _selected_package():
    package_id = str(st.session_state.get("selected_package_id", "") or "").strip()
    if not package_id:
        return None
    packages, _errors = discover_packages(_INSTALLED_STORIES_ROOT)
    return next(
        (package for package in packages if package.manifest.package_id == package_id),
        None,
    )


def _redirect_selected_player() -> None:
    if str(st.session_state.get("page", "") or "") != "player":
        return
    package = _selected_package()
    if package is None:
        return
    target = player_page_for(package)
    if target != "app.py":
        st.switch_page(target)


def inject_theme() -> None:
    GoogleSheetsAccountRepository.configure_paid_access_resolver(_paid_access_resolver)
    _install_sidebar_end_policy()
    _redirect_pending_checkout()
    _redirect_selected_player()
    st.markdown(CARD_CSS, unsafe_allow_html=True)


__all__ = ["CARD_CSS", "inject_theme", "render_story_card"]
