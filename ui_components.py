from __future__ import annotations

from collections.abc import Callable
from html import escape

import streamlit as st

from persistence.accounts import GoogleSheetsAccountRepository
from platform_core.models import AccessStatus, ProgressStatus, StoryCard
from services.paid_run_access import get_paid_run_access, terminate_paid_access


CARD_CSS = """
<style>
:root {
    --rp-bg-0: #09070d;
    --rp-bg-1: #120c1a;
    --rp-bg-2: #241333;
    --rp-panel: rgba(24, 16, 34, .76);
    --rp-panel-strong: rgba(31, 20, 44, .94);
    --rp-border: rgba(206, 167, 255, .16);
    --rp-text: #f7f2ff;
    --rp-muted: #bbb1c8;
    --rp-purple: #bc8cff;
    --rp-purple-soft: #d9bdff;
}

html, body, [data-testid="stAppViewContainer"] {
    background:
        radial-gradient(circle at 82% 8%, rgba(116, 55, 170, .20), transparent 34%),
        radial-gradient(circle at 12% 82%, rgba(74, 35, 112, .16), transparent 38%),
        linear-gradient(145deg, var(--rp-bg-0) 0%, var(--rp-bg-1) 52%, var(--rp-bg-2) 100%);
    color: var(--rp-text);
}

[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(13, 9, 19, .98), rgba(30, 17, 43, .98));
    border-right: 1px solid var(--rp-border);
}

.block-container { max-width: 1180px; padding-top: 2rem; padding-bottom: 4rem; }
.hero { padding: 1.4rem 0 1rem 0; }
.hero h1 { font-size: 2.5rem; margin-bottom: .3rem; }
[data-testid="stForm"] {
    border: 1px solid var(--rp-border);
    border-radius: 20px;
    padding: 1.2rem;
    background: rgba(18, 12, 26, .58);
    box-shadow: 0 16px 44px rgba(0,0,0,.20);
}

[data-testid="stChatInput"] {
    background: rgba(16, 10, 24, .88);
    border: 1px solid rgba(190, 139, 255, .22);
    border-radius: 18px;
}

.dialogue-message {
    max-width: 860px;
    margin: 0 0 1rem 0;
    padding: 1rem 1.1rem;
    border-radius: 20px;
    border: 1px solid var(--rp-border);
    box-shadow: 0 12px 34px rgba(0,0,0,.18);
    backdrop-filter: blur(10px);
}
.dialogue-mary {
    background: linear-gradient(135deg, rgba(31, 20, 44, .86), rgba(20, 14, 29, .72));
    margin-right: 5%;
}
.dialogue-user {
    background: rgba(255,255,255,.045);
    margin-left: 9%;
}
.dialogue-speaker {
    color: var(--rp-purple-soft);
    font-size: .76rem;
    font-weight: 800;
    letter-spacing: .12em;
    text-transform: uppercase;
    margin-bottom: .65rem;
}
.dialogue-speech { color: var(--rp-text); font-size: 1rem; line-height: 1.75; }
.dialogue-speech p { margin: 0 0 .85rem 0; }
.dialogue-speech p:last-child { margin-bottom: 0; }

.mary-thought {
    position: relative;
    margin: .1rem 0 1rem 0;
    padding: .9rem 1rem .9rem 1.05rem;
    border-radius: 14px;
    border: 1px solid rgba(206, 167, 255, .20);
    border-left: 4px solid rgba(196, 139, 255, .92);
    background: linear-gradient(100deg, rgba(126, 66, 190, .25), rgba(84, 43, 125, .09));
    overflow: hidden;
}
.mary-thought::after {
    content: "";
    position: absolute;
    width: 90px;
    height: 90px;
    right: -34px;
    top: -40px;
    border-radius: 50%;
    background: rgba(203, 162, 255, .08);
}
.mary-thought-label {
    color: #d9bdff;
    font-size: .72rem;
    font-weight: 850;
    letter-spacing: .11em;
    text-transform: uppercase;
    margin-bottom: .42rem;
}
.mary-thought-label span { margin-right: .35rem; }
.mary-thought-copy {
    color: #eadcff;
    font-family: Georgia, "Times New Roman", serif;
    font-style: italic;
    line-height: 1.62;
}
.mary-thought-copy p { margin: 0 0 .55rem 0; }
.mary-thought-copy p:last-child { margin-bottom: 0; }

.story-flip-shell { perspective: 1200px; margin: .25rem 0 .8rem 0; }
.story-flip-card {
    position: relative;
    width: 100%;
    min-height: 410px;
    transform-style: preserve-3d;
    transition: transform .62s cubic-bezier(.2,.72,.2,1);
    outline: none;
}
.story-flip-shell:hover .story-flip-card,
.story-flip-card:focus,
.story-flip-card:focus-within { transform: rotateY(180deg); }
.story-face {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    padding: 1.25rem;
    border-radius: 22px;
    border: 1px solid rgba(206, 167, 255, .18);
    backface-visibility: hidden;
    -webkit-backface-visibility: hidden;
    overflow: hidden;
    box-shadow: 0 18px 44px rgba(0,0,0,.28);
}
.story-front {
    background:
        linear-gradient(180deg, rgba(8,6,12,.04) 10%, rgba(12,8,18,.92) 85%),
        var(--cover-image, linear-gradient(145deg, #29183a, #0c0911));
    background-size: cover;
    background-position: center;
}
.story-front::before {
    content: "";
    position: absolute;
    inset: 0;
    background: radial-gradient(circle at 80% 12%, rgba(202, 155, 255, .16), transparent 34%);
    pointer-events: none;
}
.story-back {
    transform: rotateY(180deg);
    justify-content: flex-start;
    background: linear-gradient(145deg, rgba(35, 21, 50, .98), rgba(12, 9, 17, .99));
}
.story-kicker { color: #c5a2ef; font-size: .76rem; letter-spacing: .10em; text-transform: uppercase; }
.story-title { color: #fff; font-size: 1.55rem; font-weight: 800; margin: .35rem 0; }
.story-subtitle { color: #dfd5e9; line-height: 1.5; }
.story-meta { color: #b6a9c4; font-size: .84rem; margin-top: .8rem; }
.story-flip-hint {
    margin-top: .85rem;
    color: #d2b5f6;
    font-size: .8rem;
    letter-spacing: .04em;
}
.story-profile-name { color: #fff; font-size: 1.45rem; font-weight: 850; margin-bottom: .9rem; }
.story-profile-section { margin-bottom: .8rem; }
.story-profile-label {
    color: #cda8fb;
    font-size: .70rem;
    font-weight: 850;
    letter-spacing: .11em;
    text-transform: uppercase;
    margin-bottom: .25rem;
}
.story-profile-copy { color: #e5dce9; font-size: .92rem; line-height: 1.48; }
.story-back-hint { margin-top: auto; color: #9f91ac; font-size: .76rem; }

@media (max-width: 760px) {
    .block-container { padding-left: 1rem; padding-right: 1rem; }
    .dialogue-mary, .dialogue-user { margin-left: 0; margin-right: 0; }
    .story-flip-card { min-height: 440px; }
}
</style>
"""

