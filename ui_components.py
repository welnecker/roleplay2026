from __future__ import annotations

from collections.abc import Callable

import streamlit as st

from persistence.accounts import GoogleSheetsAccountRepository
from platform_core.models import AccessStatus, ProgressStatus, StoryCard
from services.paid_run_access import finish_active_run, get_paid_run_access


CARD_CSS = """
<style>
.block-container {max-width: 1180px; padding-top: 2rem;}
.story-kicker {color: #a1a1aa; font-size: .82rem; letter-spacing: .08em; text-transform: uppercase;}
.story-title {font-size: 1.45rem; font-weight: 750; margin: .25rem 0;}
.story-copy {color: #c9c9d2; min-height: 3.2rem;}
.story-meta {color: #a1a1aa; font-size: .88rem; margin-top: .6rem;}
.hero {padding: 1.4rem 0 1rem 0;}
.hero h1 {font-size: 2.5rem; margin-bottom: .3rem;}
[data-testid="stForm"] {border: 1px solid rgba(120,120,140,.25); border-radius: 18px; padding: 1.2rem;}
</style>
"""

_PILOT_PACKAGE_ID = "roleplay2026.casada_frustrada"
_ORIGINAL_BUTTON = st.button
_BUTTON_POLICY_INSTALLED = False


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


def _clear_story_session(package_id: str, user_id: str = "") -> None:
    st.session_state.story_states.pop(package_id, None)
    st.session_state.story_messages.pop(package_id, None)
    st.session_state.runtime_contexts.pop(package_id, None)
    st.session_state.started_packages.discard(package_id)
    st.session_state.restart_requests.discard(package_id)

    if user_id:
        prefix = f"pilot:{user_id}:{package_id}:"
        for key in list(st.session_state.keys()):
            if str(key).startswith(prefix):
                st.session_state.pop(key, None)


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
        finish_active_run(
            secrets=st.secrets,
            user_id=user_id,
            package_id=package_id,
            status="terminated",
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
            "será necessário realizar um novo pagamento."
        )
        clicked = bool(
            _ORIGINAL_BUTTON(
                "Encerrar execução e pagar novamente",
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
            finish_active_run(
                secrets=st.secrets,
                user_id=user_id,
                package_id=package_id,
                status="terminated",
                ending_code="user_abandoned",
            )
        except Exception as exc:
            st.error(f"Não foi possível encerrar a execução: {exc}")
            return False

        _send_to_new_payment(user_id=user_id, package_id=package_id)
        return False

    st.button = guarded_button  # type: ignore[method-assign]
    _BUTTON_POLICY_INSTALLED = True


def _redirect_pending_checkout() -> None:
    """Impede que a tela antiga de checkout do app principal seja renderizada."""

    if (
        str(st.session_state.get("page", "") or "") == "checkout"
        and str(st.session_state.get("checkout_package_id", "") or "").strip()
    ):
        st.switch_page("pages/1_Pagamento_Pix.py")


def _redirect_pilot_player() -> None:
    """Usa o player guiado apenas para o roteiro piloto de Casada frustrada."""

    if (
        str(st.session_state.get("page", "") or "") == "player"
        and str(st.session_state.get("selected_package_id", "") or "") == _PILOT_PACKAGE_ID
    ):
        st.switch_page("pages/2_Piloto_Supermercado.py")


def inject_theme() -> None:
    GoogleSheetsAccountRepository.configure_paid_access_resolver(_paid_access_resolver)
    _install_sidebar_end_policy()
    _redirect_pending_checkout()
    _redirect_pilot_player()
    st.markdown(CARD_CSS, unsafe_allow_html=True)


def _open_pix_checkout(package_id: str) -> None:
    st.session_state.checkout_package_id = package_id
    st.session_state.page = "checkout"
    st.switch_page("pages/1_Pagamento_Pix.py")


def render_story_card(
    story: StoryCard,
    *,
    on_start: Callable[[str], None],
    on_continue: Callable[[str], None],
    on_restart: Callable[[str], None],
    on_buy: Callable[[str], None],
) -> None:
    del on_restart, on_buy

    with st.container(border=True):
        label = "Degustação gratuita" if story.is_tasting else "História independente"
        st.markdown(f'<div class="story-kicker">{label}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="story-title">{story.title}</div>', unsafe_allow_html=True)
        st.caption(story.subtitle)
        st.markdown(f'<div class="story-copy">{story.description}</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="story-meta">{" • ".join(story.genres)} · {story.chapter_label}</div>',
            unsafe_allow_html=True,
        )

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

        if story.package_id == _PILOT_PACKAGE_ID and st.button(
            "Reiniciar — novo pagamento",
            key=f"restart-paid:{story.package_id}",
            use_container_width=True,
        ):
            _finish_and_restart_paid_story(story.package_id)
