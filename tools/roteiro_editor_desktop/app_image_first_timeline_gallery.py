from __future__ import annotations

import re
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from app_image_first import Image, ImageTk, slugify
from app_image_first_timeline_thumbs import ScriptEditor as ThumbnailScriptEditor


class ScriptEditor(ThumbnailScriptEditor):
    """Timeline visual com galeria clicavel de todas as imagens de referencia."""

    GALLERY_THUMB_SIZE = (96, 72)
    GALLERY_COLUMNS = 4

    def __init__(self) -> None:
        self._gallery_images: dict[str, object] = {}
        self._gallery_buttons: dict[int, ttk.Button] = {}
        self._gallery_canvas = None
        self._gallery_inner = None
        self._gallery_window = None
        self._image_prefix_snapshot = ""
        super().__init__()
        self._image_prefix_snapshot = slugify(self.image_prefix_var.get(), "imagem")
        self.title("Editor de Roteiros ROLEPLAY2026 — Timeline + Galeria")
        self._install_reference_gallery()
        self._refresh_reference_gallery()

    def _install_reference_gallery(self) -> None:
        right = self.preview_label.master.master

        # Abre um espaco entre o preview grande e os controles existentes.
        for child in right.winfo_children():
            info = child.grid_info()
            if not info:
                continue
            try:
                row = int(info.get("row", 0))
            except Exception:
                continue
            if row >= 4:
                child.grid_configure(row=row + 1)

        gallery = ttk.LabelFrame(right, text="Galeria de referencias", padding=6)
        gallery.grid(row=4, column=0, sticky="nsew", pady=(8, 4))
        gallery.columnconfigure(0, weight=1)
        gallery.rowconfigure(0, weight=1)

        canvas = tk.Canvas(gallery, height=210, highlightthickness=0)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(gallery, orient="vertical", command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scrollbar.set)

        inner = ttk.Frame(canvas)
        window = canvas.create_window((0, 0), window=inner, anchor="nw")

        def sync_scrollregion(_event=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def stretch_inner(event) -> None:
            canvas.itemconfigure(window, width=event.width)

        inner.bind("<Configure>", sync_scrollregion)
        canvas.bind("<Configure>", stretch_inner)

        self._gallery_canvas = canvas
        self._gallery_inner = inner
        self._gallery_window = window

    def _gallery_thumbnail(self, source: str):
        if Image is None or ImageTk is None:
            return None
        path = Path(source)
        if not path.exists() or not path.is_file():
            return None
        try:
            with Image.open(path) as opened:
                preview = opened.convert("RGB")
                preview.thumbnail(self.GALLERY_THUMB_SIZE)
                image = ImageTk.PhotoImage(preview)
        except Exception:
            return None
        self._gallery_images[source] = image
        return image

    def _is_reference_used(self, source: str) -> bool:
        normalized = str(Path(source))
        for mapped in self.image_sources.values():
            if str(Path(str(mapped))) == normalized:
                return True
        return False

    def _select_gallery_reference(self, index: int) -> None:
        if not (0 <= index < len(self.reference_files)):
            return
        self.reference_index = index
        self.show_reference()
        self._refresh_gallery_selection()

    def _refresh_gallery_selection(self) -> None:
        for index, button in self._gallery_buttons.items():
            button.state(["!pressed"])
            if index == self.reference_index:
                button.state(["pressed"])

    def _refresh_reference_gallery(self) -> None:
        if self._gallery_inner is None:
            return

        for child in self._gallery_inner.winfo_children():
            child.destroy()
        self._gallery_images.clear()
        self._gallery_buttons.clear()

        if not self.reference_files:
            ttk.Label(
                self._gallery_inner,
                text="Abra um lote para visualizar todas as imagens aqui.",
                anchor="center",
            ).grid(row=0, column=0, padx=8, pady=24, sticky="ew")
            return

        for column in range(self.GALLERY_COLUMNS):
            self._gallery_inner.columnconfigure(column, weight=1)

        for index, source in enumerate(self.reference_files):
            path = Path(source)
            thumb = self._gallery_thumbnail(source)
            used = self._is_reference_used(source)
            caption = f"{'✓ ' if used else ''}{path.name}"
            row, column = divmod(index, self.GALLERY_COLUMNS)

            button = ttk.Button(
                self._gallery_inner,
                text=caption,
                image=thumb if thumb is not None else "",
                compound="top",
                command=lambda i=index: self._select_gallery_reference(i),
                width=16,
            )
            button.grid(row=row, column=column, padx=4, pady=4, sticky="nsew")
            self._gallery_buttons[index] = button

        self._refresh_gallery_selection()
        if self._gallery_canvas is not None:
            self._gallery_canvas.update_idletasks()
            self._gallery_canvas.configure(scrollregion=self._gallery_canvas.bbox("all"))

    def _migrate_existing_image_prefix(self) -> int:
        current_prefix = slugify(self.image_prefix_var.get(), "imagem")
        previous_prefix = self._image_prefix_snapshot or current_prefix
        if current_prefix == previous_prefix:
            return 0

        referenced_ids = set(self.image_sources)
        referenced_ids.update(str(value) for value in self.image_map.values() if value)
        for binding in self.description_bindings.values():
            image_id = str(binding.get("image_id", "") or "")
            if image_id:
                referenced_ids.add(image_id)

        rename_map: dict[str, str] = {}
        numbered = re.compile(r"^(.+?)(\d+)\.webp$", re.IGNORECASE)
        for old_id in referenced_ids:
            match = numbered.match(old_id)
            if not match:
                continue
            new_id = f"{current_prefix}{match.group(2)}.webp"
            if new_id != old_id:
                rename_map[old_id] = new_id

        if not rename_map:
            self._image_prefix_snapshot = current_prefix
            return 0

        targets = list(rename_map.values())
        if len(targets) != len(set(targets)):
            raise ValueError("A troca do prefixo criaria image_id duplicado.")
        untouched = referenced_ids.difference(rename_map)
        collision = sorted(set(targets).intersection(untouched))
        if collision:
            raise ValueError(
                "A troca do prefixo entraria em conflito com image_id existente: "
                + ", ".join(collision[:5])
            )

        migrated_sources: dict[str, str] = {}
        for image_id, source in self.image_sources.items():
            migrated_sources[rename_map.get(image_id, image_id)] = source
        self.image_sources = migrated_sources

        self.image_map = {
            line_id: rename_map.get(str(image_id), str(image_id))
            for line_id, image_id in self.image_map.items()
        }

        for binding in self.description_bindings.values():
            old_id = str(binding.get("image_id", "") or "")
            if old_id in rename_map:
                binding["image_id"] = rename_map[old_id]

        self._image_prefix_snapshot = current_prefix
        return len(rename_map)

    def compile_current(self) -> bool:
        backup_sources = dict(self.image_sources)
        backup_map = dict(self.image_map)
        backup_bindings = {
            int(key): dict(value) for key, value in self.description_bindings.items()
        }
        backup_prefix = self._image_prefix_snapshot

        try:
            migrated = self._migrate_existing_image_prefix()
        except Exception as exc:
            from tkinter import messagebox

            messagebox.showerror("Prefixo das imagens", str(exc))
            return False

        if not super().compile_current():
            self.image_sources = backup_sources
            self.image_map = backup_map
            self.description_bindings = backup_bindings
            self._image_prefix_snapshot = backup_prefix
            return False

        if migrated:
            self.status_var.set(
                f"Prefixo atualizado: {migrated} image_id(s) migrados para "
                f"{self._image_prefix_snapshot}."
            )
            self._refresh_reference_gallery()
        return True

    def open_reference_image(self):
        super().open_reference_image()
        self._refresh_reference_gallery()

    def open_reference_batch(self):
        super().open_reference_batch()
        self._refresh_reference_gallery()

    def move_reference(self, delta: int):
        super().move_reference(delta)
        self._refresh_gallery_selection()

    def bind_reference_to_selected_line(self) -> None:
        super().bind_reference_to_selected_line()
        self._refresh_reference_gallery()

    def open_project_dialog(self):
        super().open_project_dialog()
        self._image_prefix_snapshot = slugify(self.image_prefix_var.get(), "imagem")
        self._refresh_reference_gallery()

    def new_project(self):
        super().new_project()
        self._image_prefix_snapshot = slugify(self.image_prefix_var.get(), "imagem")
        self._refresh_reference_gallery()


if __name__ == "__main__":
    app = ScriptEditor()
    app.mainloop()
