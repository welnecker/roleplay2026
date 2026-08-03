from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import streamlit as st

from packages.loader import discover_packages
from persistence.accounts import GoogleSheetsAccountRepository
from platform_core.models import AccessStatus, ProgressStatus, StoryCard
from platform_core.runtime_routing import player_page_for
import ui_components_legacy as _legacy


CARD_CSS = _legacy.CARD_CSS
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


def _profile_from_card(story: StoryCard) -> dict[str, str]:
    return {
        "name": story.profile_name or story.title,
        "identity": story.profile_identity or story.description,
        "personality": story.profile_personality
        or (
            "Uma presença construída para reagir às suas escolhas e revelar "
            "novas camadas ao longo da história."
        ),
        "intention": story.profile_intention
        or (
            "Conduzir uma relação própria com você sem antecipar os "
            "acontecimentos decisivos da trama."
        ),
    }


# A renderização visual permanece temporariamente no módulo legado, mas seus
# dados já são resolvidos pelo contrato do card, nunca pelo package_id.
_legacy._character_profile = _profile_from_card


def render_story_card(
    story: StoryCard,
    *,
    on_start: Callable[[str], None],
    on_continue: Callable[[str], None],
    on_restart: Callable[[str], None],
    on_buy: Callable[[str], None],
) -> None:
    del on_restart, on_buy

    _legacy._render_flip_card(story)

    if story.access_status == AccessStatus.LOCKED:
        st.markdown(f"### {story.price_label}")
        if st.button(
            "Jogar novamente — pagar com Pix"
            if story.progress_status == ProgressStatus.COMPLETED
            else "Comprar com Pix",
            key=f"buy:{story.package_id}",
            use_container_width=True,
            type="primary",
        ):
            _legacy._open_pix_checkout(story.package_id)
        return

    if story.progress_status == ProgressStatus.NOT_STARTED:
        if st.button(
            "Iniciar história",
            key=f"start:{story.package_id}",
            use_container_width=True,
            type="primary",
        ):
            on_start(story.package_id)
        return

    if st.button(
        "Continuar história",
        key=f"continue:{story.package_id}",
        use_container_width=True,
        type="primary",
    ):
        on_continue(story.package_id)

    if story.replay_requires_purchase and st.button(
        "Reiniciar — novo pagamento",
        key=f"restart-paid:{story.package_id}",
        use_container_width=True,
    ):
        _legacy._finish_and_restart_paid_story(story.package_id)


def inject_theme() -> None:
    GoogleSheetsAccountRepository.configure_paid_access_resolver(
        _legacy._paid_access_resolver
    )
    _legacy._install_sidebar_end_policy()
    _legacy._redirect_pending_checkout()
    _redirect_selected_player()
    st.markdown(CARD_CSS, unsafe_allow_html=True)


__all__ = ["CARD_CSS", "inject_theme", "render_story_card"]
