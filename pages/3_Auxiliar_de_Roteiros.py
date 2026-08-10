from __future__ import annotations

from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from platform_core.auth import AuthenticatedUser
from services.script_authoring import (
    ScriptAuthoringError,
    compile_draft_rows,
    package_id_from_title,
    rows_to_csv,
    rows_to_tsv,
)


st.set_page_config(page_title="Auxiliar de Roteiros", page_icon="📝", layout="wide")

DRAFT_KEY = "script_authoring_draft"
ROWS_KEY = "script_authoring_rows"
_TAG_BUTTONS = (
    ("Cena", "[CENA {block_id}] "),
    ("Beat", "[BEAT] "),
    ("Pensamento", "[PENSAMENTO] "),
    ("Fala exata", "[FALA EXATA] "),
    ("Fala", "[FALA] "),
    ("Fala livre", "[FALA LIVRE] "),
    ("Ponte", "[PONTE] "),
    ("Transição", "[TRANSIÇÃO] "),
    ("Pátio final", "[PÁTIO FINAL despedida] "),
    ("Fim", "[FIM story_complete] "),
)


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


def _append_tag(template: str, block_id: str) -> None:
    current = str(st.session_state.get(DRAFT_KEY, "") or "").rstrip()
    tag = template.format(block_id=block_id.strip() or "novo_bloco")
    st.session_state[DRAFT_KEY] = (current + "\n\n" + tag).lstrip()
    st.session_state.pop(ROWS_KEY, None)


def _clear_draft() -> None:
    st.session_state[DRAFT_KEY] = ""
    st.session_state.pop(ROWS_KEY, None)


def _render_name_placeholder_button() -> None:
    components.html(
        """
        <style>
          html, body { margin: 0; padding: 0; background: transparent; }
          #copy-name {
            width: 100%;
            min-height: 40px;
            padding: 0.55rem 0.75rem;
            border: 1px solid #9b6cff;
            border-radius: 0.5rem;
            background: #6f3fc5;
            color: #ffffff;
            font: 600 14px sans-serif;
            cursor: pointer;
          }
          #copy-name:hover { background: #8251db; }
          #copy-name:active { transform: translateY(1px); }
          #copy-name.copied { background: #237a57; border-color: #45b789; }
        </style>
        <textarea id="copy-helper" aria-hidden="true"
          style="position:fixed;left:-9999px;top:-9999px;">{{nome}}</textarea>
        <button id="copy-name" type="button" onclick="copyName()">Copiar {{nome}}</button>
        <script>
          function copyName() {
            const button = document.getElementById("copy-name");
            const helper = document.getElementById("copy-helper");
            helper.focus();
            helper.select();
            helper.setSelectionRange(0, helper.value.length);
            let copied = false;
            try {
              copied = document.execCommand("copy");
            } catch (error) {
              copied = false;
            }
            if (!copied && navigator.clipboard && navigator.clipboard.writeText) {
              navigator.clipboard.writeText(helper.value).catch(() => {});
            }
            button.textContent = "Copiado ✓";
            button.classList.add("copied");
            setTimeout(() => {
              button.textContent = "Copiar {{nome}}";
              button.classList.remove("copied");
            }, 1600);
          }
        </script>
        """,
        height=44,
    )

user = _authenticated_user()
if user is None:
    st.error("Entre na sua conta antes de acessar o auxiliar de roteiros.")
    if st.button("Voltar ao início"):
        st.switch_page("app.py")
    st.stop()

allowed_emails = _admin_emails(st.secrets)
if not allowed_emails:
    st.error(
        "O auxiliar está bloqueado até que SCRIPT_EDITOR_ADMIN_EMAILS seja "
        "configurado nos Secrets do Streamlit."
    )
    st.code('SCRIPT_EDITOR_ADMIN_EMAILS = ["seu-email@dominio.com"]', language="toml")
    st.stop()
if user.email.strip().casefold() not in allowed_emails:
    st.error("Sua conta não possui permissão para acessar o auxiliar de roteiros.")
    st.stop()

st.title("Auxiliar de Roteiros")
st.caption(
    "Produza o roteiro autoral, valide a estrutura e exporte linhas prontas "
    "para a aba ROTEIROS. Esta página não altera a planilha automaticamente."
)

st.session_state.setdefault(DRAFT_KEY, "")
mode = st.radio(
    "Operação",
    ("Criar nova história", "Criar ou refazer bloco de uma história"),
    horizontal=True,
)

left, right = st.columns(2)
with left:
    story_title = st.text_input(
        "Nome da história",
        placeholder="Ex.: Encontro com Camilly",
        disabled=mode != "Criar nova história",
    )
    suggested_package = package_id_from_title(story_title) if story_title else ""
    package_id = st.text_input(
        "package_id",
        value=suggested_package,
        placeholder="roleplay2026.nome_da_historia",
        help="Identifica a história e o card. Não identifica o bloco.",
    )
with right:
    script_version = st.text_input("script_version", value="1.0.0")
    block_id = st.text_input(
        "block_id",
        value="primeiro_encontro",
        help="Identifica o bloco/cena. Os line_id serão gerados automaticamente.",
    )

order_col, interval_col, action_col = st.columns([1, 1, 2])
with order_col:
    start_order = st.number_input("Primeira order", min_value=0, value=10, step=10)
