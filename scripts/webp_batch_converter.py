from __future__ import annotations

import re
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageOps


SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
DEFAULT_QUALITY = 90


def natural_sort_key(path: Path) -> tuple[object, ...]:
    """Ordena foto2 antes de foto10, sem depender de maiúsculas."""

    parts = re.split(r"(\d+)", path.name.casefold())
    return tuple(int(part) if part.isdigit() else part for part in parts)


def list_source_images(source_dir: Path) -> list[Path]:
    root = Path(source_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"Pasta de origem não encontrada: {root}")
    return sorted(
        (
            path
            for path in root.iterdir()
            if path.is_file() and path.suffix.casefold() in SUPPORTED_EXTENSIONS
        ),
        key=natural_sort_key,
    )


def conversion_plan(
    source_dir: Path,
    destination_dir: Path,
    *,
    prefix: str,
    start_number: int = 1,
) -> list[tuple[Path, Path]]:
    clean_prefix = prefix.strip()
    if not clean_prefix:
        raise ValueError("Informe um prefixo para os arquivos.")
    if any(character in clean_prefix for character in '<>:"/\\|?*'):
        raise ValueError("O prefixo contém caracteres inválidos para nomes de arquivo.")
    if start_number < 0:
        raise ValueError("O número inicial não pode ser negativo.")

    destination = Path(destination_dir)
    return [
        (source, destination / f"{clean_prefix}{number}.webp")
        for number, source in enumerate(
            list_source_images(Path(source_dir)), start=start_number
        )
    ]


def convert_images(
    source_dir: Path,
    destination_dir: Path,
    *,
    prefix: str,
    start_number: int = 1,
    quality: int = DEFAULT_QUALITY,
    overwrite: bool = False,
) -> list[Path]:
    """Converte e renomeia imagens sem modificar os arquivos originais."""

    if not 1 <= quality <= 100:
        raise ValueError("A qualidade deve estar entre 1 e 100.")

    plan = conversion_plan(
        source_dir,
        destination_dir,
        prefix=prefix,
        start_number=start_number,
    )
    if not plan:
        raise ValueError("Nenhuma imagem compatível foi encontrada na pasta de origem.")

    conflicts = [target for _, target in plan if target.exists()]
    if conflicts and not overwrite:
        names = ", ".join(path.name for path in conflicts[:5])
        suffix = "..." if len(conflicts) > 5 else ""
        raise FileExistsError(f"Arquivos de destino já existem: {names}{suffix}")

    destination = Path(destination_dir)
    destination.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []
    for source, target in plan:
        with Image.open(source) as opened:
            image = ImageOps.exif_transpose(opened)
            converted = image.convert("RGBA" if "A" in image.getbands() else "RGB")
            converted.save(
                target,
                "WEBP",
                quality=quality,
                method=6,
                lossless=False,
                exact=True,
            )
        generated.append(target)
    return generated


class WebpBatchConverterApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Conversor de imagens para WebP")
        self.root.minsize(760, 520)

        self.source = tk.StringVar()
        self.destination = tk.StringVar()
        self.prefix = tk.StringVar(value="camilly")
        self.start_number = tk.IntVar(value=1)
        self.quality = tk.IntVar(value=DEFAULT_QUALITY)
        self.overwrite = tk.BooleanVar(value=False)

        frame = ttk.Frame(root, padding=16)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(7, weight=1)

        self._folder_row(frame, 0, "Pasta de origem", self.source, self._choose_source)
        self._folder_row(
            frame, 1, "Pasta de destino", self.destination, self._choose_destination
        )

        ttk.Label(frame, text="Prefixo").grid(row=2, column=0, sticky="w", pady=6)
        ttk.Entry(frame, textvariable=self.prefix).grid(
            row=2, column=1, columnspan=2, sticky="ew", pady=6
        )

        ttk.Label(frame, text="Número inicial").grid(row=3, column=0, sticky="w", pady=6)
        ttk.Spinbox(frame, from_=0, to=999999, textvariable=self.start_number).grid(
            row=3, column=1, sticky="ew", pady=6
        )

        ttk.Label(frame, text="Qualidade WebP").grid(row=4, column=0, sticky="w", pady=6)
        ttk.Scale(
            frame,
            from_=50,
            to=100,
            variable=self.quality,
            orient="horizontal",
            command=lambda _value: self.quality_label.configure(
                text=str(self.quality.get())
            ),
        ).grid(row=4, column=1, sticky="ew", pady=6)
        self.quality_label = ttk.Label(frame, text=str(DEFAULT_QUALITY), width=4)
        self.quality_label.grid(row=4, column=2, sticky="e", pady=6)

        ttk.Checkbutton(
            frame,
            text="Permitir substituir arquivos WebP existentes",
            variable=self.overwrite,
        ).grid(row=5, column=1, columnspan=2, sticky="w", pady=6)

        buttons = ttk.Frame(frame)
        buttons.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(12, 8))
        ttk.Button(buttons, text="Visualizar ordem", command=self._preview).pack(
            side="left"
        )
        ttk.Button(buttons, text="Converter", command=self._convert).pack(
            side="right"
        )

        self.preview = tk.Text(frame, height=14, wrap="none", state="disabled")
        self.preview.grid(row=7, column=0, columnspan=3, sticky="nsew")
        ttk.Label(
            frame,
            text=(
                "Os arquivos originais são preservados. Qualidade 90 oferece boa "
                "redução de tamanho para uso no app."
            ),
        ).grid(row=8, column=0, columnspan=3, sticky="w", pady=(8, 0))

    @staticmethod
    def _folder_row(
        parent: ttk.Frame,
        row: int,
        label: str,
        variable: tk.StringVar,
        command: object,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=6)
        ttk.Entry(parent, textvariable=variable).grid(
            row=row, column=1, sticky="ew", pady=6
        )
        ttk.Button(parent, text="Selecionar...", command=command).grid(
            row=row, column=2, padx=(8, 0), pady=6
        )

    def _choose_source(self) -> None:
        selected = filedialog.askdirectory(title="Selecione a pasta de origem")
        if selected:
            self.source.set(selected)
            if not self.destination.get():
                self.destination.set(str(Path(selected) / "webp"))
            self._preview()

    def _choose_destination(self) -> None:
        selected = filedialog.askdirectory(title="Selecione a pasta de destino")
        if selected:
            self.destination.set(selected)

    def _plan(self) -> list[tuple[Path, Path]]:
        return conversion_plan(
            Path(self.source.get()),
            Path(self.destination.get()),
            prefix=self.prefix.get(),
            start_number=self.start_number.get(),
        )

    def _show_preview(self, lines: list[str]) -> None:
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", "\n".join(lines))
        self.preview.configure(state="disabled")

    def _preview(self) -> None:
        try:
            plan = self._plan()
            lines = [
                f"{index:>3}. {source.name}  →  {target.name}"
                for index, (source, target) in enumerate(plan, start=1)
            ]
            self._show_preview(lines or ["Nenhuma imagem compatível encontrada."])
        except (FileNotFoundError, ValueError, tk.TclError) as exc:
            self._show_preview([str(exc)])

    def _convert(self) -> None:
        try:
            generated = convert_images(
                Path(self.source.get()),
                Path(self.destination.get()),
                prefix=self.prefix.get(),
                start_number=self.start_number.get(),
                quality=self.quality.get(),
                overwrite=self.overwrite.get(),
            )
        except (FileNotFoundError, FileExistsError, OSError, ValueError, tk.TclError) as exc:
            messagebox.showerror("Conversão não realizada", str(exc))
            return

        total_bytes = sum(path.stat().st_size for path in generated)
        messagebox.showinfo(
            "Conversão concluída",
            f"{len(generated)} imagens geradas ({total_bytes / 1024 / 1024:.1f} MB).",
        )
        self._preview()


def main() -> None:
    root = tk.Tk()
    WebpBatchConverterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
