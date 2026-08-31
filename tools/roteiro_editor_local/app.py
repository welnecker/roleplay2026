from __future__ import annotations

import io
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.script_authoring import ScriptAuthoringError
from services.script_authoring_v2 import compile_v2_rows
from tools.roteiro_editor_local.core import (
    OFFICIAL_COLUMNS,
    allocate_image_ids,
    build_export_rows,
    default_image_prefix,
    rows_to_csv_text,
    rows_to_tsv_text,
    rows_to_xlsx_bytes,
    save_export_bundle,
)

st.set_page_config(page_title="Editor Local de Roteiros V2", page_icon="🎬", layout="wide")

DRAFT_KEY = "local_editor:draft"
ROWS_KEY = "local_editor:rows"
IMAGES_KEY = "local_editor:images"
IMAGE_NAMES_KEY = "local_editor:image_names"
ACTORS_KEY = "local_editor:actors"
PACKAGE_KEY = "local_editor:package"
VERSION_KEY = "local_editor:version"
PREFIX_KEY = "local_editor:frame_prefix"
IMAGE_PREFIX_KEY = "local_editor:image_prefix"
OUTPUT_KEY = "local_editor:output"


def _append_tag(tag: str) -> None:
    current = str(st.session_state.get(DRAFT_KEY, "") or "").rstrip()
    st.session_state[DRAFT_KEY] = (current + "\n\n" + tag).lstrip()
    st.session_state.pop(ROWS_KEY, None)


def _actors(raw: str) -> list[str]:
    values: list[str] = []
    for part in str(raw or "").replace(";", ",").split(","):
        actor = "_".join(part.strip().casefold().split())
        if actor and actor not in values:
            values.append(actor)
    if "usuario" not in values:
        values.append("usuario")
    return values or ["usuario"]


def _is_description(row: dict[str, object]) -> bool:
    return str(row.get("instruction", "") or "").lstrip().startswith("[DESCRIÇÃO]")


def _short(text: object, limit: int = 78) -> str:
    value = " ".join(str(text or "").split())
    return value if len(value) <= limit else value[: limit - 1] + "…"


def _compile() -> None:
    try:
        rows = compile_v2_rows(
            st.session_state.get(DRAFT_KEY, ""),
            package_id=st.session_state.get(PACKAGE_KEY, ""),
            script_version=st.session_state.get(VERSION_KEY, ""),
            frame_prefix=st.session_state.get(PREFIX_KEY, "quadro"),
            start_order=int(st.session_state.get("local_editor:start_order", 10)),
            order_step=int(st.session_state.get("local_editor:order_step", 10)),
            start_frame_number=int(st.session_state.get("local_editor:start_frame", 1)),
        )
    except ScriptAuthoringError as exc:
        st.session_state.pop(ROWS_KEY, None)
        st.error("O roteiro precisa de correções:")
        for line in str(exc).splitlines():
            st.write(f"- {line}")
        return
    st.session_state[ROWS_KEY] = rows
    valid_ids = {str(row.get("line_id", "")) for row in rows}
    st.session_state[IMAGES_KEY] = {
        key: value
        for key, value in dict(st.session_state.get(IMAGES_KEY, {})).items()
        if key in valid_ids
    }
    st.session_state[IMAGE_NAMES_KEY] = {
        key: value
        for key, value in dict(st.session_state.get(IMAGE_NAMES_KEY, {})).items()
        if key in valid_ids
    }
    st.success("Estrutura V2 atualizada. line_id e order foram gerados pelo compilador oficial.")


st.session_state.setdefault(DRAFT_KEY, "")
st.session_state.setdefault(ROWS_KEY, [])
st.session_state.setdefault(IMAGES_KEY, {})
st.session_state.setdefault(IMAGE_NAMES_KEY, {})
st.session_state.setdefault(ACTORS_KEY, "camilly, usuario")
st.session_state.setdefault(PACKAGE_KEY, "roleplay2026.camilly")
st.session_state.setdefault(VERSION_KEY, "200")
st.session_state.setdefault(PREFIX_KEY, "encontro")
st.session_state.setdefault(IMAGE_PREFIX_KEY, "camilly")
st.session_state.setdefault(
    OUTPUT_KEY,
    str(Path.home() / "Documents" / "Roleplay2026_Editor" / "camilly"),
)

