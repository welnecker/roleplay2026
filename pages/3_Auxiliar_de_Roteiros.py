from __future__ import annotations

from html import escape
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from platform_core.auth import AuthenticatedUser
from services.script_authoring import (
    ScriptAuthoringError,
    clear_authoring_state,
    compile_draft_rows,
    rows_to_csv,
    rows_to_tsv,
    slugify,
    synchronized_package_id,
)
from services.script_authoring_v2 import compile_v2_rows, preview_v2_frames
from services.pwa import install_pwa_metadata


st.set_page_config(page_title="Auxiliar de Roteiros", page_icon="📝", layout="wide")
install_pwa_metadata()

DRAFT_KEY = "script_authoring_draft"
ROWS_KEY = "script_authoring_rows"
STORY_TITLE_KEY = "script_authoring_story_title"
PACKAGE_ID_KEY = "script_authoring_package_id"
PACKAGE_SUGGESTION_KEY = "script_authoring_package_suggestion"
AUTHORING_MODE_KEY = "script_authoring_mode"
ACTORS_KEY = "script_authoring_v2_actors"
SELECTED_ACTOR_KEY = "script_authoring_v2_selected_actor"

LEGACY_TAG_BUTTONS = (
    ("Cena", "[CENA {block_id}] ", "Abre um bloco narrativo."),
    ("Beat", "[BEAT] ", "Define o acontecimento obrigatório."),
    ("Pensamento", "[PENSAMENTO] ", "Pensamento interno da personagem."),
    ("Pensamento interpretado", "[PENSAMENTO INTERPRETADO] ", "Núcleo psicológico desenvolvido pelo modelo."),
    ("Fala exata", "[FALA EXATA] ", "Texto autoral literal."),
    ("Fala", "[FALA] ", "Fala canônica da personagem."),
    ("Fala interpretada", "[FALA INTERPRETADA] ", "Fala livre que preserva o núcleo autoral."),
    ("Fala exata íntima", "[FALA EXATA INTIMA] ", "Fala literal em etapa íntima autorizada."),
    ("Fala livre", "[FALA LIVRE] ", "Orienta o modelo sem fixar cada palavra."),
    ("Ponte", "[PONTE] ", "Orienta a reação dentro do beat."),
    ("Transição", "[TRANSIÇÃO] ", "Introduz tempo ou local antes do próximo beat."),
    ("Pátio final", "[PÁTIO FINAL despedida] ", "Abre o encerramento normal."),
    ("Pátio decisão", "[PÁTIO DECISÃO decisao_id] ", "Abre uma decisão vinculada ao beat anterior."),
    ("Aceite", "[ACEITE] ", "Critério semântico binário para avançar."),
    ("Prosseguir", "[PROSSEGUIR] ", "Mensagem sugerida enviada como fala normal do usuário."),
    ("Tentar a sorte", "[TENTAR A SORTE] ", "Aviso exibido antes do campo livre."),
    ("Aviso", "[AVISO] ", "Resposta após o primeiro não aceite."),
    ("Encerramento", "[ENCERRAMENTO codigo] ", "Fala final após o segundo não aceite."),
    ("Fim", "[FIM story_complete] ", "Encerra a run."),
)

V2_PALETTE = ("#ED8BAE", "#F1B5CB", "#F0CFDD", "#F3D5E6")


def _authenticated_user() -> AuthenticatedUser | None:
    value = st.session_state.get("authenticated_user")
    return value if isinstance(value, AuthenticatedUser) else None


def _admin_emails(secrets: Any) -> set[str]:
    raw = secrets.get("SCRIPT_EDITOR_ADMIN_EMAILS", "")
    if isinstance(raw, str):
        values = raw.replace(";", ",").split(",")
    elif isinstance(raw, (list, tuple, set)):
        values = list(raw)
    else:
        values = []
    return {str(value).strip().casefold() for value in values if str(value).strip()}


def _clear_draft() -> None:
    clear_authoring_state(st.session_state, draft_key=DRAFT_KEY, rows_key=ROWS_KEY)


def _sync_package_id_from_title() -> None:
    package_id, suggestion = synchronized_package_id(
        st.session_state.get(STORY_TITLE_KEY, ""),
        st.session_state.get(PACKAGE_ID_KEY, ""),
        st.session_state.get(PACKAGE_SUGGESTION_KEY, ""),
    )
    st.session_state[PACKAGE_ID_KEY] = package_id
    st.session_state[PACKAGE_SUGGESTION_KEY] = suggestion


def _append_text(text: str) -> None:
    current = str(st.session_state.get(DRAFT_KEY, "") or "").rstrip()
    st.session_state[DRAFT_KEY] = (current + "\n\n" + text).lstrip()
    st.session_state.pop(ROWS_KEY, None)


