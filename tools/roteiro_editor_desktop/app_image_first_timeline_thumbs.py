from __future__ import annotations

from pathlib import Path

from app_image_first import Image, ImageTk
from app_image_first_timeline import ScriptEditor as TimelineScriptEditor


class ScriptEditor(TimelineScriptEditor):
    """Timeline visual com thumbnail apenas em linhas com image_id explícito."""

    THUMB_SIZE = (52, 52)

    def __init__(self) -> None:
        self._timeline_thumbnails: dict[str, object] = {}
        super().__init__()
        self.title("Editor de Roteiros ROLEPLAY2026 — Timeline visual com miniaturas")

    def _configure_timeline_tree(self) -> None:
        super()._configure_timeline_tree()
        # Aumenta apenas o suficiente para acomodar a miniatura sem deixar
        # a timeline com aparência de galeria.
        try:
            self.tree.master.winfo_toplevel().style.configure("Treeview", rowheight=58)
        except Exception:
            from tkinter import ttk

            ttk.Style(self).configure("Treeview", rowheight=58)

    def _thumbnail_for(self, image_id: str):
        if not image_id or Image is None or ImageTk is None:
            return None
        source = str(self.image_sources.get(image_id, "") or "").strip()
        if not source:
            return None
        path = Path(source)
        if not path.exists() or not path.is_file():
            return None
        try:
            with Image.open(path) as opened:
                preview = opened.convert("RGB")
                preview.thumbnail(self.THUMB_SIZE)
                thumb = ImageTk.PhotoImage(preview)
        except Exception:
            return None
        self._timeline_thumbnails[image_id] = thumb
        return thumb

    def refresh_tree(self) -> None:
        selected = self.tree.selection()
        selected_id = str(selected[0]) if selected else ""
        self.tree.delete(*self.tree.get_children())
        self._timeline_thumbnails.clear()

        current_parent = ""
        frame_number = 0
        for row in self.rows:
            line_id = str(row["line_id"])
            instruction = str(row.get("instruction", ""))
            image_id = str(row.get("image_id", "") or "")
            values = (row["order"], line_id, instruction, image_id)
            thumb = self._thumbnail_for(image_id)

            if line_id.endswith("_descricao"):
                frame_number += 1
                current_parent = line_id
                label = f"QUADRO {frame_number:02d}"
                if image_id:
                    label += f"  •  {image_id}"
                kwargs = {
                    "iid": line_id,
                    "text": label,
                    "values": values,
                    "open": True,
                    "tags": ("frame",),
                }
                if thumb is not None:
                    kwargs["image"] = thumb
                self.tree.insert("", "end", **kwargs)
                continue

            label = "FALA"
            upper = instruction.upper()
            if upper.startswith("[PENSAMENTO"):
                label = "PENSAMENTO"
            elif upper.startswith("[FALA EXATA"):
                label = "FALA EXATA"
            elif upper.startswith("[FALA INTERPRETADA") or upper.startswith("[FALA INTERPRETATIVA"):
                label = "FALA INTERPRETADA"
            elif "_BALAO]" in upper:
                label = "FALA BALÃO"
            if "_BALAO]" in upper and label != "FALA BALÃO":
                label += " BALÃO"
            if image_id:
                label += f"  •  {image_id}"

            kwargs = {
                "iid": line_id,
                "text": label,
                "values": values,
            }
            if thumb is not None:
                kwargs["image"] = thumb
            self.tree.insert(
                current_parent if current_parent and self.tree.exists(current_parent) else "",
                "end",
                **kwargs,
            )

        self.tree.tag_configure("frame", font=("Segoe UI", 9, "bold"))
        if selected_id and self.tree.exists(selected_id):
            self.tree.selection_set(selected_id)
            self.tree.see(selected_id)


if __name__ == "__main__":
    app = ScriptEditor()
    app.mainloop()