st.title("🎬 Editor Local de Roteiros V2")
st.caption(
    "Ferramenta autoral local. Prepara imagens WebP e as sete colunas oficiais da aba ROTEIROS; "
    "não publica nada no GitHub nem no Google Sheets."
)

with st.expander("1. Configuração do roteiro", expanded=True):
    c1, c2, c3 = st.columns(3)
    with c1:
        package_id = st.text_input("package_id", key=PACKAGE_KEY)
        script_version = st.text_input("script_version", key=VERSION_KEY)
    with c2:
        frame_prefix = st.text_input("Prefixo dos quadros", key=PREFIX_KEY, help="Ex.: encontro → encontro_001")
        actors_raw = st.text_input("Personagens", key=ACTORS_KEY, help="Separe por vírgulas. usuario é sempre incluído.")
    with c3:
        st.number_input("Primeira order", min_value=0, step=10, value=10, key="local_editor:start_order")
        st.number_input("Intervalo da order", min_value=1, step=1, value=10, key="local_editor:order_step")
        st.number_input("Primeiro nº do quadro", min_value=1, step=1, value=1, key="local_editor:start_frame")

    suggested_prefix = default_image_prefix(package_id)
    if not str(st.session_state.get(IMAGE_PREFIX_KEY, "") or "").strip():
        st.session_state[IMAGE_PREFIX_KEY] = suggested_prefix

actors = _actors(actors_raw)

st.subheader("2. Escrever roteiro")
actor_col, desc_col, fala_col, pensamento_col = st.columns([2.3, 1, 1, 1])
with actor_col:
    selected_actor = st.selectbox("Ator para a próxima tag", actors)
with desc_col:
    st.write("")
    st.write("")
    if st.button("+ DESCRIÇÃO", width="stretch"):
        _append_tag("[DESCRIÇÃO] ")
        st.rerun()
with fala_col:
    st.write("")
    st.write("")
    if st.button("+ FALA", width="stretch"):
        _append_tag(f"[FALA {selected_actor}] ")
        st.rerun()
with pensamento_col:
    st.write("")
    st.write("")
    if st.button("+ PENSAMENTO", width="stretch"):
        _append_tag(f"[PENSAMENTO {selected_actor}] ")
        st.rerun()

name_col, article_col, pronoun_col, name_help_col = st.columns([1, 1, 1, 2.3])
for column, token in (
    (name_col, "{{nome}}"),
    (article_col, "{{*nome}}"),
    (pronoun_col, "{{**nome}}"),
):
    with column:
        if st.button(f"+ {token}", width="stretch"):
            current = str(st.session_state.get(DRAFT_KEY, "") or "")
            st.session_state[DRAFT_KEY] = current + token
            st.rerun()
with name_help_col:
    st.caption("nome · o/a + nome · ele/ela; no neutro, somente o nome")

st.text_area(
    "Roteiro",
    key=DRAFT_KEY,
    height=430,
    placeholder=(
        "[DESCRIÇÃO] Camilly se aproxima do carro.\n\n"
        "[FALA camilly] Oi, {{nome}}...\n\n"
        "[PENSAMENTO camilly] Eu observo a reação dele."
    ),
)

compile_col, clear_col = st.columns([4, 1])
with compile_col:
    if st.button("Validar e atualizar estrutura", type="primary", width="stretch"):
        _compile()
with clear_col:
    if st.button("Limpar tudo", width="stretch"):
        for key in (DRAFT_KEY, ROWS_KEY, IMAGES_KEY, IMAGE_NAMES_KEY):
            st.session_state.pop(key, None)
        st.rerun()

