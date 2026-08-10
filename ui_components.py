from __future__ import annotations

from collections.abc import Callable
from html import escape
from pathlib import Path

import streamlit as st

from packages.loader import discover_packages
from persistence.accounts import GoogleSheetsAccountRepository
from platform_core.models import AccessStatus, ProgressStatus, StoryCard
from platform_core.runtime_routing import player_page_for
from services.paid_run_access import get_paid_run_access, terminate_paid_access
from ui_theme import CARD_CSS


_INSTALLED_STORIES_ROOT = Path(__file__).resolve().parent / "installed_stories"
_ORIGINAL_BUTTON = st.button
_BUTTON_POLICY_INSTALLED = False


def _selected_package():
    package_id = str(st.session_state.get("selected_package_id", "") or "").strip()
    if not package_id:
        return None
    packages, _errors = discover_packages(_INSTALLED_STORIES_ROOT)
    return next(
        (package for package in packages if package.manifest.package_id == package_id),
        None,
    )


def _paid_access_resolver(*, user_id: str, package_id: str, access: str) -> bool:
    if access == "free":
        return True
    try:
        return get_paid_run_access(
            secrets=st.secrets,
            user_id=user_id,
            package_id=package_id,
        ).allowed
    except Exception:
        return False


def _discard_from_session_collection(name: str, value: str) -> None:
    collection = st.session_state.get(name)
    if hasattr(collection, "discard"):
        collection.discard(value)
    elif isinstance(collection, dict):
        collection.pop(value, None)


def _clear_story_session(package_id: str, user_id: str = "") -> None:
    for name in ("story_states", "story_messages", "runtime_contexts"):
        mapping = st.session_state.get(name)
        if isinstance(mapping, dict):
            mapping.pop(package_id, None)
    for name in ("started_packages", "restart_requests"):
        _discard_from_session_collection(name, package_id)

    st.session_state.pop(f"pix_order:{package_id}", None)
    st.session_state.pop(f"pix_qr_base64:{package_id}", None)
    st.session_state.pop("payment_access_ready", None)
    if user_id:
        st.session_state.pop(f"immersive_profile:{user_id}:{package_id}", None)

    if user_id:
        prefix = f"editorial:{user_id}:{package_id}:"
        for key in list(st.session_state.keys()):
            if str(key).startswith(prefix):
                st.session_state.pop(key, None)


def _open_pix_checkout(package_id: str) -> None:
    st.session_state.pop(f"pix_order:{package_id}", None)
    st.session_state.pop(f"pix_qr_base64:{package_id}", None)
    st.session_state.checkout_package_id = package_id
    st.session_state.page = "checkout"
    st.switch_page("pages/1_Pagamento_Pix.py")


def _send_to_new_payment(*, user_id: str, package_id: str) -> None:
    _clear_story_session(package_id, user_id)
    st.session_state.checkout_package_id = package_id
    st.session_state.selected_package_id = None
    st.session_state.page = "checkout"
    st.switch_page("pages/1_Pagamento_Pix.py")


def _finish_and_restart_paid_story(package_id: str) -> None:
    user = st.session_state.get("authenticated_user")
    user_id = str(getattr(user, "user_id", "") or "")
    if not user_id:
        st.error("Não foi possível identificar o usuário desta execução.")
        return
    try:
        terminate_paid_access(
            secrets=st.secrets,
            user_id=user_id,
            package_id=package_id,
            ending_code="user_restart_requested",
        )
    except Exception as exc:
        st.error(f"Não foi possível encerrar a execução atual: {exc}")
        return
    _send_to_new_payment(user_id=user_id, package_id=package_id)