def _append_legacy_tag(template: str, block_id: str) -> None:
    _append_text(template.format(block_id=block_id.strip() or "novo_bloco"))


def _append_v2_tag(kind: str, actor: str = "") -> None:
    if kind == "DESCRIÇÃO":
        _append_text("[DESCRIÇÃO] ")
        return
    clean_actor = slugify(actor, fallback="usuario")
    _append_text(f"[{kind} {clean_actor}] ")


def _actor_options(raw: str) -> list[str]:
    result: list[str] = []
    for value in str(raw or "").replace(";", ",").split(","):
        actor = slugify(value.strip(), fallback="")
        if actor and actor not in result:
            result.append(actor)
    if "usuario" not in result:
        result.append("usuario")
    return result or ["usuario"]


def _render_name_placeholder_button() -> None:
    components.html(
        """
        <style>
          html, body { margin:0; padding:0; background:transparent; }
          .buttons { display:grid; grid-template-columns:repeat(3,1fr); gap:.4rem; }
          .copy-name { width:100%; min-height:40px; padding:.55rem .5rem;
            border:1px solid #D24369; border-radius:.6rem; background:#D24369;
            color:white; font:600 14px sans-serif; cursor:pointer; }
          .copy-name.copied { background:#237a57; border-color:#45b789; }
        </style>
        <div class="buttons">
          <button class="copy-name" type="button" data-token="{{nome}}">Copiar {{nome}}</button>
          <button class="copy-name" type="button" data-token="{{*nome}}">Copiar {{*nome}}</button>
          <button class="copy-name" type="button" data-token="{{**nome}}">Copiar {{**nome}}</button>
        </div>
        <script>
          document.querySelectorAll('.copy-name').forEach((button) => {
            button.addEventListener('click', () => {
              const token=button.dataset.token;
              const helper=document.createElement('textarea');
              helper.value=token; helper.style.position='fixed'; helper.style.left='-9999px';
              document.body.appendChild(helper); helper.focus(); helper.select();
              let copied=false; try { copied=document.execCommand('copy'); } catch(e) {}
              if(!copied && navigator.clipboard){ navigator.clipboard.writeText(token).catch(()=>{}); }
              helper.remove(); const original=button.textContent;
              button.textContent='Copiado ✓'; button.classList.add('copied');
              setTimeout(()=>{button.textContent=original;button.classList.remove('copied');},1400);
            });
          });
        </script>
        """,
        height=44,
    )


def _render_v2_preview(draft: str, frame_prefix: str, start_frame_number: int) -> None:
    source = str(draft or "").strip()
    if not source:
        return
    try:
        frames = preview_v2_frames(
            source,
            frame_prefix=frame_prefix,
            start_frame_number=int(start_frame_number),
        )
    except ScriptAuthoringError:
        return

    with st.expander("Prévia estrutural dos quadros", expanded=False):
        st.caption("Prévia do roteiro autoral. O modelo ainda não interpretou as falas.")
        for frame in frames:
            st.markdown(f"**{escape(frame.frame_id)}**")
            st.markdown(
                '<div style="padding:.8rem 1rem;border-radius:14px;background:#D24369;color:white;'
                'font-family:Comic Sans MS,Comic Sans,Chalkboard SE,Marker Felt,Segoe Print,cursive;">'
                '<strong style="font-size:.75rem;">CENA</strong><br>'
                f'{escape(frame.description)}</div>',
                unsafe_allow_html=True,
            )
            entries = list(frame.entries)
            for offset in range(0, len(entries), 4):
                chunk = entries[offset : offset + 4]
                columns = st.columns(4)
                for position, entry in enumerate(chunk):
                    with columns[position]:
                        color = V2_PALETTE[(offset + position) % 4]
                        label = (
                            f"✦ pensamento · {entry.actor}"
                            if entry.kind == "PENSAMENTO"
                            else (
                                f"fala exata · {entry.actor}"
                                if entry.delivery == "exata"
                                else (
                                    f"fala interpretada · {entry.actor}"
                                    if entry.delivery == "interpretada"
                                    else entry.actor
                                )
                            )
                        )
                        style = "font-style:italic;" if entry.kind == "PENSAMENTO" else ""
                        border = "2px dotted rgba(70,36,52,.35)" if entry.kind == "PENSAMENTO" else "1px solid rgba(70,36,52,.20)"
                        st.markdown(
                            f'<div style="min-height:110px;padding:.75rem;border-radius:16px;background:{color};'
                            f'color:#2B1822;border:{border};font-family:Comic Sans MS,Comic Sans,Chalkboard SE,Marker Felt,Segoe Print,cursive;">'
                            f'<strong style="font-size:.72rem;">{escape(label)}</strong><br>'
                            f'<span style="{style}">{escape(entry.text)}</span></div>',
                            unsafe_allow_html=True,
                        )
            st.divider()


