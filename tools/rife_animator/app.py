from __future__ import annotations

import os
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from core import (  # noqa: E402
    DEFAULT_FFMPEG,
    AnimatorError,
    RenderSettings,
    render_with_practical_rife,
    render_with_vulkan,
)


class RifeAnimator(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("EntreCenas — Animador de Quadros")
        self.geometry("980x690")
        self.minsize(820, 580)
        self.images: list[Path] = []
        self.last_output: Path | None = None

        self.engine_var = tk.StringVar(value="Vulkan portátil")
        self.rife_var = tk.StringVar()
        self.practical_var = tk.StringVar()
        self.python_var = tk.StringVar(value=sys.executable)
        self.model_var = tk.StringVar()
        self.ffmpeg_var = tk.StringVar(value=str(DEFAULT_FFMPEG))
        self.duration_var = tk.DoubleVar(value=12.0)
        self.cycle_var = tk.DoubleVar(value=2.0)
        self.fps_var = tk.IntVar(value=24)
        self.mode_var = tk.StringVar(value="loop")
        self.status_var = tk.StringVar(value="Selecione entre 2 e 12 imagens.")
        self._build()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        header = ttk.Frame(self, padding=14)
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text="EntreCenas — Animador de Quadros", font=("Segoe UI", 17, "bold")).pack(side="left")

        body = ttk.Panedwindow(self, orient="horizontal")
        body.grid(row=1, column=0, sticky="nsew", padx=14)
        left = ttk.Frame(body, padding=10)
        right = ttk.Frame(body, padding=10)
        body.add(left, weight=3)
        body.add(right, weight=2)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(left)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(toolbar, text="Selecionar imagens", command=self.select_images).pack(side="left")
        ttk.Button(toolbar, text="Remover", command=self.remove_selected).pack(side="left", padx=5)
        ttk.Button(toolbar, text="↑", width=4, command=lambda: self.move(-1)).pack(side="right")
        ttk.Button(toolbar, text="↓", width=4, command=lambda: self.move(1)).pack(side="right", padx=5)
        self.listbox = tk.Listbox(left, font=("Segoe UI", 10), activestyle="dotbox")
        self.listbox.grid(row=1, column=0, sticky="nsew")

        right.columnconfigure(1, weight=1)
        row = 0
        row = self._combo(right, row, "Motor", self.engine_var, ("Vulkan portátil", "Practical-RIFE 4.25"))
        row = self._path(right, row, "RIFE Vulkan (.exe)", self.rife_var, file=True)
        row = self._path(right, row, "Pasta Practical-RIFE", self.practical_var)
        row = self._path(right, row, "Python do ambiente", self.python_var, file=True)
        row = self._path(right, row, "Pasta do modelo 4.25", self.model_var)
        row = self._path(right, row, "FFmpeg", self.ffmpeg_var, file=True)
        row = self._spin(right, row, "Duração final (s)", self.duration_var, 10, 120, 1)
        row = self._spin(right, row, "Duração do ciclo (s)", self.cycle_var, 0.5, 10, 0.1)
        row = self._combo(right, row, "FPS", self.fps_var, (24, 30, 48, 60))
        row = self._combo(right, row, "Ciclo", self.mode_var, ("loop", "pingpong"))

        actions = ttk.Frame(self, padding=14)
        actions.grid(row=2, column=0, sticky="ew")
        self.generate_button = ttk.Button(actions, text="Gerar vídeo", command=self.generate)
        self.generate_button.pack(side="left")
        self.open_button = ttk.Button(actions, text="Abrir último vídeo", command=self.open_video, state="disabled")
        self.open_button.pack(side="left", padx=8)
        ttk.Label(actions, textvariable=self.status_var).pack(side="left", padx=12)

    def _path(self, parent, row, label, variable, *, file=False):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", padx=5)
        chooser = filedialog.askopenfilename if file else filedialog.askdirectory
        ttk.Button(parent, text="...", width=4, command=lambda: self._choose(variable, chooser)).grid(row=row, column=2)
        return row + 1

    def _combo(self, parent, row, label, variable, values):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Combobox(parent, textvariable=variable, values=values, state="readonly").grid(row=row, column=1, columnspan=2, sticky="ew", padx=5)
        return row + 1

    def _spin(self, parent, row, label, variable, start, end, step):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Spinbox(parent, textvariable=variable, from_=start, to=end, increment=step).grid(row=row, column=1, columnspan=2, sticky="ew", padx=5)
        return row + 1

    @staticmethod
    def _choose(variable, chooser) -> None:
        selected = chooser()
        if selected:
            variable.set(selected)

    def select_images(self) -> None:
        selected = filedialog.askopenfilenames(filetypes=[("Imagens", "*.png *.jpg *.jpeg *.webp")])
        self.images.extend(Path(path) for path in selected if Path(path) not in self.images)
        self.refresh_list()

    def refresh_list(self) -> None:
        self.listbox.delete(0, "end")
        for index, path in enumerate(self.images, 1):
            self.listbox.insert("end", f"{index:02d}  {path.name}")
        self.status_var.set(f"{len(self.images)} imagem(ns) selecionada(s).")

    def remove_selected(self) -> None:
        selected = self.listbox.curselection()
        if selected:
            self.images.pop(selected[0])
            self.refresh_list()

    def move(self, offset: int) -> None:
        selected = self.listbox.curselection()
        if not selected:
            return
        old = selected[0]
        new = max(0, min(len(self.images) - 1, old + offset))
        if new == old:
            return
        self.images[old], self.images[new] = self.images[new], self.images[old]
        self.refresh_list()
        self.listbox.selection_set(new)

    def generate(self) -> None:
        output = filedialog.asksaveasfilename(defaultextension=".mp4", filetypes=[("Vídeo MP4", "*.mp4")])
        if not output:
            return
        self.generate_button.configure(state="disabled")
        self.open_button.configure(state="disabled")
        threading.Thread(target=self._generate_worker, args=(Path(output),), daemon=True).start()

    def _progress(self, message: str) -> None:
        self.after(0, self.status_var.set, message)

    def _generate_worker(self, output: Path) -> None:
        try:
            settings = RenderSettings(
                duration_seconds=float(self.duration_var.get()),
                cycle_seconds=float(self.cycle_var.get()),
                fps=int(self.fps_var.get()),
                mode=self.mode_var.get(),
            )
            common = dict(images=self.images, ffmpeg=Path(self.ffmpeg_var.get()), output=output, settings=settings, progress=self._progress)
            if self.engine_var.get() == "Vulkan portátil":
                result = render_with_vulkan(rife_executable=Path(self.rife_var.get()), **common)
            else:
                result = render_with_practical_rife(
                    python_executable=Path(self.python_var.get()),
                    practical_rife_dir=Path(self.practical_var.get()),
                    model_dir=Path(self.model_var.get()),
                    **common,
                )
        except (AnimatorError, OSError, ValueError) as exc:
            self.after(0, messagebox.showerror, "Não foi possível gerar", str(exc))
            self.after(0, self.status_var.set, "Falha na geração.")
        else:
            self.last_output = result
            self.after(0, self.open_button.configure, {"state": "normal"})
            self.after(0, self.status_var.set, f"Concluído: {result.name}")
        finally:
            self.after(0, self.generate_button.configure, {"state": "normal"})

    def open_video(self) -> None:
        if self.last_output and self.last_output.is_file():
            os.startfile(self.last_output)  # type: ignore[attr-defined]


if __name__ == "__main__":
    RifeAnimator().mainloop()