def _install_sidebar_end_policy() -> None:
    global _BUTTON_POLICY_INSTALLED
    if _BUTTON_POLICY_INSTALLED:
        return

    def guarded_button(label: str, *args: object, **kwargs: object) -> bool:
        if label != "Reiniciar história":
            return bool(_ORIGINAL_BUTTON(label, *args, **kwargs))

        st.caption(
            "Encerrar esta execução elimina o acesso atual. Para jogar novamente, "
            "pode ser necessário realizar um novo pagamento."
        )
        clicked = bool(
            _ORIGINAL_BUTTON(
                "Encerrar execução",
                *args,
                **kwargs,
            )
        )
        if not clicked:
            return False

        user = st.session_state.get("authenticated_user")
        package_id = str(st.session_state.get("selected_package_id", "") or "")
        user_id = str(getattr(user, "user_id", "") or "")
        if not user_id or not package_id:
            st.error("Não foi possível identificar a execução ativa.")
            return False
        try:
            terminate_paid_access(
                secrets=st.secrets,
                user_id=user_id,
                package_id=package_id,
                ending_code="user_abandoned",
            )
        except Exception as exc:
            st.error(f"Não foi possível encerrar a execução: {exc}")
            return False

        _clear_story_session(package_id, user_id)
        st.session_state.page = "library"
        st.session_state.selected_package_id = None
        st.switch_page("app.py")
        return False

    st.button = guarded_button  # type: ignore[method-assign]
    _BUTTON_POLICY_INSTALLED = True


def _redirect_pending_checkout() -> None:
    if (
        str(st.session_state.get("page", "") or "") == "checkout"
        and str(st.session_state.get("checkout_package_id", "") or "").strip()
    ):
        st.switch_page("pages/1_Pagamento_Pix.py")


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
        or "Uma presença que reage às suas escolhas e revela novas camadas ao longo da história.",
        "intention": story.profile_intention
        or "Construir uma relação própria com você sem antecipar os acontecimentos decisivos da trama.",
    }


def _render_flip_card(story: StoryCard) -> None:
    profile = _profile_from_card(story)
    label = "Degustação gratuita" if story.is_tasting else "História independente"
    cover_style = ""
    if story.cover_url:
        cover_style = f"--cover-image: url('{escape(story.cover_url, quote=True)}');"

    html = f"""
    <div class="story-flip-shell">
      <div class="story-flip-card" tabindex="0" role="button" aria-label="Virar card de {escape(story.title)}">
        <section class="story-face story-front" style="{cover_style}">
          <div class="story-kicker">{escape(label)}</div>
          <div class="story-title">{escape(story.title)}</div>
          <div class="story-subtitle">{escape(story.subtitle)}</div>
          <div class="story-meta">{escape(' • '.join(story.genres))} · {escape(story.chapter_label)}</div>
          <div class="story-flip-hint">↻ Passe o mouse ou toque para conhecer o personagem</div>
        </section>
        <section class="story-face story-back">
          <div class="story-profile-name">{escape(profile['name'])}</div>
          <div class="story-profile-section">
            <div class="story-profile-label">Quem é</div>
            <div class="story-profile-copy">{escape(profile['identity'])}</div>
          </div>
          <div class="story-profile-section">
            <div class="story-profile-label">Como é</div>
            <div class="story-profile-copy">{escape(profile['personality'])}</div>
          </div>
          <div class="story-profile-section">
            <div class="story-profile-label">O que pretende com você</div>
            <div class="story-profile-copy">{escape(profile['intention'])}</div>
          </div>
          <div class="story-back-hint">Role para continuar · toque fora do card para voltar à capa.</div>
        </section>
      </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_story_card(
    story: StoryCard,
    *,
    on_start: Callable[[str], None],
    on_continue: Callable[[str], None],
    on_restart: Callable[[str], None],
    on_buy: Callable[[str], None],
) -> None:
    del on_restart, on_buy
    _render_flip_card(story)

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
            _open_pix_checkout(story.package_id)
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
        _finish_and_restart_paid_story(story.package_id)


def inject_theme() -> None:
    GoogleSheetsAccountRepository.configure_paid_access_resolver(_paid_access_resolver)
    _install_sidebar_end_policy()
    _redirect_pending_checkout()
    _redirect_selected_player()
    st.markdown(CARD_CSS, unsafe_allow_html=True)


__all__ = ["CARD_CSS", "inject_theme", "render_story_card"]