_PILOT_PACKAGE_ID = "roleplay2026.casada_frustrada"
_ORIGINAL_BUTTON = st.button
_BUTTON_POLICY_INSTALLED = False

_CHARACTER_PROFILES: dict[str, dict[str, str]] = {
    _PILOT_PACKAGE_ID: {
        "name": "Mary",
        "identity": (
            "Mary é uma mulher adulta, casada e emocionalmente inquieta. Sua rotina já não acompanha "
            "tudo o que ela sente e deseja viver."
        ),
        "personality": (
            "Espontânea, sensual, curiosa e bem-humorada. Costuma esconder insegurança, desejo e "
            "expectativa atrás de provocações e conversas aparentemente inocentes."
        ),
        "intention": (
            "Ela quer descobrir até onde pode confiar em você e se existe espaço para cumplicidade, "
            "atenção e uma conexão mais íntima — sem revelar tudo de uma vez."
        ),
    }
}


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
    st.session_state.pop(f"pix_order:{package_id}", None)
    st.session_state.pop(f"pix_qr_base64:{package_id}", None)
    st.session_state.pop("payment_access_ready", None)

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
            terminate_paid_access(
                secrets=st.secrets,
                user_id=user_id,
                package_id=package_id,
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
    if (
        str(st.session_state.get("page", "") or "") == "checkout"
        and str(st.session_state.get("checkout_package_id", "") or "").strip()
    ):
        st.switch_page("pages/1_Pagamento_Pix.py")


def _redirect_pilot_player() -> None:
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
    st.session_state.pop(f"pix_order:{package_id}", None)
    st.session_state.pop(f"pix_qr_base64:{package_id}", None)
    st.session_state.checkout_package_id = package_id
    st.session_state.page = "checkout"
    st.switch_page("pages/1_Pagamento_Pix.py")


def _character_profile(story: StoryCard) -> dict[str, str]:
    profile = _CHARACTER_PROFILES.get(story.package_id)
    if profile is not None:
        return profile
    return {
        "name": story.title,
        "identity": story.description,
        "personality": "Uma presença construída para reagir às suas escolhas e revelar novas camadas ao longo da história.",
        "intention": "Conduzir uma relação própria com você sem antecipar os acontecimentos decisivos da trama.",
    }


def _render_flip_card(story: StoryCard) -> None:
    profile = _character_profile(story)
    label = "Degustação gratuita" if story.is_tasting else "História independente"
    cover_style = ""
    if story.cover_url:
        safe_url = escape(story.cover_url, quote=True)
        cover_style = f"--cover-image: url('{safe_url}');"

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
          <div class="story-back-hint">Toque fora do card para voltar à capa.</div>
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

    if story.package_id == _PILOT_PACKAGE_ID and st.button(
        "Reiniciar — novo pagamento",
        key=f"restart-paid:{story.package_id}",
        use_container_width=True,
    ):
        _finish_and_restart_paid_story(story.package_id)