def _render_legacy_controls(block_id: str) -> None:
    st.subheader("Inserir tag — modo legado")
    button_columns = st.columns(5)
    for index, (label, template, description) in enumerate(LEGACY_TAG_BUTTONS):
        with button_columns[index % len(button_columns)]:
            if st.button(
                label,
                key=f"script_tag:{label}",
                help=description,
                width="stretch",
            ):
                _append_legacy_tag(template, block_id)
                st.rerun()


user = _authenticated_user()
if user is None:
    st.error("Entre na sua conta antes de acessar o auxiliar de roteiros.")
    if st.button("Voltar ao início"):
        st.switch_page("app.py")
    st.stop()

allowed_emails = _admin_emails(st.secrets)
if not allowed_emails:
    st.error("O auxiliar está bloqueado até que SCRIPT_EDITOR_ADMIN_EMAILS seja configurado nos Secrets.")
    st.code('SCRIPT_EDITOR_ADMIN_EMAILS = ["seu-email@dominio.com"]', language="toml")
    st.stop()
if user.email.strip().casefold() not in allowed_emails:
    st.error("Sua conta não possui permissão para acessar o auxiliar de roteiros.")
    st.stop()

st.title("Auxiliar de Roteiros")
st.caption("Crie roteiros V2 multipersonagem ou mantenha roteiros legados; exportação continua pronta para a aba ROTEIROS.")

st.session_state.setdefault(DRAFT_KEY, "")
st.session_state.setdefault(PACKAGE_ID_KEY, "")
st.session_state.setdefault(PACKAGE_SUGGESTION_KEY, "")
st.session_state.setdefault(ACTORS_KEY, "camilly, usuario")

authoring_mode = st.radio(
    "Modo de roteiro",
    ("V2 — Visual novel / multipersonagem", "Legado — Beats e pátios"),
    key=AUTHORING_MODE_KEY,
    horizontal=True,
)
is_v2 = authoring_mode.startswith("V2")

operation = st.radio(
    "Operação",
    ("Criar nova história", "Criar ou refazer bloco/quadro de uma história"),
    horizontal=True,
)

left, right = st.columns(2)
with left:
    st.text_input(
        "Nome da história",
        key=STORY_TITLE_KEY,
        placeholder="Ex.: Encontro com Camilly",
        disabled=operation != "Criar nova história",
        on_change=_sync_package_id_from_title,
    )
    package_id = st.text_input(
        "package_id",
        key=PACKAGE_ID_KEY,
        placeholder="roleplay2026.nome_da_historia",
        help="Identifica a história e o card.",
    )
with right:
    script_version = st.text_input("script_version", value="200" if is_v2 else "1.0.0")
    block_id = st.text_input(
        "Prefixo dos quadros" if is_v2 else "block_id",
        value="encontro" if is_v2 else "primeiro_encontro",
        help=(
            "V2: gera encontro_001, encontro_002... e seus line_id."
            if is_v2
            else "Identifica o bloco/cena legado."
        ),
    )

order_col, interval_col, frame_col = st.columns(3)
with order_col:
    start_order = st.number_input("Primeira order", min_value=0, value=10, step=10)
with interval_col:
    order_step = st.number_input("Intervalo", min_value=1, value=10, step=1)
with frame_col:
    start_frame_number = st.number_input(
        "Primeiro nº do quadro",
        min_value=1,
        value=1,
        step=1,
        disabled=not is_v2,
    )

if is_v2:
    st.subheader("Personagens e ações")
    actors_raw = st.text_input(
        "Personagens do roteiro",
        key=ACTORS_KEY,
        help="Separe por vírgulas. 'usuario' é reservado ao protagonista e é sempre disponibilizado.",
        placeholder="camilly, usuario, renan",
    )
    actors = _actor_options(actors_raw)
    if st.session_state.get(SELECTED_ACTOR_KEY) not in actors:
        st.session_state[SELECTED_ACTOR_KEY] = actors[0]

    actor_col, description_col, speech_col, exact_col, interpreted_col, thought_col = st.columns([2, 1, 1, 1, 1, 1])
    with actor_col:
        selected_actor = st.selectbox("Ator", actors, key=SELECTED_ACTOR_KEY)
    with description_col:
        st.write("")
        st.write("")
        if st.button("+ Novo quadro", width="stretch", type="secondary"):
            _append_v2_tag("DESCRIÇÃO")
            st.rerun()
    with speech_col:
        st.write("")
        st.write("")
        if st.button("+ Fala", width="stretch"):
            _append_v2_tag("FALA", selected_actor)
            st.rerun()
    with exact_col:
        st.write("")
        st.write("")
        if st.button("+ Fala exata", width="stretch"):
            _append_v2_tag("FALA EXATA", selected_actor)
            st.rerun()
    with interpreted_col:
        st.write("")
        st.write("")
        if st.button("+ Fala interpretada", width="stretch"):
            _append_v2_tag("FALA INTERPRETADA", selected_actor)
            st.rerun()
    with thought_col:
        st.write("")
        st.write("")
        if st.button("+ Pensamento", width="stretch"):
            _append_v2_tag("PENSAMENTO", selected_actor)
            st.rerun()

    st.info(
        "Cada [DESCRIÇÃO] abre um novo quadro. Use [FALA EXATA ator] para texto literal, "
        "[FALA ator] para ajustes mínimos e [FALA INTERPRETADA ator] para desenvolvimento do núcleo autoral. "
        "Falas e pensamentos seguem a order da planilha. "
        "Você pode repetir o mesmo personagem quantas vezes quiser dentro do quadro."
    )
