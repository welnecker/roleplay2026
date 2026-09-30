from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from core import (
    AudioSegment,
    MediaEditorError,
    copy_image_to_clipboard,
    create_audio_segment,
    export_audio_clip,
    export_audio_segments,
    export_synchronized_clip,
    export_synchronized_segment,
    extract_frame_at_index,
    extract_precision_frames,
    ffmpeg_executable,
    frame_time,
    load_media_editor_settings,
    move_audio_segment,
    probe_media,
    rename_audio_segments,
    save_media_editor_settings,
    split_audio_segment,
    trim_audio_segment,
    waveform_peaks,
)
from PIL import Image, ImageTk
from bridge import install_bridge

PROFILES = {
    "Leve": (8, 58, 854),
    "Equilibrado": (10, 65, 960),
    "Alta qualidade": (12, 75, 1280),
    "Personalizado": None,
}


class MediaTimelineEditor(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Editor de Mídia EntreCenas — Timeline precisa")
        self.geometry("1380x1040")
        self.minsize(1080, 820)
        self.configure(bg="#183D3A")
        self.video_path: Path | None = None
        self.image_path: Path | None = None
        self.audio_path: Path | None = None
        self.audio_info = None
        self.media_info = None
        self.media_duration = 1.0
        self.visual_duration = 1.0
        self.precision_frames: list[Path] = []
        self.timeline_images: list[ImageTk.PhotoImage] = []
        self.current_photo: ImageTk.PhotoImage | None = None
        self.wave_peaks: list[float] = []
        self.preview_images: list[ImageTk.PhotoImage] = []
        self.preview_durations: list[int] = []
        self.preview_job: str | None = None
        self.preview_index = 0
        self.privacy_hidden = True
        self.folder_settings = load_media_editor_settings()
        self.audio_drag_x = 0
        self.audio_drag_offset = 0
        self.audio_segments: list[AudioSegment] = []
        self.segment_history: list[list[AudioSegment]] = []
        self.selected_segment = -1
        self.segment_drag_origin = 0.0
        self.playhead_time = 0.0
        self.workspace = Path(tempfile.mkdtemp(prefix="entrecenas_timeline_"))
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._build()
        self.bind("<Left>", lambda _event: self.step_frame(-1))
        self.bind("<Right>", lambda _event: self.step_frame(1))
        self.bind("<Shift-Left>", lambda _event: self.step_frame(-10))
        self.bind("<Shift-Right>", lambda _event: self.step_frame(10))

    def _build(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#183D3A")
        style.configure("TLabel", background="#183D3A", foreground="#FFFFFF")
        style.configure("TLabelframe", background="#183D3A", foreground="#FFFFFF")
        style.configure("TLabelframe.Label", background="#183D3A", foreground="#FFFFFF")
        style.configure("Title.TLabel", font=("Segoe UI", 17, "bold"))
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))

        top = ttk.Frame(self, padding=12)
        top.pack(fill="x")
        ttk.Label(top, text="Editor de Mídia EntreCenas", style="Title.TLabel").pack(
            side="left"
        )
        ttk.Button(top, text="ABRIR VÍDEO", command=self.open_video).pack(
            side="left", padx=(20, 5)
        )
        ttk.Button(top, text="ABRIR IMAGEM", command=self.open_image).pack(
            side="left", padx=5
        )
        ttk.Button(top, text="ABRIR ÁUDIO", command=self.open_audio).pack(
            side="left", padx=5
        )
        ttk.Button(top, text="ÁUDIO DO VÍDEO", command=self.use_video_audio).pack(
            side="left", padx=5
        )
        self.privacy_button = ttk.Button(
            top,
            text="MOSTRAR MÍDIA",
            command=self.toggle_privacy,
        )
        self.privacy_button.pack(side="left", padx=(14, 5))
        ttk.Button(
            top, text="EXPORTAR", style="Accent.TButton", command=self.export
        ).pack(side="right", padx=5)
        ttk.Button(top, text="PRÉVIA SINCRONIZADA", command=self.preview).pack(
            side="right", padx=5
        )

        self.source_label = ttk.Label(
            self, text="Abra um vídeo MP4 para começar.", padding=(14, 0)
        )
        self.source_label.pack(fill="x")

        viewer = ttk.Frame(self, padding=(12, 8))
        viewer.pack(fill="both", expand=True)
        self.preview_label = tk.Label(
            viewer,
            text="VISUALIZADOR DE FRAMES",
            bg="#102F2D",
            fg="#D6E5E3",
            font=("Segoe UI", 14, "bold"),
            anchor="center",
        )
        self.preview_label.pack(fill="both", expand=True)
        self.privacy_mask = tk.Label(
            viewer,
            text="MÍDIA OCULTA\n\nClique em MOSTRAR MÍDIA para visualizar",
            bg="#0B1F1E",
            fg="#FFFFFF",
            font=("Segoe UI", 18, "bold"),
            anchor="center",
            justify="center",
        )
        self.privacy_mask.place(relx=0, rely=0, relwidth=1, relheight=1)

        transport = ttk.Frame(self, padding=(12, 0, 12, 8))
        transport.pack(fill="x")
        ttk.Button(
            transport, text="|◀", width=5, command=lambda: self.set_frame(0)
        ).pack(side="left", padx=2)
        ttk.Button(
            transport, text="◀ 10", width=6, command=lambda: self.step_frame(-10)
        ).pack(side="left", padx=2)
        ttk.Button(
            transport, text="◀ 1 FRAME", command=lambda: self.step_frame(-1)
        ).pack(side="left", padx=2)
        ttk.Button(
            transport, text="1 FRAME ▶", command=lambda: self.step_frame(1)
        ).pack(side="left", padx=2)
        ttk.Button(
            transport, text="10 ▶", width=6, command=lambda: self.step_frame(10)
        ).pack(side="left", padx=2)
        ttk.Button(transport, text="▶|", width=5, command=self.last_frame).pack(
            side="left", padx=2
        )
        self.frame_label = ttk.Label(
            transport, text="Frame: —   Tempo: 00:00.000", font=("Segoe UI", 10, "bold")
        )
        self.frame_label.pack(side="left", padx=14)
        ttk.Button(transport, text="COPIAR FRAME", command=self.copy_frame).pack(
            side="right", padx=3
        )
        ttk.Button(transport, text="SALVAR FRAME", command=self.save_frame).pack(
            side="right", padx=3
        )

        frame_row = ttk.Frame(self, padding=(12, 0, 12, 8))
        frame_row.pack(fill="x")
        self.frame_var = tk.DoubleVar(value=0)
        self.frame_scale = ttk.Scale(
            frame_row,
            variable=self.frame_var,
            from_=0,
            to=1,
            command=self._frame_slider_changed,
        )
        self.frame_scale.pack(side="left", fill="x", expand=True)
        ttk.Label(frame_row, text="Ir ao frame:").pack(side="left", padx=(10, 4))
        self.frame_entry_var = tk.StringVar(value="1")
        self.frame_entry = ttk.Spinbox(
            frame_row,
            from_=1,
            to=1,
            width=9,
            textvariable=self.frame_entry_var,
            command=self.go_to_typed_frame,
        )
        self.frame_entry.pack(side="left")
        self.frame_entry.bind("<Return>", lambda _event: self.go_to_typed_frame())

        timeline_box = ttk.LabelFrame(
            self,
            text=" TIMELINE VISUAL — clique para posicionar o playhead ",
            padding=7,
        )
        timeline_box.pack(fill="x", padx=12, pady=(0, 6))
        self.timeline_canvas = tk.Canvas(
            timeline_box, height=94, bg="#102F2D", highlightthickness=0, cursor="hand2"
        )
        self.timeline_canvas.pack(fill="x")
        self.timeline_canvas.bind("<Button-1>", self._timeline_clicked)

        selectors = ttk.Frame(timeline_box)
        selectors.pack(fill="x", pady=(5, 0))
        self.start_var = tk.DoubleVar(value=0.0)
        self.end_var = tk.DoubleVar(value=1.0)
        ttk.Button(selectors, text="MARCAR INÍCIO", command=self.mark_start).grid(
            row=0, column=0, rowspan=2, padx=(0, 6)
        )
        ttk.Label(selectors, text="Início").grid(row=0, column=1)
        self.start_scale = ttk.Scale(
            selectors,
            variable=self.start_var,
            from_=0,
            to=1,
            command=self._selection_changed,
        )
        self.start_scale.grid(row=0, column=2, sticky="ew", padx=6)
        self.start_text = ttk.Label(selectors, text="00:00.000", width=12)
        self.start_text.grid(row=0, column=3)
        ttk.Label(selectors, text="Fim").grid(row=1, column=1)
        self.end_scale = ttk.Scale(
            selectors,
            variable=self.end_var,
            from_=0,
            to=1,
            command=self._selection_changed,
        )
        self.end_scale.grid(row=1, column=2, sticky="ew", padx=6)
        self.end_text = ttk.Label(selectors, text="00:01.000", width=12)
        self.end_text.grid(row=1, column=3)
        ttk.Button(selectors, text="MARCAR FIM", command=self.mark_end).grid(
            row=0, column=4, rowspan=2, padx=(6, 0)
        )
        selectors.columnconfigure(2, weight=1)

        audio_box = ttk.LabelFrame(
            self, text=" PISTA DE ÁUDIO SINCRONIZADA ", padding=7
        )
        audio_box.pack(fill="x", padx=12, pady=(0, 7))
        self.wave_canvas = tk.Canvas(
            audio_box, height=68, bg="#241A22", highlightthickness=0
        )
        self.wave_canvas.pack(fill="x")
        self.wave_canvas.bind("<Button-1>", self._audio_clicked)
        self.wave_canvas.bind("<B1-Motion>", self._audio_drag_move)
        self.wave_canvas.bind("<ButtonRelease-1>", self._audio_drag_end)
        audio_controls = ttk.Frame(audio_box)
        audio_controls.pack(fill="x", pady=(4, 0))
        self.audio_label = ttk.Label(
            audio_controls, text="Áudio: faixa original do vídeo, quando existir."
        )
        self.audio_label.pack(side="left")
        ttk.Button(
            audio_controls,
            text="EXPORTAR TODOS",
            command=self.export_all_audio_segments,
        ).pack(side="right", padx=2)
        ttk.Button(
            audio_controls,
            text="EXPORTAR SELECIONADO",
            command=self.export_selected_audio,
        ).pack(side="right", padx=2)
        ttk.Button(
            audio_controls, text="OUVIR TRECHO", command=self.play_selected_audio
        ).pack(side="right", padx=2)

        segment_controls = ttk.Frame(audio_box)
        segment_controls.pack(fill="x", pady=(5, 0))
        ttk.Button(
            segment_controls, text="CORTAR NO CURSOR", command=self.split_at_playhead
        ).pack(side="left", padx=2)
        ttk.Button(
            segment_controls,
            text="INÍCIO = CURSOR",
            command=self.trim_start_to_playhead,
        ).pack(side="left", padx=2)
        ttk.Button(
            segment_controls, text="FIM = CURSOR", command=self.trim_end_to_playhead
        ).pack(side="left", padx=2)
        ttk.Button(
            segment_controls, text="EXCLUIR BLOCO", command=self.delete_selected_segment
        ).pack(side="left", padx=2)
        ttk.Button(segment_controls, text="DESFAZER", command=self.undo_segments).pack(
            side="left", padx=2
        )
        ttk.Label(
            segment_controls, text="Arraste o bloco colorido para sincronizar."
        ).pack(side="right", padx=5)

        self.segment_table = ttk.Treeview(
            audio_box,
            columns=("name", "source", "position", "duration"),
            show="headings",
            height=3,
            selectmode="browse",
        )
        self.segment_table.heading("name", text="Nome do arquivo")
        self.segment_table.heading("source", text="Trecho no áudio original")
        self.segment_table.heading("position", text="Posição na timeline")
        self.segment_table.heading("duration", text="Duração")
        self.segment_table.column("name", width=260)
        self.segment_table.column("source", width=250)
        self.segment_table.column("position", width=150)
        self.segment_table.column("duration", width=130)
        self.segment_table.pack(fill="x", pady=(5, 0))
        self.segment_table.bind("<<TreeviewSelect>>", self._segment_table_selected)

        options = ttk.Frame(self, padding=(12, 0, 12, 8))
        options.pack(fill="x")
        self.name_var = tk.StringVar(value="cena1")
        self.profile_var = tk.StringVar(value="Equilibrado")
        self.fps_var = tk.IntVar(value=10)
        self.quality_var = tk.IntVar(value=65)
        self.size_var = tk.IntVar(value=960)
        self.offset_var = tk.IntVar(value=0)
        self.volume_var = tk.DoubleVar(value=1.0)
        self.fade_in_var = tk.IntVar(value=0)
        self.fade_out_var = tk.IntVar(value=250)

        profile_cell = ttk.Frame(options)
        profile_cell.grid(row=0, column=0, padx=4, sticky="ew")
        ttk.Label(profile_cell, text="Perfil").pack(anchor="w")
        profile = ttk.Combobox(
            profile_cell,
            state="readonly",
            textvariable=self.profile_var,
            values=list(PROFILES),
            width=15,
        )
        profile.pack(fill="x")
        profile.bind("<<ComboboxSelected>>", self._profile_changed)

        fields = [
            ("Nome", self.name_var, 15),
            ("FPS", self.fps_var, 6),
            ("Qualidade", self.quality_var, 7),
            ("Máx. px", self.size_var, 8),
            ("Posição bloco ms", self.offset_var, 10),
            ("Volume", self.volume_var, 7),
            ("Fade-in ms", self.fade_in_var, 8),
            ("Fade-out ms", self.fade_out_var, 8),
        ]
        for column, (label, variable, width) in enumerate(fields, start=1):
            cell = ttk.Frame(options)
            cell.grid(row=0, column=column, padx=4, sticky="ew")
            ttk.Label(cell, text=label).pack(anchor="w")
            entry = ttk.Entry(cell, textvariable=variable, width=width)
            entry.pack(fill="x")
            if any(
                variable is item
                for item in (self.fps_var, self.quality_var, self.size_var)
            ):
                entry.bind(
                    "<KeyRelease>", lambda _event: self.profile_var.set("Personalizado")
                )
            if variable is self.offset_var:
                entry.bind("<KeyRelease>", self._offset_entry_changed)
            options.columnconfigure(column, weight=1)

        self.status_var = tk.StringVar(
            value="Pronto. Use ← e → para caminhar frame por frame."
        )
        ttk.Label(self, textvariable=self.status_var, padding=(14, 0, 14, 9)).pack(
            fill="x"
        )

    def _dialog_dir(self, key: str) -> str:
        value = str(self.folder_settings.get(key, "") or "").strip()
        if value and Path(value).is_dir():
            return value
        return str(Path.home())

    def _remember_dir(self, key: str, path: Path) -> None:
        folder = path if path.is_dir() else path.parent
        if folder.is_dir():
            self.folder_settings[key] = str(folder)
            save_media_editor_settings(self.folder_settings)

    def toggle_privacy(self) -> None:
        self.privacy_hidden = not self.privacy_hidden
        if self.privacy_hidden:
            self.privacy_mask.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.privacy_button.configure(text="MOSTRAR MÍDIA")
        else:
            self.privacy_mask.place_forget()
            self.privacy_button.configure(text="OCULTAR MÍDIA")
        if self.precision_frames:
            self._draw_timeline()
        self.status_var.set(
            "Privacidade ativada: mídia oculta."
            if self.privacy_hidden
            else "Mídia visível temporariamente."
        )

    @staticmethod
    def _clock(value: float) -> str:
        minutes, seconds = divmod(max(0.0, value), 60)
        return f"{int(minutes):02d}:{seconds:06.3f}"

    def _profile_changed(self, _event=None) -> None:
        values = PROFILES.get(self.profile_var.get())
        if values:
            self.fps_var.set(values[0])
            self.quality_var.set(values[1])
            self.size_var.set(values[2])
            self.status_var.set(f"Perfil {self.profile_var.get()} aplicado.")

    def open_video(self) -> None:
        selected = filedialog.askopenfilename(
            title="Abrir vídeo",
            initialdir=self._dialog_dir("last_open_dir"),
            filetypes=[("Vídeos", "*.mp4 *.mov *.mkv *.webm"), ("Todos", "*.*")],
        )
        if not selected:
            return
        self.stop_preview()
        self.video_path = Path(selected)
        self._remember_dir("last_open_dir", self.video_path)
        self.image_path = None
        self.status_var.set("Analisando e indexando todos os frames...")
        threading.Thread(
            target=self._load_video_worker, args=(self.video_path,), daemon=True
        ).start()

    def _load_video_worker(self, source: Path) -> None:
        try:
            info = probe_media(source)
            folder = self.workspace / "precision"
            frames = extract_precision_frames(source, folder, max_width=960)
        except Exception as exc:
            self.after(0, lambda error=exc: self._error(error))
            return
        self.after(0, lambda: self._finish_video_load(info, frames))

    def _finish_video_load(self, info, frames: list[Path]) -> None:
        self.media_info = info
        self.visual_duration = info.duration
        self.media_duration = max(
            info.duration,
            self.audio_info.duration if self.audio_info is not None else 0.0,
        )
        self.precision_frames = frames
        last = max(0, len(frames) - 1)
        self.frame_scale.configure(to=last)
        self.frame_entry.configure(to=max(1, len(frames)))
        self.start_scale.configure(to=self.media_duration)
        self.end_scale.configure(to=self.media_duration)
        self.start_var.set(0.0)
        self.end_var.set(info.duration)
        self.name_var.set(self.video_path.stem[:40] if self.video_path else "cena1")
        self.source_label.configure(
            text=f"Vídeo: {self.video_path}  •  {info.width}×{info.height}  •  "
            f"{info.duration:.3f}s  •  {info.fps:g} FPS  •  {len(frames)} frames"
        )
        if info.has_audio and self.audio_path is None and self.video_path is not None:
            self.audio_info = info
            self.audio_segments = [
                create_audio_segment(
                    info.duration,
                    name=f"{self.name_var.get()}_audio_01",
                )
            ]
            self.selected_segment = 0
            self.segment_history = []
            self.audio_label.configure(text="Áudio: faixa original do vídeo.")
            self._refresh_segment_table()
        self._draw_timeline()
        self.set_frame(0)
        self._selection_changed()
        self._draw_waveform()
        self.status_var.set(
            f"Indexação concluída: {len(frames)} frames. Setas ← → avançam um frame; Shift avança dez."
        )

    def open_image(self) -> None:
        selected = filedialog.askopenfilename(
            title="Abrir imagem",
            initialdir=self._dialog_dir("last_open_dir"),
            filetypes=[
                ("Imagens", "*.png *.jpg *.jpeg *.webp *.bmp"),
                ("Todos", "*.*"),
            ],
        )
        if not selected:
            return
        self.stop_preview()
        self.image_path = Path(selected)
        self._remember_dir("last_open_dir", self.image_path)
        self.video_path = None
        self.media_info = None
        self.visual_duration = 0.0
        self.precision_frames = [self.image_path]
        duration = self.audio_info.duration if self.audio_info is not None else 10.0
        self.media_duration = max(0.2, duration)
        self.frame_scale.configure(to=0)
        self.frame_entry.configure(to=1)
        self.start_scale.configure(to=self.media_duration)
        self.end_scale.configure(to=self.media_duration)
        self.start_var.set(0.0)
        self.end_var.set(self.media_duration)
        self.name_var.set(self.image_path.stem[:40])
        with Image.open(self.image_path) as image:
            width, height = image.size
        self.source_label.configure(
            text=f"Imagem: {self.image_path}  •  {width}×{height}  •  "
            f"timeline {self.media_duration:.3f}s"
        )
        self._draw_timeline()
        self.set_frame(0)
        self._selection_changed()
        self._draw_waveform()
        self.status_var.set(
            "Imagem carregada. Abra o áudio e clique na pista para posicionar o cursor."
        )

    def set_frame(self, index: int) -> None:
        if not self.precision_frames:
            return
        index = max(0, min(int(index), len(self.precision_frames) - 1))
        self.frame_var.set(index)
        self.frame_entry_var.set(str(index + 1))
        if self.image_path is not None:
            timestamp = self.playhead_time
        else:
            fps = (
                self.media_info.fps
                if self.media_info and self.media_info.fps
                else len(self.precision_frames) / self.media_duration
            )
            timestamp = min(self.media_duration, frame_time(index, fps))
            self.playhead_time = timestamp
        self.frame_label.configure(
            text=f"Frame: {index + 1}/{len(self.precision_frames)}  •  índice {index}  •  Tempo: {self._clock(timestamp)}"
        )
        with Image.open(self.precision_frames[index]) as source:
            frame = source.convert("RGB")
            frame.thumbnail((1080, 455), Image.Resampling.LANCZOS)
            self.current_photo = ImageTk.PhotoImage(frame)
        self.preview_label.configure(image=self.current_photo, text="")
        self._draw_playhead()

    def _frame_slider_changed(self, value) -> None:
        self.set_frame(round(float(value)))

    def step_frame(self, amount: int) -> None:
        self.set_frame(round(float(self.frame_var.get())) + amount)

    def last_frame(self) -> None:
        self.set_frame(len(self.precision_frames) - 1)

    def go_to_typed_frame(self) -> None:
        try:
            self.set_frame(int(self.frame_entry_var.get()) - 1)
        except ValueError:
            self._error(MediaEditorError("Informe um número de frame válido."))

    def _current_time(self) -> float:
        if self.image_path is not None:
            return max(0.0, min(self.media_duration, self.playhead_time))
        if not self.precision_frames:
            return max(0.0, min(self.media_duration, self.playhead_time))
        fps = (
            self.media_info.fps
            if self.media_info and self.media_info.fps
            else len(self.precision_frames) / self.media_duration
        )
        return min(
            self.media_duration, frame_time(round(float(self.frame_var.get())), fps)
        )

    def _timeline_clicked(self, event) -> None:
        if not self.precision_frames:
            return
        ratio = max(0.0, min(1.0, event.x / max(1, self.timeline_canvas.winfo_width())))
        if self.image_path is not None:
            self._set_playhead_time(ratio * self.media_duration)
        else:
            self.set_frame(round(ratio * (len(self.precision_frames) - 1)))

    def _set_playhead_time(self, value: float) -> None:
        self.playhead_time = max(0.0, min(self.media_duration, float(value)))
        if self.image_path is not None:
            self.frame_label.configure(
                text=f"Imagem estática  •  Tempo: {self._clock(self.playhead_time)}"
            )
        elif self.media_info is not None and self.media_info.fps > 0:
            self.set_frame(round(self.playhead_time * self.media_info.fps))
            return
        self._draw_playhead()

    def _draw_timeline(self) -> None:
        canvas = self.timeline_canvas
        canvas.delete("all")
        width = max(1, canvas.winfo_width() or 1200)
        height = 90
        if self.privacy_hidden:
            canvas.create_rectangle(0, 0, width, height, fill="#0B1F1E", outline="")
            canvas.create_text(
                width / 2,
                height / 2,
                text="MÍDIA OCULTA",
                fill="#FFFFFF",
                font=("Segoe UI", 12, "bold"),
            )
            self.timeline_images = []
            self._draw_selection()
            return
        count = max(1, min(len(self.precision_frames), 16))
        indices = [
            round(i * (len(self.precision_frames) - 1) / max(1, count - 1))
            for i in range(count)
        ]
        cell_width = width / count
        self.timeline_images = []
        for position, index in enumerate(indices):
            with Image.open(self.precision_frames[index]) as source:
                image = source.convert("RGB")
                image.thumbnail(
                    (max(40, int(cell_width) - 3), height - 5), Image.Resampling.LANCZOS
                )
                photo = ImageTk.PhotoImage(image)
            self.timeline_images.append(photo)
            canvas.create_image(
                position * cell_width + cell_width / 2, height / 2, image=photo
            )
        self._draw_selection()

    def _selection_changed(self, _value=None) -> None:
        start = float(self.start_var.get())
        end = float(self.end_var.get())
        if start > end - 0.2:
            end = min(self.media_duration, start + 0.2)
            self.end_var.set(end)
        self.start_text.configure(text=self._clock(start))
        self.end_text.configure(text=self._clock(end))
        self._draw_selection()

    def mark_start(self) -> None:
        value = min(self._current_time(), float(self.end_var.get()) - 0.2)
        self.start_var.set(max(0.0, value))
        self._selection_changed()

    def mark_end(self) -> None:
        value = max(self._current_time(), float(self.start_var.get()) + 0.2)
        self.end_var.set(min(self.media_duration, value))
        self._selection_changed()

    def _draw_selection(self) -> None:
        canvas = self.timeline_canvas
        canvas.delete("overlay")
        width = max(1, canvas.winfo_width())
        start_x = width * float(self.start_var.get()) / max(0.001, self.media_duration)
        end_x = width * float(self.end_var.get()) / max(0.001, self.media_duration)
        canvas.create_rectangle(
            0,
            0,
            start_x,
            94,
            fill="#000000",
            outline="",
            stipple="gray50",
            tags="overlay",
        )
        canvas.create_rectangle(
            end_x,
            0,
            width,
            94,
            fill="#000000",
            outline="",
            stipple="gray50",
            tags="overlay",
        )
        canvas.create_line(
            start_x, 0, start_x, 94, fill="#4DE0C1", width=3, tags="overlay"
        )
        canvas.create_line(end_x, 0, end_x, 94, fill="#D24369", width=3, tags="overlay")
        self._draw_playhead()

    def _draw_playhead(self) -> None:
        ratio = self._current_time() / max(0.001, self.media_duration)
        for canvas, height in ((self.timeline_canvas, 94), (self.wave_canvas, 68)):
            canvas.delete("playhead")
            x = max(0, canvas.winfo_width()) * ratio
            canvas.create_line(
                x, 0, x, height, fill="#FFD166", width=2, tags="playhead"
            )

    def open_audio(self) -> None:
        selected = filedialog.askopenfilename(
            title="Abrir áudio",
            initialdir=self._dialog_dir("last_open_dir"),
            filetypes=[("Áudio", "*.mp3 *.wav *.m4a *.ogg *.aac"), ("Todos", "*.*")],
        )
        if not selected:
            return
        self.audio_path = Path(selected)
        self._remember_dir("last_open_dir", self.audio_path)
        try:
            self._configure_audio(self.audio_path)
        except Exception as exc:
            self._error(exc)

    def use_video_audio(self) -> None:
        if self.video_path is None:
            self._error(MediaEditorError("Abra um vídeo com áudio primeiro."))
            return
        self.audio_path = None
        try:
            self._configure_audio(self.video_path)
        except Exception as exc:
            self._error(exc)

    def _configure_audio(self, source: Path) -> None:
        info = probe_media(source)
        if not info.has_audio:
            raise MediaEditorError(
                "O arquivo selecionado não contém uma faixa de áudio."
            )
        self.audio_info = info
        self.media_duration = max(self.visual_duration, info.duration, 0.2)
        self.start_scale.configure(to=self.media_duration)
        self.end_scale.configure(to=self.media_duration)
        self.end_var.set(
            min(self.media_duration, max(0.2, self.visual_duration or info.duration))
        )
        initial_offset = max(0.0, self._audio_offset() / 1000.0)
        initial = create_audio_segment(
            info.duration,
            name=f"{self.name_var.get()}_audio_01",
            timeline_start=initial_offset,
        )
        self.audio_segments = [initial]
        self.segment_history = []
        self.selected_segment = 0
        self.audio_label.configure(
            text=f"Áudio: {source}  •  {info.duration:.3f}s  •  1 bloco"
        )
        if self.image_path is not None:
            self.source_label.configure(
                text=f"Imagem: {self.image_path}  •  timeline {self.media_duration:.3f}s"
            )
        if self.precision_frames:
            self._draw_timeline()
            self._selection_changed()
        self._refresh_segment_table()
        self._draw_waveform()

    def _draw_waveform(self) -> None:
        source = self.audio_path or self.video_path
        if source is None or self.audio_info is None:
            return
        self.status_var.set("Lendo a forma de onda da pista de áudio...")
        threading.Thread(target=self._wave_worker, args=(source,), daemon=True).start()

    def _wave_worker(self, source: Path) -> None:
        duration = (
            self.audio_info.duration
            if self.audio_info is not None
            else self.media_duration
        )
        peaks = waveform_peaks(source, start=0, duration=duration, points=1000)
        self.after(0, lambda: self._paint_wave(peaks))

    def _paint_wave(self, peaks: list[float]) -> None:
        self.wave_peaks = peaks
        canvas = self.wave_canvas
        canvas.delete("all")
        width = max(1, canvas.winfo_width() or 1200)
        height = 68
        middle = height / 2
        audio_duration = (
            self.audio_info.duration
            if self.audio_info is not None
            else self.media_duration
        )
        for segment_index, segment in enumerate(self.audio_segments):
            start_x = width * segment.timeline_start / max(0.001, self.media_duration)
            end_x = width * segment.timeline_end / max(0.001, self.media_duration)
            selected = segment_index == self.selected_segment
            canvas.create_rectangle(
                start_x,
                2,
                end_x,
                height - 2,
                fill="#5D3045" if selected else "#38232E",
                outline="#FFD166" if selected else "#8F6475",
                width=2 if selected else 1,
            )
            for index, peak in enumerate(peaks):
                source_time = index * audio_duration / max(1, len(peaks) - 1)
                if not segment.source_start <= source_time <= segment.source_end:
                    continue
                timeline_time = (
                    segment.timeline_start + source_time - segment.source_start
                )
                x = width * timeline_time / max(0.001, self.media_duration)
                if 0 <= x <= width:
                    amplitude = peak * (height * 0.40)
                    canvas.create_line(
                        x,
                        middle - amplitude,
                        x,
                        middle + amplitude,
                        fill="#FFD0DF" if selected else "#ED8BAE",
                    )
        self._draw_playhead()
        self.status_var.set(
            f"Áudio dividido em {len(self.audio_segments)} bloco(s). Clique para selecionar; arraste para sincronizar."
        )

    def _audio_offset(self) -> int:
        try:
            return int(self.offset_var.get())
        except (tk.TclError, ValueError):
            return 0

    def _offset_entry_changed(self, _event=None) -> None:
        if 0 <= self.selected_segment < len(self.audio_segments):
            segment = self.audio_segments[self.selected_segment]
            self.audio_segments[self.selected_segment] = move_audio_segment(
                segment,
                max(0.0, self._audio_offset() / 1000.0),
            )
            self._refresh_segment_table(keep_selection=True)
        self._paint_wave(self.wave_peaks)

    def _audio_clicked(self, event) -> None:
        timeline_time = max(
            0.0,
            min(
                self.media_duration,
                event.x / max(1, self.wave_canvas.winfo_width()) * self.media_duration,
            ),
        )
        self._set_playhead_time(timeline_time)
        selected = next(
            (
                index
                for index in range(len(self.audio_segments) - 1, -1, -1)
                if self.audio_segments[index].timeline_start
                <= timeline_time
                <= self.audio_segments[index].timeline_end
            ),
            -1,
        )
        if selected >= 0:
            self._remember_segments()
            self.selected_segment = selected
            self.segment_table.selection_set(str(selected))
            self.segment_table.focus(str(selected))
            self.offset_var.set(
                round(self.audio_segments[selected].timeline_start * 1000)
            )
        self.audio_drag_x = event.x
        self.segment_drag_origin = (
            self.audio_segments[selected].timeline_start if selected >= 0 else 0.0
        )
        self._paint_wave(self.wave_peaks)

    def _audio_drag_move(self, event) -> None:
        if not 0 <= self.selected_segment < len(self.audio_segments):
            return
        width = max(1, self.wave_canvas.winfo_width())
        delta = (event.x - self.audio_drag_x) / width * self.media_duration
        segment = self.audio_segments[self.selected_segment]
        self.offset_var.set(round(segment.timeline_start * 1000))
        self.audio_segments[self.selected_segment] = move_audio_segment(
            segment,
            self.segment_drag_origin + delta,
        )
        self._paint_wave(self.wave_peaks)

    def _audio_drag_end(self, _event=None) -> None:
        if 0 <= self.selected_segment < len(self.audio_segments):
            self.offset_var.set(
                round(
                    self.audio_segments[self.selected_segment].timeline_start * 1000
                )
            )
            self._refresh_segment_table(keep_selection=True)

    def _remember_segments(self) -> None:
        snapshot = list(self.audio_segments)
        if not self.segment_history or self.segment_history[-1] != snapshot:
            self.segment_history.append(snapshot)
            self.segment_history = self.segment_history[-30:]

    def _renumber_segments(self) -> None:
        self.audio_segments = rename_audio_segments(
            self.audio_segments,
            f"{self.name_var.get()}_audio",
        )

    def _refresh_segment_table(self, *, keep_selection: bool = False) -> None:
        previous = self.selected_segment if keep_selection else -1
        for item in self.segment_table.get_children():
            self.segment_table.delete(item)
        for index, segment in enumerate(self.audio_segments):
            self.segment_table.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    segment.name,
                    f"{self._clock(segment.source_start)} → {self._clock(segment.source_end)}",
                    self._clock(segment.timeline_start),
                    self._clock(segment.duration),
                ),
            )
        if self.audio_segments:
            self.selected_segment = min(
                max(0, previous if previous >= 0 else self.selected_segment),
                len(self.audio_segments) - 1,
            )
            self.segment_table.selection_set(str(self.selected_segment))
            self.segment_table.focus(str(self.selected_segment))
        else:
            self.selected_segment = -1

    def _segment_table_selected(self, _event=None) -> None:
        selection = self.segment_table.selection()
        if not selection:
            return
        self.selected_segment = int(selection[0])
        segment = self.audio_segments[self.selected_segment]
        self._set_playhead_time(segment.timeline_start)
        self._paint_wave(self.wave_peaks)

    def _selected_audio_segment(self) -> AudioSegment:
        if not 0 <= self.selected_segment < len(self.audio_segments):
            raise MediaEditorError("Selecione um bloco de áudio.")
        return self.audio_segments[self.selected_segment]

    def split_at_playhead(self) -> None:
        try:
            segment = self._selected_audio_segment()
            left, right = split_audio_segment(segment, self._current_time())
            self._remember_segments()
            self.audio_segments[self.selected_segment : self.selected_segment + 1] = [
                left,
                right,
            ]
            self._renumber_segments()
            self.selected_segment += 1
            self._refresh_segment_table(keep_selection=True)
            self._paint_wave(self.wave_peaks)
            self.status_var.set("Corte criado. O arquivo original permaneceu intacto.")
        except Exception as exc:
            self._error(exc)

    def trim_start_to_playhead(self) -> None:
        try:
            segment = self._selected_audio_segment()
            local = self._current_time() - segment.timeline_start
            self._remember_segments()
            trimmed = trim_audio_segment(
                segment,
                source_start=segment.source_start + local,
            )
            self.audio_segments[self.selected_segment] = AudioSegment(
                trimmed.name,
                trimmed.source_start,
                trimmed.source_end,
                self._current_time(),
            )
            self._refresh_segment_table(keep_selection=True)
            self._paint_wave(self.wave_peaks)
        except Exception as exc:
            self._error(exc)

    def trim_end_to_playhead(self) -> None:
        try:
            segment = self._selected_audio_segment()
            source_end = (
                segment.source_start + self._current_time() - segment.timeline_start
            )
            self._remember_segments()
            self.audio_segments[self.selected_segment] = trim_audio_segment(
                segment,
                source_end=source_end,
            )
            self._refresh_segment_table(keep_selection=True)
            self._paint_wave(self.wave_peaks)
        except Exception as exc:
            self._error(exc)

    def delete_selected_segment(self) -> None:
        try:
            self._selected_audio_segment()
        except Exception as exc:
            self._error(exc)
            return
        self._remember_segments()
        del self.audio_segments[self.selected_segment]
        self._renumber_segments()
        self.selected_segment = min(self.selected_segment, len(self.audio_segments) - 1)
        self._refresh_segment_table(keep_selection=True)
        self._paint_wave(self.wave_peaks)

    def undo_segments(self) -> None:
        if not self.segment_history:
            self.status_var.set("Não há edição de áudio para desfazer.")
            return
        self.audio_segments = self.segment_history.pop()
        self.selected_segment = min(
            max(0, self.selected_segment), len(self.audio_segments) - 1
        )
        self._refresh_segment_table(keep_selection=True)
        self._paint_wave(self.wave_peaks)
        self.status_var.set("Última edição de áudio desfeita.")

    def _full_frame_target(self) -> Path:
        index = round(float(self.frame_var.get()))
        folder = self.workspace / "captures"
        return folder / f"frame_{index + 1:06d}.png"

    def copy_frame(self) -> None:
        if self.image_path is not None:
            try:
                copy_image_to_clipboard(self.image_path)
                self.status_var.set("Imagem copiada. Use Ctrl+V no programa desejado.")
            except Exception as exc:
                self._error(exc)
            return
        if self.video_path is None:
            self._error(MediaEditorError("Abra uma imagem ou um vídeo primeiro."))
            return
        index = round(float(self.frame_var.get()))
        target = self._full_frame_target()
        self.status_var.set(f"Extraindo o frame {index + 1} na resolução original...")
        threading.Thread(
            target=self._copy_frame_worker, args=(index, target), daemon=True
        ).start()

    def _copy_frame_worker(self, index: int, target: Path) -> None:
        try:
            extract_frame_at_index(self.video_path, target, index)  # type: ignore[arg-type]
            copy_image_to_clipboard(target)
            self.after(
                0,
                lambda: self.status_var.set(
                    f"Frame {index + 1} copiado. Use Ctrl+V no programa desejado."
                ),
            )
        except Exception as exc:
            self.after(0, lambda error=exc: self._error(error))

    def save_frame(self) -> None:
        if self.video_path is None and self.image_path is None:
            self._error(MediaEditorError("Abra uma imagem ou um vídeo primeiro."))
            return
        index = round(float(self.frame_var.get()))
        source = self.video_path or self.image_path
        default = f"{source.stem}_frame_{index + 1:06d}.png"  # type: ignore[union-attr]
        selected = filedialog.asksaveasfilename(
            title="Salvar frame",
            initialdir=self._dialog_dir("last_export_dir"),
            defaultextension=".png",
            initialfile=default,
            filetypes=[
                ("PNG sem perdas", "*.png"),
                ("JPEG", "*.jpg"),
                ("WebP", "*.webp"),
            ],
        )
        if not selected:
            return
        target = Path(selected)
        self._remember_dir("last_export_dir", target)
        if self.image_path is not None:
            try:
                with Image.open(self.image_path) as image:
                    image.save(target, quality=92)
                self.status_var.set(f"Imagem salva: {target}")
            except Exception as exc:
                self._error(exc)
            return
        self.status_var.set(f"Salvando frame {index + 1}...")
        threading.Thread(
            target=self._save_frame_worker, args=(index, target), daemon=True
        ).start()

    def _save_frame_worker(self, index: int, target: Path) -> None:
        try:
            if target.suffix.lower() == ".png":
                extract_frame_at_index(self.video_path, target, index)  # type: ignore[arg-type]
            else:
                temporary = self.workspace / "captures" / f"save_{index + 1:06d}.png"
                extract_frame_at_index(self.video_path, temporary, index)  # type: ignore[arg-type]
                with Image.open(temporary) as image:
                    image.save(target, quality=92)
            self.after(0, lambda: self.status_var.set(f"Frame salvo: {target}"))
        except Exception as exc:
            self.after(0, lambda error=exc: self._error(error))

    def _settings(self) -> dict:
        if self.video_path is None:
            raise MediaEditorError("Abra um vídeo primeiro.")
        start = float(self.start_var.get())
        end = float(self.end_var.get())
        if end - start < 0.2:
            raise MediaEditorError("Escolha um intervalo de pelo menos 0,2 segundo.")
        return {
            "video_source": self.video_path,
            "basename": self.name_var.get(),
            "start": start,
            "end": end,
            "fps": int(self.fps_var.get()),
            "quality": int(self.quality_var.get()),
            "max_side": int(self.size_var.get()),
            "audio_source": self.audio_path,
            "audio_offset_ms": int(self.offset_var.get()),
            "audio_volume": float(self.volume_var.get()),
            "audio_fade_in_ms": int(self.fade_in_var.get()),
            "audio_fade_out_ms": int(self.fade_out_var.get()),
        }

    def preview(self) -> None:
        if self.image_path is not None:
            self.play_selected_audio()
            return
        try:
            if self.audio_segments:
                settings = self._segment_settings()
                segment_mode = True
            else:
                settings = self._settings()
                segment_mode = False
        except Exception as exc:
            self._error(exc)
            return
        self.stop_preview()
        target = self.workspace / "preview"
        if target.exists():
            shutil.rmtree(target)
        target.mkdir()
        self.status_var.set("Gerando prévia sincronizada...")
        settings.update({"destination_dir": target, "max_side": 720, "quality": 60})
        worker = self._segment_preview_worker if segment_mode else self._preview_worker
        threading.Thread(target=worker, args=(settings,), daemon=True).start()

    def _segment_settings(self) -> dict:
        if self.video_path is None:
            raise MediaEditorError(
                "Abra um vídeo para exportar movimento sincronizado."
            )
        return {
            "video_source": self.video_path,
            "audio_source": self._audio_source(),
            "segment": self._selected_audio_segment(),
            "basename": self._selected_audio_segment().name.replace("_audio_", "_"),
            "fps": int(self.fps_var.get()),
            "quality": int(self.quality_var.get()),
            "max_side": int(self.size_var.get()),
            "audio_volume": float(self.volume_var.get()),
            "audio_fade_in_ms": int(self.fade_in_var.get()),
            "audio_fade_out_ms": int(self.fade_out_var.get()),
        }

    def _segment_preview_worker(self, settings: dict) -> None:
        try:
            result = export_synchronized_segment(**settings)
            self.after(0, lambda: self._start_preview(result))
        except Exception as exc:
            self.after(0, lambda error=exc: self._error(error))

    def _preview_worker(self, settings: dict) -> None:
        try:
            result = export_synchronized_clip(**settings)
            self.after(0, lambda: self._start_preview(result))
        except Exception as exc:
            self.after(0, lambda error=exc: self._error(error))

    def _start_preview(self, result) -> None:
        image = Image.open(result.webp_path)
        self.preview_images = []
        self.preview_durations = []
        try:
            for index in range(getattr(image, "n_frames", 1)):
                image.seek(index)
                frame = image.convert("RGB")
                frame.thumbnail((1080, 455), Image.Resampling.LANCZOS)
                self.preview_images.append(ImageTk.PhotoImage(frame))
                self.preview_durations.append(
                    int(image.info.get("duration", round(1000 / result.fps)))
                )
        finally:
            image.close()
        self.preview_index = 0
        if result.audio_path is not None:
            self._play_preview_audio(result.audio_path)
        self._advance_preview()
        self.status_var.set(
            f"Prévia: {result.frame_count} frames, {result.duration:.3f}s, {result.fps} FPS."
        )

    def _play_preview_audio(self, mp3: Path) -> None:
        try:
            import winsound
        except ImportError:
            return
        wav = self.workspace / "preview.wav"
        completed = subprocess.run(
            [ffmpeg_executable(), "-y", "-i", str(mp3), str(wav)],
            capture_output=True,
            check=False,
        )
        if completed.returncode == 0:
            winsound.PlaySound(str(wav), winsound.SND_FILENAME | winsound.SND_ASYNC)

    def _advance_preview(self) -> None:
        if not self.preview_images:
            return
        index = self.preview_index
        self.preview_label.configure(image=self.preview_images[index], text="")
        self.preview_index += 1
        if self.preview_index < len(self.preview_images):
            self.preview_job = self.after(
                self.preview_durations[index], self._advance_preview
            )

    def stop_preview(self) -> None:
        if self.preview_job:
            self.after_cancel(self.preview_job)
            self.preview_job = None
        try:
            import winsound

            winsound.PlaySound(None, winsound.SND_PURGE)
        except (ImportError, RuntimeError):
            pass

    def _audio_source(self) -> Path:
        source = self.audio_path or self.video_path
        if source is None or self.audio_info is None:
            raise MediaEditorError(
                "Abra um áudio do ElevenLabs ou use o áudio do vídeo."
            )
        return source

    def play_selected_audio(self) -> None:
        try:
            source = self._audio_source()
            segment = self._selected_audio_segment()
        except Exception as exc:
            self._error(exc)
            return
        target = self.workspace / "selected_preview.wav"
        self.status_var.set("Preparando o trecho selecionado...")
        threading.Thread(
            target=self._play_segment_worker,
            args=(
                source,
                segment,
                target,
                float(self.volume_var.get()),
                int(self.fade_in_var.get()),
                int(self.fade_out_var.get()),
            ),
            daemon=True,
        ).start()

    def _play_segment_worker(
        self,
        source: Path,
        segment: AudioSegment,
        target: Path,
        volume: float,
        fade_in_ms: int,
        fade_out_ms: int,
    ) -> None:
        try:
            export_audio_clip(
                source,
                target,
                start=segment.source_start,
                end=segment.source_end,
                volume=volume,
                fade_in_ms=fade_in_ms,
                fade_out_ms=fade_out_ms,
            )
            self.after(0, lambda: self._play_wav(target, segment))
        except Exception as exc:
            self.after(0, lambda error=exc: self._error(error))

    def _play_wav(self, target: Path, segment: AudioSegment) -> None:
        try:
            import winsound

            winsound.PlaySound(str(target), winsound.SND_FILENAME | winsound.SND_ASYNC)
            self.status_var.set(
                f"Reproduzindo {segment.name}: {segment.duration:.3f}s."
            )
        except (ImportError, RuntimeError) as exc:
            self._error(
                MediaEditorError(f"Não foi possível reproduzir o trecho: {exc}")
            )

    def export_selected_audio(self) -> None:
        try:
            source = self._audio_source()
            segment = self._selected_audio_segment()
        except Exception as exc:
            self._error(exc)
            return
        selected = filedialog.asksaveasfilename(
            title="Exportar bloco selecionado",
            initialdir=self._dialog_dir("last_export_dir"),
            defaultextension=".mp3",
            initialfile=f"{segment.name}.mp3",
            filetypes=[("MP3", "*.mp3"), ("WAV", "*.wav")],
        )
        if not selected:
            return
        self._remember_dir("last_export_dir", Path(selected))
        kwargs = {
            "source": source,
            "destination": Path(selected),
            "start": segment.source_start,
            "end": segment.source_end,
            "volume": float(self.volume_var.get()),
            "fade_in_ms": int(self.fade_in_var.get()),
            "fade_out_ms": int(self.fade_out_var.get()),
        }
        self.status_var.set("Exportando o bloco selecionado...")
        threading.Thread(
            target=self._audio_export_worker, args=(kwargs,), daemon=True
        ).start()

    def export_all_audio_segments(self) -> None:
        try:
            source = self._audio_source()
            if not self.audio_segments:
                raise MediaEditorError("Não existem blocos de áudio para exportar.")
        except Exception as exc:
            self._error(exc)
            return
        destination = filedialog.askdirectory(
            title="Escolha a pasta para os diálogos separados",
            initialdir=self._dialog_dir("last_export_dir"),
        )
        if not destination:
            return
        self._remember_dir("last_export_dir", Path(destination))
        segments = rename_audio_segments(
            self.audio_segments,
            f"{self.name_var.get()}_audio",
        )
        self.audio_segments = segments
        self._refresh_segment_table(keep_selection=True)
        kwargs = {
            "source": source,
            "destination_dir": Path(destination),
            "segments": segments,
            "volume": float(self.volume_var.get()),
            "fade_in_ms": int(self.fade_in_var.get()),
            "fade_out_ms": int(self.fade_out_var.get()),
        }
        self.status_var.set(f"Exportando {len(segments)} blocos de áudio...")
        threading.Thread(
            target=self._audio_batch_worker, args=(kwargs,), daemon=True
        ).start()

    def _audio_batch_worker(self, kwargs: dict) -> None:
        try:
            results = export_audio_segments(**kwargs)
            self.after(0, lambda: self._audio_batch_done(results))
        except Exception as exc:
            self.after(0, lambda error=exc: self._error(error))

    def _audio_batch_done(self, results: list[Path]) -> None:
        self.status_var.set(f"{len(results)} diálogos exportados.")
        messagebox.showinfo(
            "Áudios exportados",
            f"{len(results)} arquivo(s) foram criados em:\n{results[0].parent}",
        )

    def export_audio_only(self) -> None:
        if self.video_path is None:
            self._error(MediaEditorError("Abra um vídeo primeiro."))
            return
        source = self.audio_path or self.video_path
        selected = filedialog.asksaveasfilename(
            title="Exportar pista de áudio",
            initialdir=self._dialog_dir("last_export_dir"),
            defaultextension=".mp3",
            initialfile=f"{self.name_var.get()}_audio.mp3",
            filetypes=[("MP3", "*.mp3"), ("WAV", "*.wav")],
        )
        if not selected:
            return
        self._remember_dir("last_export_dir", Path(selected))
        kwargs = {
            "source": source,
            "destination": Path(selected),
            "start": float(self.start_var.get()),
            "end": float(self.end_var.get()),
            "offset_ms": int(self.offset_var.get()),
            "volume": float(self.volume_var.get()),
            "fade_in_ms": int(self.fade_in_var.get()),
            "fade_out_ms": int(self.fade_out_var.get()),
        }
        self.status_var.set("Exportando a pista de áudio...")
        threading.Thread(
            target=self._audio_export_worker, args=(kwargs,), daemon=True
        ).start()

    def _audio_export_worker(self, kwargs: dict) -> None:
        try:
            result = export_audio_clip(**kwargs)
            self.after(0, lambda: self.status_var.set(f"Áudio exportado: {result}"))
        except Exception as exc:
            self.after(0, lambda error=exc: self._error(error))

    def export(self) -> None:
        if self.image_path is not None:
            self.export_all_audio_segments()
            return
        try:
            if self.audio_segments:
                settings = self._segment_settings()
                segment_mode = True
            else:
                settings = self._settings()
                segment_mode = False
        except Exception as exc:
            self._error(exc)
            return
        destination = filedialog.askdirectory(
            title="Escolha a pasta de exportação",
            initialdir=self._dialog_dir("last_export_dir"),
        )
        if not destination:
            return
        self._remember_dir("last_export_dir", Path(destination))
        settings["destination_dir"] = Path(destination)
        self.status_var.set("Exportando WebP e áudio sincronizado...")
        worker = self._segment_export_worker if segment_mode else self._export_worker
        threading.Thread(target=worker, args=(settings,), daemon=True).start()

    def _segment_export_worker(self, settings: dict) -> None:
        try:
            result = export_synchronized_segment(**settings)
            self.after(0, lambda: self._export_done(result))
        except Exception as exc:
            self.after(0, lambda error=exc: self._error(error))

    def _export_worker(self, settings: dict) -> None:
        try:
            result = export_synchronized_clip(**settings)
            self.after(0, lambda: self._export_done(result))
        except Exception as exc:
            self.after(0, lambda error=exc: self._error(error))

    @staticmethod
    def _size(path: Path | None) -> str:
        if path is None or not path.exists():
            return "—"
        return f"{path.stat().st_size / (1024 * 1024):.2f} MB"

    def _export_done(self, result) -> None:
        audio = (
            f"\nMP3: {result.audio_path} ({self._size(result.audio_path)})"
            if result.audio_path
            else "\nSem faixa de áudio."
        )
        self.status_var.set(
            f"Exportação concluída: WebP {self._size(result.webp_path)}."
        )
        messagebox.showinfo(
            "Concluído",
            f"WebP: {result.webp_path} ({self._size(result.webp_path)}){audio}\n"
            f"Duração: {result.duration:.3f}s\nPerfil: {self.profile_var.get()}",
        )

    def _error(self, error: Exception) -> None:
        self.status_var.set("Operação interrompida.")
        messagebox.showerror("Editor de mídia", str(error))

    def _close(self) -> None:
        self.stop_preview()
        shutil.rmtree(self.workspace, ignore_errors=True)
        self.destroy()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--bridge", type=Path)
    args, _unknown = parser.parse_known_args()

    app = MediaTimelineEditor()
    if args.bridge is not None:
        install_bridge(app, args.bridge)
    app.mainloop()
