from __future__ import annotations

import json
import threading
from pathlib import Path
from tkinter import messagebox, ttk

from core import MediaEditorError, export_audio_clip
from PIL import Image, ImageTk


_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}


def install_bridge(editor, bridge_path: Path) -> None:
    context = json.loads(Path(bridge_path).read_text(encoding="utf-8"))
    editor._bridge_context = context
    editor._bridge_committed = False

    line_id = str(context.get("line_id", "") or "")
    instruction = str(context.get("instruction", "") or "")
    suggested = str(context.get("suggested_audio_id", "") or "audio.mp3")

    bar = ttk.Frame(editor, padding=(14, 5, 14, 10))
    bar.pack(fill="x")
    ttk.Label(
        bar,
        text=f"LINHA DO ROTEIRO: {line_id}  •  {instruction[:100]}",
    ).pack(side="left", fill="x", expand=True)
    ttk.Button(
        bar,
        text="USAR TRECHO NESTA LINHA E FECHAR",
        style="Accent.TButton",
        command=lambda: commit_bridge_audio(editor),
    ).pack(side="right", padx=(10, 0))

    editor.protocol("WM_DELETE_WINDOW", lambda: close_bridge(editor))
    editor.after(150, lambda: _load_bridge_context(editor, context))

    suggested_stem = Path(suggested).stem
    if suggested_stem:
        editor.name_var.set(suggested_stem.replace("_audio", ""))


def _load_bridge_context(editor, context: dict) -> None:
    visual_source = str(context.get("visual_source", "") or "").strip()
    audio_source = str(context.get("audio_source", "") or "").strip()

    if visual_source and Path(visual_source).is_file():
        source = Path(visual_source)
        suffix = source.suffix.lower()
        if suffix in _VIDEO_EXTENSIONS:
            editor.stop_preview()
            editor.video_path = source
            editor.image_path = None
            editor.status_var.set("Carregando a mídia da linha selecionada...")
            threading.Thread(
                target=editor._load_video_worker,
                args=(source,),
                daemon=True,
            ).start()
        elif suffix in _IMAGE_EXTENSIONS:
            _load_image(editor, source)

    if audio_source and Path(audio_source).is_file():
        editor.audio_path = Path(audio_source)
        try:
            editor._configure_audio(editor.audio_path)
            editor.status_var.set(
                "Áudio já vinculado carregado. Edite o trecho e feche para devolver ao roteiro."
            )
        except Exception as exc:
            editor._error(exc)
    elif not visual_source:
        editor.status_var.set(
            "Linha aberta pelo Editor de Roteiros. Clique em ABRIR ÁUDIO para carregar o diálogo."
        )


def _load_image(editor, source: Path) -> None:
    editor.stop_preview()
    editor.image_path = source
    editor.video_path = None
    editor.media_info = None
    editor.visual_duration = 0.0
    editor.precision_frames = [source]
    duration = editor.audio_info.duration if editor.audio_info is not None else 10.0
    editor.media_duration = max(0.2, duration)
    editor.frame_scale.configure(to=0)
    editor.frame_entry.configure(to=1)
    editor.start_scale.configure(to=editor.media_duration)
    editor.end_scale.configure(to=editor.media_duration)
    editor.start_var.set(0.0)
    editor.end_var.set(editor.media_duration)
    with Image.open(source) as image:
        width, height = image.size
    editor.source_label.configure(
        text=f"Imagem da linha: {source}  •  {width}×{height}  •  "
        f"timeline {editor.media_duration:.3f}s"
    )
    editor._draw_timeline()
    editor.set_frame(0)
    editor._selection_changed()
    editor._draw_waveform()


def commit_bridge_audio(editor, *, quiet: bool = False) -> bool:
    context = getattr(editor, "_bridge_context", None)
    if not context:
        return False

    try:
        source = editor._audio_source()
        segment = editor._selected_audio_segment()
        audio_id = str(context.get("suggested_audio_id", "") or "").strip()
        output_dir = Path(str(context.get("output_dir", "") or ""))
        result_path = Path(str(context.get("result_path", "") or ""))
        if not audio_id or not output_dir or not result_path:
            raise MediaEditorError("O vínculo com o Editor de Roteiros está incompleto.")

        output_dir.mkdir(parents=True, exist_ok=True)
        destination = output_dir / audio_id
        export_audio_clip(
            source,
            destination,
            start=segment.source_start,
            end=segment.source_end,
            volume=float(editor.volume_var.get()),
            fade_in_ms=int(editor.fade_in_var.get()),
            fade_out_ms=int(editor.fade_out_var.get()),
        )
        result = {
            "version": 1,
            "line_id": str(context.get("line_id", "") or ""),
            "audio_id": audio_id,
            "audio_source": str(destination),
            "duration": segment.duration,
            "source_start": segment.source_start,
            "source_end": segment.source_end,
            "timeline_start": segment.timeline_start,
        }
        result_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = result_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(result_path)
        editor._bridge_committed = True
        if not quiet:
            messagebox.showinfo(
                "Áudio vinculado",
                f"{audio_id} foi pré-salvo para a linha do roteiro.",
            )
        editor._close()
        return True
    except Exception as exc:
        if not quiet:
            editor._error(exc)
        return False


def close_bridge(editor) -> None:
    if getattr(editor, "_bridge_committed", False):
        editor._close()
        return

    context = getattr(editor, "_bridge_context", None)
    if context and editor.audio_info is not None and editor.audio_segments:
        if commit_bridge_audio(editor, quiet=True):
            return

    editor._close()