rows = st.session_state.get(ROWS_KEY)
if not isinstance(rows, list) or not rows:
    st.stop()

st.subheader("3. Linhas geradas")
preview_rows = build_export_rows(rows)
st.dataframe(preview_rows, width="stretch", hide_index=True, column_order=list(OFFICIAL_COLUMNS))

st.subheader("4. Imagens")
st.caption(
    "Por padrão, atribua imagens às [DESCRIÇÃO]. Se quiser uma troca visual em uma fala/pensamento, "
    "ative a opção abaixo e atribua a imagem diretamente àquela linha."
)

images: dict[str, bytes] = dict(st.session_state.get(IMAGES_KEY, {}))
image_names: dict[str, str] = dict(st.session_state.get(IMAGE_NAMES_KEY, {}))

description_rows = [row for row in rows if _is_description(row)]
unassigned_descriptions = [
    row for row in description_rows if str(row.get("line_id", "")) not in images
]

batch_files = st.file_uploader(
    "Importar várias imagens e atribuir em sequência às próximas [DESCRIÇÃO] sem imagem",
    type=["png", "jpg", "jpeg", "webp", "bmp"],
    accept_multiple_files=True,
    key="local_editor:batch_upload",
)
if batch_files:
    st.caption(
        f"{len(batch_files)} imagem(ns) selecionada(s); "
        f"{len(unassigned_descriptions)} descrição(ões) ainda sem imagem."
    )
    if st.button("Atribuir lote às DESCRIÇÕES", type="secondary"):
        for row, uploaded in zip(unassigned_descriptions, batch_files):
            line_id = str(row.get("line_id", ""))
            images[line_id] = uploaded.getvalue()
            image_names[line_id] = uploaded.name
        st.session_state[IMAGES_KEY] = images
        st.session_state[IMAGE_NAMES_KEY] = image_names
        st.success("Imagens do lote atribuídas na ordem das DESCRIÇÕES.")
        st.rerun()

allow_dialogue_images = st.checkbox(
    "Permitir imagem também em [FALA] e [PENSAMENTO]",
    value=False,
)
eligible_rows = rows if allow_dialogue_images else description_rows
options = [str(row.get("line_id", "")) for row in eligible_rows]
row_by_id = {str(row.get("line_id", "")): row for row in rows}

if options:
    selected_line = st.selectbox(
        "Linha para atribuição individual",
        options,
        format_func=lambda line_id: f"{line_id} — {_short(row_by_id[line_id].get('instruction'))}",
    )
    left, right = st.columns([2, 1])
    with left:
        uploaded = st.file_uploader(
            "Escolher imagem para esta linha",
            type=["png", "jpg", "jpeg", "webp", "bmp"],
            key=f"local_editor:single:{selected_line}",
        )
        if uploaded is not None:
            images[selected_line] = uploaded.getvalue()
            image_names[selected_line] = uploaded.name
            st.session_state[IMAGES_KEY] = images
            st.session_state[IMAGE_NAMES_KEY] = image_names
            st.success(f"Imagem atribuída a {selected_line}.")
    with right:
        if selected_line in images:
            st.image(images[selected_line], caption=image_names.get(selected_line, selected_line), width="stretch")
            if st.button("Remover imagem desta linha", key=f"remove:{selected_line}", width="stretch"):
                images.pop(selected_line, None)
                image_names.pop(selected_line, None)
                st.session_state[IMAGES_KEY] = images
                st.session_state[IMAGE_NAMES_KEY] = image_names
                st.rerun()

st.markdown("##### Numeração e formato de saída")
i1, i2, i3 = st.columns(3)
with i1:
    image_prefix = st.text_input("Prefixo das imagens", key=IMAGE_PREFIX_KEY, help="Ex.: camilly → camilly1.webp")
with i2:
    image_start_number = st.number_input("Primeiro número da imagem", min_value=1, value=1, step=1)