else:
    _render_legacy_controls(block_id)

name_button, name_help = st.columns([3, 2])
with name_button:
    _render_name_placeholder_button()
with name_help:
    st.caption(
        "{{nome}} usa o nome; {{*nome}} usa o/a + nome; "
        "{{**nome}} usa ele/ela. No tratamento neutro, os três usam somente o nome."
    )

placeholder = (
    "[DESCRIÇÃO] Camilly e {{nome}} chegam à praia e encontram Renan.\n\n"
    "[FALA camilly] Eu cumprimento Renan com surpresa.\n\n"
    "[FALA renan] Eu respondo naturalmente e observo quem está com ela.\n\n"
    "[PENSAMENTO usuario] A reação dos dois parece mais íntima do que esperava.\n\n"
    "[FALA usuario] Eu me apresento a Renan com naturalidade."
    if is_v2
    else (
        "[CENA primeiro_encontro] Eu encontro o usuário.\n\n"
        "[BEAT] Eu inicio a conversa.\n\n"
        "[PENSAMENTO] Quero descobrir como ele reage.\n\n"
        "[FALA EXATA] Oi, {{nome}}... que bom ter você aqui."
    )
)

draft = st.text_area("Roteiro", key=DRAFT_KEY, height=470, placeholder=placeholder)

if is_v2:
    _render_v2_preview(draft, block_id, int(start_frame_number))

generate_column, clear_column = st.columns([3, 1])
with generate_column:
    generate = st.button("Validar e gerar", type="primary", width="stretch")
with clear_column:
    st.button("Limpar", width="stretch", on_click=_clear_draft)

if generate:
    try:
        if is_v2:
            st.session_state[ROWS_KEY] = compile_v2_rows(
                draft,
                package_id=package_id,
                script_version=script_version,
                frame_prefix=block_id,
                start_order=int(start_order),
                order_step=int(order_step),
                start_frame_number=int(start_frame_number),
            )
        else:
            st.session_state[ROWS_KEY] = compile_draft_rows(
                draft,
                package_id=package_id,
                script_version=script_version,
                initial_block_id=block_id,
                start_order=int(start_order),
                order_step=int(order_step),
            )
    except ScriptAuthoringError as exc:
        st.session_state.pop(ROWS_KEY, None)
        st.error("O roteiro precisa de correções:")
        for message in str(exc).splitlines():
            st.write(f"- {message}")
    else:
        st.success("Roteiro validado e convertido para a estrutura da aba ROTEIROS.")

rows = st.session_state.get(ROWS_KEY)
if isinstance(rows, list) and rows:
    st.subheader("Prévia das linhas")
    st.dataframe(rows, width="stretch", hide_index=True)

    tsv = rows_to_tsv(rows)
    csv_text = rows_to_csv(rows)
    filename_base = f"{package_id.replace('.', '_')}_{script_version}"

    download_tsv, download_csv = st.columns(2)
    with download_tsv:
        st.download_button(
            "Baixar TSV para colar na planilha",
            data=tsv.encode("utf-8"),
            file_name=f"{filename_base}.tsv",
            mime="text/tab-separated-values",
            width="stretch",
            type="primary",
        )
    with download_csv:
        st.download_button(
            "Baixar CSV de segurança",
            data=csv_text.encode("utf-8"),
            file_name=f"{filename_base}.csv",
            mime="text/csv",
            width="stretch",
        )

    with st.expander("Copiar manualmente para a aba ROTEIROS"):
        st.caption("Copie o conteúdo tabulado e cole na primeira célula da área de destino.")
        st.code(tsv, language=None)

if st.button("Voltar aos cards"):
    st.switch_page("app.py")
