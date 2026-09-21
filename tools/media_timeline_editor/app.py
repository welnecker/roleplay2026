from __future__ import annotations

import shutil
import subprocess
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from core import (
    MediaEditorError,
    export_synchronized_clip,
    extract_timeline_frames,
    ffmpeg_executable,
    probe_media,
    waveform_peaks,
)


class MediaTimelineEditor(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Editor de Mídia EntreCenas — MP4 → WebP + MP3")
        self.geometry("1240x820")
        self.minsize(980, 700)
        self.configure(bg="#183D3A")
        self.video_path: Path | None = None
        self.audio_path: Path | None = None
        self.media_duration = 1.0
        self.timeline_files: list[Path] = []
        self.timeline_images: list[ImageTk.PhotoImage] = []
        self.preview_images: list[ImageTk.PhotoImage] = []
        self.preview_durations: list[int] = []
        self.preview_job: str | None = None
        self.preview_index = 0
        self.workspace = Path(tempfile.mkdtemp(prefix="entrecenas_timeline_"))
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._build()

    def _build(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#183D3A")
        style.configure("TLabel", background="#183D3A", foreground="#FFFFFF")
        style.configure("Title.TLabel", font=("Segoe UI", 17, "bold"))
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))

        top = ttk.Frame(self, padding=12)
        top.pack(fill="x")
        ttk.Label(top, text="Editor de Mídia EntreCenas", style="Title.TLabel").pack(side="left")
        ttk.Button(top, text="ABRIR MP4", command=self.open_video).pack(side="left", padx=(24, 5))
        ttk.Button(top, text="ABRIR MP3", command=self.open_audio).pack(side="left", padx=5)
        ttk.Button(top, text="USAR ÁUDIO DO VÍDEO", command=self.use_video_audio).pack(side="left", padx=5)
        ttk.Button(top, text="PRÉVIA", command=self.preview).pack(side="right", padx=5)
        ttk.Button(top, text="EXPORTAR", style="Accent.TButton", command=self.export).pack(side="right", padx=5)

        self.source_label = ttk.Label(self, text="Abra um vídeo MP4 para começar.", padding=(14, 0))
        self.source_label.pack(fill="x")

        preview_frame = ttk.Frame(self, padding=12)
        preview_frame.pack(fill="both", expand=True)
        self.preview_label = tk.Label(
            preview_frame, text="PRÉVIA", bg="#102F2D", fg="#D6E5E3",
            font=("Segoe UI", 14, "bold"), anchor="center",
        )
        self.preview_label.pack(fill="both", expand=True)

        timeline_box = ttk.LabelFrame(self, text=" TIMELINE DO VÍDEO ", padding=8)
        timeline_box.pack(fill="x", padx=12, pady=(0, 8))
        self.timeline_canvas = tk.Canvas(timeline_box, height=116, bg="#102F2D", highlightthickness=0)
        self.timeline_canvas.pack(fill="x")

        selectors = ttk.Frame(timeline_box)
        selectors.pack(fill="x", pady=(6, 0))
        self.start_var = tk.DoubleVar(value=0.0)
        self.end_var = tk.DoubleVar(value=1.0)
        ttk.Label(selectors, text="Início").grid(row=0, column=0, sticky="w")
        self.start_scale = ttk.Scale(selectors, variable=self.start_var, from_=0, to=1, command=self._selection_changed)
        self.start_scale.grid(row=0, column=1, sticky="ew", padx=8)
        self.start_text = ttk.Label(selectors, text="00:00.000", width=12)
        self.start_text.grid(row=0, column=2)
        ttk.Label(selectors, text="Fim").grid(row=1, column=0, sticky="w")
        self.end_scale = ttk.Scale(selectors, variable=self.end_var, from_=0, to=1, command=self._selection_changed)
        self.end_scale.grid(row=1, column=1, sticky="ew", padx=8)
        self.end_text = ttk.Label(selectors, text="00:01.000", width=12)
        self.end_text.grid(row=1, column=2)
        selectors.columnconfigure(1, weight=1)

        audio_box = ttk.LabelFrame(self, text=" FAIXA DE ÁUDIO ", padding=8)
        audio_box.pack(fill="x", padx=12, pady=(0, 8))
        self.wave_canvas = tk.Canvas(audio_box, height=74, bg="#241A22", highlightthickness=0)
        self.wave_canvas.pack(fill="x")
        self.audio_label = ttk.Label(audio_box, text="Áudio: será usado o áudio do próprio MP4, quando existir.")
        self.audio_label.pack(anchor="w", pady=(4, 2))

        options = ttk.Frame(self, padding=(12, 0, 12, 12))
        options.pack(fill="x")
        self.name_var = tk.StringVar(value="cena1")
        self.fps_var = tk.IntVar(value=12)
        self.quality_var = tk.IntVar(value=78)
        self.size_var = tk.IntVar(value=1280)
        self.offset_var = tk.IntVar(value=0)
        self.volume_var = tk.DoubleVar(value=1.0)
        self.fade_in_var = tk.IntVar(value=0)
        self.fade_out_var = tk.IntVar(value=250)
        fields = [
            ("Nome", self.name_var, 14), ("FPS", self.fps_var, 6),
            ("Qualidade", self.quality_var, 7), ("Máx. px", self.size_var, 8),
            ("Áudio offset ms", self.offset_var, 9), ("Volume", self.volume_var, 7),
            ("Fade-in ms", self.fade_in_var, 8), ("Fade-out ms", self.fade_out_var, 8),
        ]
        for column, (label, variable, width) in enumerate(fields):
            cell = ttk.Frame(options)
            cell.grid(row=0, column=column, padx=4, sticky="ew")
            ttk.Label(cell, text=label).pack(anchor="w")
            ttk.Entry(cell, textvariable=variable, width=width).pack(fill="x")
            options.columnconfigure(column, weight=1)
        self.status_var = tk.StringVar(value="Pronto.")
        ttk.Label(self, textvariable=self.status_var, padding=(14, 0, 14, 10)).pack(fill="x")

    @staticmethod
    def _clock(value: float) -> str:
        minutes, seconds = divmod(max(0.0, value), 60)
        return f"{int(minutes):02d}:{seconds:06.3f}"

    def _selection_changed(self, _value: object = None) -> None:
        start = float(self.start_var.get())
        end = float(self.end_var.get())
        if start > end - 0.2:
            if _value is not None:
                end = min(self.media_duration, start + 0.2)
                self.end_var.set(end)
        self.start_text.configure(text=self._clock(start))
        self.end_text.configure(text=self._clock(end))
        self._draw_selection()

    def open_video(self) -> None:
        selected = filedialog.askopenfilename(
            title="Abrir vídeo", filetypes=[("Vídeo MP4", "*.mp4"), ("Vídeos", "*.mp4 *.mov *.mkv"), ("Todos", "*.*")]
        )
        if not selected:
            return
        self.video_path = Path(selected)
        self.status_var.set("Analisando vídeo e extraindo miniaturas...")
        threading.Thread(target=self._load_video_worker, daemon=True).start()

    def _load_video_worker(self) -> None:
        try:
            info = probe_media(self.video_path)  # type: ignore[arg-type]
            folder = self.workspace / "timeline"
            frames = extract_timeline_frames(self.video_path, folder, sample_fps=1.0)  # type: ignore[arg-type]
        except Exception as exc:
            self.after(0, lambda: self._error(exc))
            return
        self.after(0, lambda: self._finish_video_load(info, frames))

    def _finish_video_load(self, info, frames: list[Path]) -> None:
        self.media_duration = info.duration
        self.timeline_files = frames
        self.start_scale.configure(to=info.duration)
        self.end_scale.configure(to=info.duration)
        self.start_var.set(0.0)
        self.end_var.set(info.duration)
        self.source_label.configure(
            text=f"Vídeo: {self.video_path}  •  {info.width}×{info.height}  •  {info.duration:.3f}s  •  {info.fps:g} FPS"
        )
        self.name_var.set(self.video_path.stem[:40] if self.video_path else "cena1")
        self._draw_timeline()
        self._draw_waveform()
        self._selection_changed()
        self.status_var.set(f"Timeline carregada: {len(frames)} miniaturas.")

    def open_audio(self) -> None:
        selected = filedialog.askopenfilename(
            title="Abrir áudio", filetypes=[("MP3", "*.mp3"), ("Áudio", "*.mp3 *.wav *.m4a *.ogg"), ("Todos", "*.*")]
        )
        if not selected:
            return
        self.audio_path = Path(selected)
        self.audio_label.configure(text=f"Áudio separado: {self.audio_path}")
        self._draw_waveform()

    def use_video_audio(self) -> None:
        self.audio_path = None
        self.audio_label.configure(text="Áudio: faixa original do vídeo.")
        self._draw_waveform()

    def _draw_timeline(self) -> None:
        self.timeline_canvas.delete("all")
        width = max(1, self.timeline_canvas.winfo_width() or 1100)
        height = 110
        count = max(1, min(len(self.timeline_files), 12))
        indices = [round(index * (len(self.timeline_files) - 1) / max(1, count - 1)) for index in range(count)]
        cell_width = width / count
        self.timeline_images = []
        for position, index in enumerate(indices):
            image = Image.open(self.timeline_files[index]).convert("RGB")
            image.thumbnail((max(40, int(cell_width) - 4), height - 8), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(image)
            self.timeline_images.append(photo)
            self.timeline_canvas.create_image(position * cell_width + cell_width / 2, height / 2, image=photo)
        self._draw_selection()

    def _draw_selection(self) -> None:
        canvas = self.timeline_canvas
        canvas.delete("selection")
        width = max(1, canvas.winfo_width())
        start_x = width * float(self.start_var.get()) / max(0.001, self.media_duration)
        end_x = width * float(self.end_var.get()) / max(0.001, self.media_duration)
        canvas.create_rectangle(0, 0, start_x, 116, fill="#000000", outline="", stipple="gray50", tags="selection")
        canvas.create_rectangle(end_x, 0, width, 116, fill="#000000", outline="", stipple="gray50", tags="selection")
        canvas.create_line(start_x, 0, start_x, 116, fill="#4DE0C1", width=3, tags="selection")
        canvas.create_line(end_x, 0, end_x, 116, fill="#D24369", width=3, tags="selection")

    def _draw_waveform(self) -> None:
        if self.video_path is None:
            return
        source = self.audio_path or self.video_path
        self.status_var.set("Lendo a forma de onda...")
        threading.Thread(target=self._wave_worker, args=(source,), daemon=True).start()

    def _wave_worker(self, source: Path) -> None:
        peaks = waveform_peaks(source, start=0, duration=self.media_duration, points=900)
        self.after(0, lambda: self._paint_wave(peaks))

    def _paint_wave(self, peaks: list[float]) -> None:
        canvas = self.wave_canvas
        canvas.delete("all")
        width = max(1, canvas.winfo_width() or 1100)
        height = 74
        middle = height / 2
        step = width / max(1, len(peaks))
        for index, peak in enumerate(peaks):
            amplitude = peak * (height * 0.44)
            x = index * step
            canvas.create_line(x, middle - amplitude, x, middle + amplitude, fill="#ED8BAE")
        self.status_var.set("Áudio carregado. Ajuste o intervalo ou faça a prévia.")

    def _settings(self) -> dict:
        if self.video_path is None:
            raise MediaEditorError("Abra um vídeo primeiro.")
        start = float(self.start_var.get())
        end = float(self.end_var.get())
        if end - start < 0.2:
            raise MediaEditorError("Escolha um intervalo de pelo menos 0,2 segundo.")
        return {
            "video_source": self.video_path, "basename": self.name_var.get(),
            "start": start, "end": end, "fps": int(self.fps_var.get()),
            "quality": int(self.quality_var.get()), "max_side": int(self.size_var.get()),
            "audio_source": self.audio_path, "audio_offset_ms": int(self.offset_var.get()),
            "audio_volume": float(self.volume_var.get()),
            "audio_fade_in_ms": int(self.fade_in_var.get()),
            "audio_fade_out_ms": int(self.fade_out_var.get()),
        }

    def preview(self) -> None:
        try:
            settings = self._settings()
        except Exception as exc:
            self._error(exc)
            return
        self.stop_preview()
        target = self.workspace / "preview"
        if target.exists():
            shutil.rmtree(target)
        target.mkdir()
        self.status_var.set("Gerando prévia sincronizada...")
        settings.update({"destination_dir": target, "max_side": 720, "quality": 65})
        threading.Thread(target=self._preview_worker, args=(settings,), daemon=True).start()

    def _preview_worker(self, settings: dict) -> None:
        try:
            result = export_synchronized_clip(**settings)
            self.after(0, lambda: self._start_preview(result))
        except Exception as exc:
            self.after(0, lambda: self._error(exc))

    def _start_preview(self, result) -> None:
        image = Image.open(result.webp_path)
        self.preview_images = []
        self.preview_durations = []
        try:
            for index in range(getattr(image, "n_frames", 1)):
                image.seek(index)
                frame = image.convert("RGB")
                frame.thumbnail((900, 440), Image.Resampling.LANCZOS)
                self.preview_images.append(ImageTk.PhotoImage(frame))
                self.preview_durations.append(int(image.info.get("duration", round(1000 / result.fps))))
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
            capture_output=True, check=False,
        )
        if completed.returncode == 0:
            winsound.PlaySound(str(wav), winsound.SND_FILENAME | winsound.SND_ASYNC)

    def _advance_preview(self) -> None:
        if not self.preview_images:
            return
        index = self.preview_index % len(self.preview_images)
        self.preview_label.configure(image=self.preview_images[index], text="")
        self.preview_index += 1
        if self.preview_index < len(self.preview_images):
            self.preview_job = self.after(self.preview_durations[index], self._advance_preview)

    def stop_preview(self) -> None:
        if self.preview_job:
            self.after_cancel(self.preview_job)
            self.preview_job = None
        try:
            import winsound
            winsound.PlaySound(None, winsound.SND_PURGE)
        except (ImportError, RuntimeError):
            pass

    def export(self) -> None:
        try:
            settings = self._settings()
        except Exception as exc:
            self._error(exc)
            return
        destination = filedialog.askdirectory(title="Escolha a pasta de exportação")
        if not destination:
            return
        settings["destination_dir"] = Path(destination)
        self.status_var.set("Exportando WebP e áudio sincronizado...")
        threading.Thread(target=self._export_worker, args=(settings,), daemon=True).start()

    def _export_worker(self, settings: dict) -> None:
        try:
            result = export_synchronized_clip(**settings)
            self.after(0, lambda: self._export_done(result))
        except Exception as exc:
            self.after(0, lambda: self._error(exc))

    def _export_done(self, result) -> None:
        audio = f"\n{result.audio_path}" if result.audio_path else "\nSem faixa de áudio."
        self.status_var.set(f"Exportação concluída em {result.duration:.3f}s.")
        messagebox.showinfo("Concluído", f"Arquivos gerados:\n{result.webp_path}{audio}")

    def _error(self, error: Exception) -> None:
        self.status_var.set("Operação interrompida.")
        messagebox.showerror("Editor de mídia", str(error))

    def _close(self) -> None:
        self.stop_preview()
        shutil.rmtree(self.workspace, ignore_errors=True)
        self.destroy()


if __name__ == "__main__":
    MediaTimelineEditor().mainloop()
