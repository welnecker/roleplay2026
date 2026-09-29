from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from tkinter import messagebox, ttk

from core import EditorError, normalize_audio_name, slugify


def install_media_bridge(editor) -> None:
    button = editor._find_button("ATRIBUIR ÁUDIO À LINHA")
    if button is None:
        return
    button.configure(
        text="EDITAR ÁUDIO/MÍDIA DA LINHA",
        command=lambda: open_media_editor(editor),
        style="Big.TButton",
    )


def _media_editor_command(bridge_path: Path) -> list[str]:
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable).with_name("Editor_Midia_EntreCenas.exe")
        if not executable.is_file():
            raise EditorError(
                "Editor_Midia_EntreCenas.exe não foi encontrado ao lado do Editor de Roteiros."
            )
        return [str(executable), "--bridge", str(bridge_path)]

    media_app = Path(__file__).resolve().parents[1] / "media_timeline_editor" / "app.py"
    if not media_app.is_file():
        raise EditorError(f"Editor de mídia não encontrado: {media_app}")
    return [sys.executable, str(media_app), "--bridge", str(bridge_path)]


def _row_by_id(editor, line_id: str):
    for row in editor.rows:
        if str(row.get("line_id", "")) == line_id:
            return row
    return None


def _visual_source_for_line(editor, line_id: str) -> tuple[str, str]:
    inherited_image_id = ""
    for row in editor.rows:
        current_id = str(row.get("line_id", ""))
        image_id = str(
            row.get("image_id", "") or editor.image_map.get(current_id, "") or ""
        )
        if image_id:
            inherited_image_id = image_id
        if current_id != line_id:
            continue

        motion_id = str(
            row.get("motion_id", "") or editor.motion_map.get(current_id, "") or ""
        )
        if motion_id:
            source = str(editor.motion_sources.get(motion_id, "") or "")
            if source and Path(source).is_file():
                return source, "video"

        if inherited_image_id:
            source = str(editor.image_sources.get(inherited_image_id, "") or "")
            if source and Path(source).is_file():
                return source, "image"
        return "", ""
    return "", ""


def open_media_editor(editor) -> None:
    if not editor.rows and not editor.compile_current():
        return
    selection = editor.tree.selection()
    if not selection:
        messagebox.showinfo(
            "Editor de mídia",
            "Selecione a linha que receberá o áudio.",
        )
        return

    line_id = str(selection[0])
    row = _row_by_id(editor, line_id)
    if row is None:
        messagebox.showinfo(
            "Editor de mídia",
            "Selecione uma linha narrativa válida.",
        )
        return

    existing_audio_id = str(
        row.get("audio_id", "") or editor.audio_map.get(line_id, "") or ""
    )
    existing_audio_source = (
        str(editor.audio_sources.get(existing_audio_id, "") or "")
        if existing_audio_id
        else ""
    )

    if existing_audio_id:
        suggested_audio_id = existing_audio_id
    else:
        suggested_audio_id = normalize_audio_name(
            editor.image_prefix_var.get(),
            editor.next_audio_number(),
            Path("dialogo.mp3"),
        )

    visual_source, visual_kind = _visual_source_for_line(editor, line_id)
    package_slug = slugify(
        editor.package_var.get().split(".")[-1],
        "roteiro",
    )
    staging_dir = (
        Path.home()
        / "Documents"
        / "EntreCenas_Roteiros"
        / "media_staging"
        / package_slug
    )
    staging_dir.mkdir(parents=True, exist_ok=True)

    bridge_dir = Path(tempfile.mkdtemp(prefix="entrecenas_media_bridge_"))
    bridge_path = bridge_dir / "request.json"
    result_path = bridge_dir / "result.json"
    payload = {
        "version": 1,
        "line_id": line_id,
        "instruction": str(row.get("instruction", "") or ""),
        "suggested_audio_id": suggested_audio_id,
        "existing_audio_id": existing_audio_id,
        "audio_source": (
            existing_audio_source
            if existing_audio_source and Path(existing_audio_source).is_file()
            else ""
        ),
        "visual_source": visual_source,
        "visual_kind": visual_kind,
        "output_dir": str(staging_dir),
        "result_path": str(result_path),
    }
    bridge_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    try:
        process = subprocess.Popen(_media_editor_command(bridge_path))
    except Exception as exc:
        messagebox.showerror("Editor de mídia", str(exc))
        return

    editor.status_var.set(
        f"Editor de mídia aberto para {line_id}. Ao fechá-lo, o audio_id será atualizado."
    )
    editor.after(
        400,
        lambda: _poll_media_editor(editor, process, result_path, line_id),
    )


def _poll_media_editor(
    editor,
    process: subprocess.Popen,
    result_path: Path,
    line_id: str,
) -> None:
    if process.poll() is None:
        editor.after(
            400,
            lambda: _poll_media_editor(editor, process, result_path, line_id),
        )
        return

    if not result_path.is_file():
        editor.status_var.set(
            f"Editor de mídia fechado sem alteração em {line_id}."
        )
        return

    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
        audio_id = str(result.get("audio_id", "") or "").strip()
        audio_source = str(result.get("audio_source", "") or "").strip()
        if not audio_id or not audio_source or not Path(audio_source).is_file():
            raise EditorError("O editor de mídia não devolveu um áudio válido.")

        previous = str(editor.audio_map.get(line_id, "") or "")
        if previous and previous != audio_id:
            editor.audio_sources.pop(previous, None)
        editor.audio_map[line_id] = audio_id
        editor.audio_sources[audio_id] = audio_source

        if not editor.compile_current():
            raise EditorError("Não foi possível recompilar o roteiro com o novo áudio.")
        if editor.tree.exists(line_id):
            editor.tree.selection_set(line_id)
            editor.tree.see(line_id)
        editor.status_var.set(
            f"{line_id} → {audio_id} pré-salvo. Será incluído em Exportar Roteiro + Imagens."
        )
    except Exception as exc:
        messagebox.showerror("Editor de mídia", str(exc))