with i3:
    quality = st.slider("Qualidade WebP", min_value=60, max_value=100, value=88, step=1)
max_dimension = st.select_slider(
    "Maior dimensão máxima da imagem",
    options=[960, 1200, 1440, 1600, 1920, 2560],
    value=1600,
    help="A proporção é preservada; imagens menores não são ampliadas.",
)

planned_image_ids = allocate_image_ids(
    rows,
    images.keys(),
    prefix=image_prefix,
    start_number=int(image_start_number),
)
export_rows = build_export_rows(rows, planned_image_ids)

if planned_image_ids:
    assignment_preview = [
        {
            "line_id": line_id,
            "arquivo_original": image_names.get(line_id, ""),
            "image_id": image_id,
            "instruction": row_by_id[line_id].get("instruction", ""),
        }
        for line_id, image_id in planned_image_ids.items()
    ]
    st.dataframe(assignment_preview, width="stretch", hide_index=True)
else:
    st.info("Nenhuma imagem atribuída ainda. O roteiro pode ser exportado mesmo assim.")

st.subheader("5. Exportar")
st.caption("O cabeçalho exportado é exatamente: package_id, script_version, line_id, order, instruction, status, image_id.")

xlsx_bytes = rows_to_xlsx_bytes(export_rows)
csv_text = rows_to_csv_text(export_rows)
tsv_text = rows_to_tsv_text(export_rows)
filename_base = f"{str(package_id).replace('.', '_')}_{script_version}"

d1, d2, d3 = st.columns(3)
with d1:
    st.download_button(
        "Baixar Excel (.xlsx)",
        data=xlsx_bytes,
        file_name=f"{filename_base}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
        type="primary",
    )
with d2:
    st.download_button(
        "Baixar TSV",
        data=tsv_text.encode("utf-8"),
        file_name=f"{filename_base}.tsv",
        mime="text/tab-separated-values",
        width="stretch",
    )
with d3:
    st.download_button(
        "Baixar CSV",
        data=csv_text.encode("utf-8-sig"),
        file_name=f"{filename_base}.csv",
        mime="text/csv",
        width="stretch",
    )

st.markdown("##### Salvar pacote completo no PC")
output_dir = st.text_input(
    "Pasta de saída",
    key=OUTPUT_KEY,
    help="O editor criará roteiro.xlsx, roteiro.csv, roteiro.tsv, projeto_roteiro.json e a subpasta imagens.",
)
overwrite = st.checkbox("Permitir sobrescrever arquivos já existentes nessa pasta", value=False)

if st.button("Salvar roteiro + imagens na pasta", type="primary", width="stretch"):
    meta = {
        "draft": st.session_state.get(DRAFT_KEY, ""),
        "package_id": package_id,
        "script_version": script_version,
        "frame_prefix": frame_prefix,
        "actors": actors_raw,
        "start_order": int(st.session_state.get("local_editor:start_order", 10)),
        "order_step": int(st.session_state.get("local_editor:order_step", 10)),
        "start_frame_number": int(st.session_state.get("local_editor:start_frame", 1)),
        "image_prefix": image_prefix,
        "image_start_number": int(image_start_number),
        "quality": int(quality),
        "max_dimension": int(max_dimension),
        "source_image_names": image_names,
    }
    try:
        result = save_export_bundle(
            output_dir,
            rows,
            images,
            image_prefix=image_prefix,
            image_start_number=int(image_start_number),
            quality=int(quality),
            max_dimension=int(max_dimension),
            project_meta=meta,
            overwrite=overwrite,
        )
    except Exception as exc:
        st.error(f"Não foi possível salvar o pacote: {exc}")
    else:
        st.success(f"Pacote salvo em: {result['root']}")
        st.code(
            "\n".join(
                [
                    str(result["xlsx"]),
                    str(result["csv"]),
                    str(result["tsv"]),
                    str(result["images_dir"]),
                    str(result["project"]),
                ]
            ),
            language=None,
        )
