from __future__ import annotations

from pathlib import Path
from tkinter import messagebox, ttk

from app_image_first_balao import ScriptEditor as BalloonScriptEditor
from app_image_first import normalize_image_name


class ScriptEditor(BalloonScriptEditor):
    """Editor imagem-primeiro com visão de quadros e imagem por linha."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Editor de Roteiros ROLEPLAY2026 — Timeline visual")
        self._configure_timeline_tree()
        self._install_timeline_controls()
        if self.rows:
            self.refresh_tree()

    def _configure_timeline_tree(self) -> None:
        self.tree.configure(show="tree headings")
        self.tree.heading("#0", text="Quadro / linha")
        self.tree.column("#0", width=185, minwidth=150, stretch=False)

    def _walk_widgets(self, widget):
        yield widget
        for child in widget.winfo_children():
            yield from self._walk_widgets(child)

    def _find_button(self, text: str):
        for widget in self._walk_widgets(self):
            if isinstance(widget, ttk.Button) and widget.cget("text") == text:
                return widget
        return None

    def _install_timeline_controls(self) -> None:
        old = self._find_button("Usar imagem atual na DESCRIÇÃO selecionada")
        if old is not None:
            old.configure(
                text="USAR IMAGEM ATUAL NESTA LINHA",
                command=self.bind_reference_to_selected_line,
            )

        description_button = self._find_button("+ DESCRIÇÃO DESTA IMAGEM")
        if description_button is not None:
            toolbar = description_button.master
            new_frame = ttk.Button(
                toolbar,
                text="+ NOVO QUADRO",
                command=self.insert_description_from_reference,
            )
            new_frame.pack(side="left", padx=(0, 8), after=description_button)

    def _row_by_id(self, line_id: str):
        for row in self.rows:
            if str(row.get("line_id", "")) == line_id:
                return row
        return None

    def bind_reference_to_selected_line(self) -> None:
        source = self.current_reference()
        if not source:
            messagebox.showinfo("Imagem", "Abra uma imagem de referência primeiro.")
            return
        if not self.rows and not self.compile_current():
            return

        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo(
                "Linha",
                "Selecione uma DESCRIÇÃO, FALA, FALA BALÃO ou PENSAMENTO na timeline.",
            )
            return

        line_id = str(selection[0])
        row = self._row_by_id(line_id)
        if row is None:
            messagebox.showinfo("Linha", "Selecione uma linha narrativa válida.")
            return

        previous = str(self.image_map.get(line_id, "") or "")
        if previous:
            self.image_sources.pop(previous, None)

        image_id = normalize_image_name(self.image_prefix_var.get(), self.next_image_number())
        self.image_map[line_id] = image_id
        self.image_sources[image_id] = source

        # Se a linha for uma DESCRIÇÃO, a associação por ordinal continua coerente
        # com o fluxo imagem-primeiro, inclusive após reabrir o projeto.
        descriptions = [
            item
            for item in self.rows
            if str(item.get("line_id", "")).endswith("_descricao")
        ]
        description_ids = [str(item["line_id"]) for item in descriptions]
        if line_id in description_ids:
            ordinal = description_ids.index(line_id) + 1
            self.description_bindings[ordinal] = {
                "source": source,
                "image_id": image_id,
            }

        if not self.compile_current():
            return
        if self.tree.exists(line_id):
            self.tree.selection_set(line_id)
            self.tree.see(line_id)
        self.status_var.set(
            f"{line_id} → {image_id} ({Path(source).name}). Continue o quadro ou avance a imagem."
        )

    def refresh_tree(self) -> None:
        selected = self.tree.selection()
        selected_id = str(selected[0]) if selected else ""
        self.tree.delete(*self.tree.get_children())

        current_parent = ""
        frame_number = 0
        for row in self.rows:
            line_id = str(row["line_id"])
            instruction = str(row.get("instruction", ""))
            image_id = str(row.get("image_id", "") or "")
            values = (row["order"], line_id, instruction, image_id)

            if line_id.endswith("_descricao"):
                frame_number += 1
                current_parent = line_id
                label = f"QUADRO {frame_number:02d}"
                if image_id:
                    label += f"  •  {image_id}"
                self.tree.insert(
                    "",
                    "end",
                    iid=line_id,
                    text=label,
                    values=values,
                    open=True,
                    tags=("frame",),
                )
                continue

            label = "FALA"
            upper = instruction.upper()
            if upper.startswith("[PENSAMENTO"):
                label = "PENSAMENTO"
            elif "_BALAO]" in upper:
                label = "FALA BALÃO"
            if image_id:
                label += f"  •  {image_id}"

            self.tree.insert(
                current_parent if current_parent and self.tree.exists(current_parent) else "",
                "end",
                iid=line_id,
                text=label,
                values=values,
            )

        self.tree.tag_configure("frame", font=("Segoe UI", 9, "bold"))
        if selected_id and self.tree.exists(selected_id):
            self.tree.selection_set(selected_id)
            self.tree.see(selected_id)


if __name__ == "__main__":
    app = ScriptEditor()
    app.mainloop()