with interval_col:
    order_step = st.number_input("Intervalo", min_value=1, value=10, step=1)
with action_col:
    st.write("")
    st.write("")
    if st.button("Preparar bloco", use_container_width=True):
        if not str(st.session_state.get(DRAFT_KEY, "") or "").strip():
            st.session_state[DRAFT_KEY] = f"[CENA {block_id or 'novo_bloco'}] "
        st.rerun()

st.subheader("Inserir tag")
button_columns = st.columns(5)
for index, (label, template) in enumerate(_TAG_BUTTONS):
    with button_columns[index % len(button_columns)]:
        if st.button(label, key=f"script_tag:{label}", use_container_width=True):
            _append_tag(template, block_id)
            st.rerun()

name_button, name_help = st.columns([1, 4])
with name_button:
    _render_name_placeholder_button()
with name_help:
    st.caption(
        "Posicione o cursor dentro do roteiro e cole para inserir o nome do usuário "
        "em qualquer fala ou pensamento."
    )

with st.expander("Tags direcionadas por tratamento ou anatomia"):
    st.info(
        "Todos os pensamentos e falas abaixo pertencem à personagem. "
        "O complemento HOMEM, MULHER ou NEUTRA escolhe qual variante será usada "
        "conforme o tratamento selecionado pelo usuário."
    )
    directed = (
        (
            "Pensamento para homem",
            "[PENSAMENTO HOMEM] ",
            "Pensamento interno da personagem quando o usuário escolheu “Como homem”. "
            "Ex.: [PENSAMENTO HOMEM] Humm... gostei do jeito dele.",
        ),
        (
            "Pensamento para mulher",
            "[PENSAMENTO MULHER] ",
            "Pensamento interno da personagem quando o usuário escolheu “Como mulher”. "
            "Ex.: [PENSAMENTO MULHER] Humm... gostei do jeito dela.",
        ),
        (
            "Pensamento neutro",
            "[PENSAMENTO NEUTRA] ",
            "Pensamento interno da personagem para tratamento neutro. "
            "Ex.: [PENSAMENTO NEUTRA] Humm... gostei dessa aproximação.",
        ),
        (
            "Fala para homem",
            "[FALA EXATA HOMEM] ",
            "Fala da personagem dirigida ao usuário tratado como homem. "
            "Ex.: [FALA EXATA HOMEM] Oi, {{nome}}... meu lindo.",
        ),
        (
            "Fala para mulher",
            "[FALA EXATA MULHER] ",
            "Fala da personagem dirigida ao usuário tratado como mulher. "
            "Ex.: [FALA EXATA MULHER] Oi, {{nome}}... minha linda.",
        ),
        (
            "Fala neutra",
            "[FALA EXATA NEUTRA] ",
            "Fala da personagem sem flexão masculina ou feminina. "
            "Ex.: [FALA EXATA NEUTRA] Oi, {{nome}}... que prazer.",
        ),
        (
            "Pensamento — corpo masculino",
            "[PENSAMENTO CORPO_MASCULINO] ",
            "Pensamento da personagem usado somente quando o usuário informou anatomia masculina. "
            "Use quando o conteúdo depende da anatomia, não apenas do tratamento.",
        ),
        (
            "Pensamento — corpo feminino",
            "[PENSAMENTO CORPO_FEMININO] ",
            "Pensamento da personagem usado somente quando o usuário informou anatomia feminina. "
            "Use quando o conteúdo depende da anatomia, não apenas do tratamento.",
        ),
        (
            "Pensamento — corpo intersexo",
            "[PENSAMENTO CORPO_INTERSEXO] ",
            "Pensamento da personagem usado somente quando o usuário informou anatomia intersexo. "
            "Use quando o conteúdo depende da anatomia, não apenas do tratamento.",
        ),
    )
    directed_columns = st.columns(3)
    for index, (label, template, description) in enumerate(directed):
        with directed_columns[index % 3]:
            if st.button(
                label,
                key=f"script_directed:{label}",
                help=description,
                use_container_width=True,
            ):
                _append_tag(template, block_id)
                st.rerun()

draft = st.text_area(
    "Roteiro",
    key=DRAFT_KEY,
    height=460,
    placeholder=(
        "[CENA primeiro_encontro] Eu encontro o usuário.\n\n"
        "[BEAT] Eu inicio a conversa.\n\n"
        "[PENSAMENTO] Quero descobrir como ele reage.\n\n"
        "[FALA EXATA] Oi, {{nome}}... que bom ter você aqui."
    ),
)

generate_column, clear_column = st.columns([3, 1])
with generate_column:
    generate = st.button("Validar e gerar", type="primary", use_container_width=True)
with clear_column:
    st.button(
        "Limpar",
        use_container_width=True,
        on_click=_clear_draft,
    )

if generate:
    try:
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
    st.dataframe(rows, use_container_width=True, hide_index=True)

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
            use_container_width=True,
            type="primary",
        )
    with download_csv:
        st.download_button(
            "Baixar CSV de segurança",
            data=csv_text.encode("utf-8"),
            file_name=f"{filename_base}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with st.expander("Copiar manualmente para a aba ROTEIROS"):
        st.caption(
            "O conteúdo abaixo usa tabulações. Copie tudo e cole na primeira célula "
            "da área de destino da planilha."
        )
        st.code(tsv, language=None)

if st.button("Voltar aos cards"):
    st.switch_page("app.py")
