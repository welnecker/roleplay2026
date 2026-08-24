from __future__ import annotations

import re
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from app_image_first_balao import ScriptEditor as BalloonScriptEditor
from app_image_first import normalize_image_name, slugify

_TAG = re.compile(r"^\s*\[([^\]]+)\]\s*(.*)$", re.DOTALL)


class ScriptEditor(BalloonScriptEditor):
    """Editor imagem-primeiro com visão de quadros, imagem por linha e edição."""

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
        self.tree.bind("<Double-1>", self._on_tree_double_click)

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
            toolbar = old.master
            edit = ttk.Button(
                toolbar,
                text="EDITAR LINHA SELECIONADA",
                command=self.edit_selected_line,
            )
            edit.pack(side="right", padx=(0, 8), before=old)

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

    def _row_index(self, line_id: str) -> int:
        for index, row in enumerate(self.rows):
            if str(row.get("line_id", "")) == line_id:
                return index
        return -1

    def _parse_instruction(self, instruction: str) -> tuple[str, str, str]:
        match = _TAG.match(str(instruction or ""))
        if match is None:
            return "", "", str(instruction or "").strip()
        header = " ".join(match.group(1).strip().split())
        body = str(match.group(2) or "").strip()
        parts = header.split(maxsplit=1)
        kind = parts[0].upper()
        actor = parts[1].strip() if len(parts) > 1 else ""
        if kind == "DESCRIÇÃO" or kind == "DESCRICAO":
            return "DESCRIÇÃO", "", body
        if kind == "PENSAMENTO":
            return "PENSAMENTO", actor, body
        if kind == "FALA" and actor.lower().endswith("_balao"):
            return "FALA BALÃO", actor[:-6].rstrip("_"), body
        if kind == "FALA":
            return "FALA", actor, body
        return kind, actor, body

    def _instruction_from_editor(self, kind: str, actor: str, body: str) -> str:
        clean_body = str(body or "").strip()
        if not clean_body:
            raise ValueError("O texto da linha não pode ficar vazio.")
        if kind == "DESCRIÇÃO":
            return f"[DESCRIÇÃO] {clean_body}"
        clean_actor = slugify(actor, "")
        if not clean_actor:
            raise ValueError("Selecione um ator válido.")
        if kind == "FALA BALÃO":
            return f"[FALA {clean_actor}_balao] {clean_body}"
        if kind == "PENSAMENTO":
            return f"[PENSAMENTO {clean_actor}] {clean_body}"
        return f"[FALA {clean_actor}] {clean_body}"

    def _replace_row_instruction(self, line_id: str, new_instruction: str) -> str:
        index = self._row_index(line_id)
        if index < 0:
            raise ValueError("A linha selecionada não existe mais no roteiro atual.")

        old_image_id = str(self.image_map.get(line_id, "") or self.rows[index].get("image_id", "") or "")
        old_source = str(self.image_sources.get(old_image_id, "") or "") if old_image_id else ""
        instructions = [str(row.get("instruction", "")).strip() for row in self.rows]
        instructions[index] = new_instruction
        self.draft.delete("1.0", "end")
        self.draft.insert("1.0", "\n\n".join(instructions))

        # Recompila uma primeira vez para descobrir o novo line_id da mesma posição.
        old_map = dict(self.image_map)
        old_map.pop(line_id, None)
        self.image_map = old_map
        if not self.compile_current():
            raise ValueError("A alteração tornou o roteiro inválido.")
        if index >= len(self.rows):
            raise ValueError("A alteração removeu a linha inesperadamente.")
        new_line_id = str(self.rows[index]["line_id"])

        # Migra a imagem da linha editada para o novo id, caso o tipo/ator tenha mudado.
        if old_image_id:
            self.image_map[new_line_id] = old_image_id
            if old_source:
                self.image_sources[old_image_id] = old_source

        # Se era/continua sendo descrição, sincroniza o binding ordinal da imagem-primeiro.
        descriptions = [
            item
            for item in self.rows
            if str(item.get("line_id", "")).endswith("_descricao")
        ]
        description_ids = [str(item["line_id"]) for item in descriptions]
        if new_line_id in description_ids and old_image_id:
            ordinal = description_ids.index(new_line_id) + 1
            self.description_bindings[ordinal] = {
                "source": old_source,
                "image_id": old_image_id,
            }

        if not self.compile_current():
            raise ValueError("Não foi possível recompilar a linha alterada.")
        return new_line_id

    def _on_tree_double_click(self, event) -> None:
        row_id = self.tree.identify_row(event.y)
        if row_id:
            self.tree.selection_set(row_id)
            self.edit_selected_line()

    def edit_selected_line(self) -> None:
        if not self.rows and not self.compile_current():
            return
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Editar linha", "Selecione uma linha da timeline.")
            return
        line_id = str(selection[0])
        row = self._row_by_id(line_id)
        if row is None:
            messagebox.showinfo("Editar linha", "Selecione uma linha narrativa válida.")
            return

        kind, actor, body = self._parse_instruction(str(row.get("instruction", "")))
        is_description = kind == "DESCRIÇÃO"

        dialog = tk.Toplevel(self)
        dialog.title(f"Editar — {line_id}")
        dialog.transient(self)
        dialog.grab_set()
        dialog.geometry("650x420")
        dialog.minsize(560, 360)
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(4, weight=1)

        ttk.Label(dialog, text="Tipo").grid(row=0, column=0, sticky="w", padx=14, pady=(14, 3))
        kind_var = tk.StringVar(value=kind)
        kind_combo = ttk.Combobox(
            dialog,
            textvariable=kind_var,
            state="readonly",
            values=("DESCRIÇÃO",) if is_description else ("FALA", "PENSAMENTO", "FALA BALÃO"),
        )
        kind_combo.grid(row=1, column=0, sticky="ew", padx=14)

        ttk.Label(dialog, text="Ator").grid(row=2, column=0, sticky="w", padx=14, pady=(10, 3))
        actor_values = [
            slugify(raw.strip(), "")
            for raw in self.actors_var.get().replace(";", ",").split(",")
            if slugify(raw.strip(), "")
        ]
        if "usuario" not in actor_values:
            actor_values.append("usuario")
        actor_var = tk.StringVar(value=actor or (actor_values[0] if actor_values else "usuario"))
        actor_combo = ttk.Combobox(dialog, textvariable=actor_var, state="readonly", values=actor_values)
        actor_combo.grid(row=3, column=0, sticky="ew", padx=14)
        if is_description:
            actor_combo.configure(state="disabled")

        text_frame = ttk.Frame(dialog)
        text_frame.grid(row=4, column=0, sticky="nsew", padx=14, pady=(12, 8))
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(1, weight=1)
        ttk.Label(text_frame, text="Texto").grid(row=0, column=0, sticky="w", pady=(0, 3))
        editor = tk.Text(text_frame, wrap="word", undo=True, font=("Segoe UI", 11), padx=8, pady=8)
        editor.grid(row=1, column=0, sticky="nsew")
        editor.insert("1.0", body)
        editor.focus_set()

        image_id = str(row.get("image_id", "") or "")
        image_note = f"Imagem vinculada: {image_id}" if image_id else "Sem image_id próprio (herda a imagem anterior)."
        ttk.Label(dialog, text=image_note).grid(row=5, column=0, sticky="w", padx=14, pady=(0, 8))

        actions = ttk.Frame(dialog)
        actions.grid(row=6, column=0, sticky="ew", padx=14, pady=(0, 14))
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)

        def save() -> None:
            try:
                instruction = self._instruction_from_editor(
                    kind_var.get(),
                    actor_var.get(),
                    editor.get("1.0", "end-1c"),
                )
                new_line_id = self._replace_row_instruction(line_id, instruction)
            except Exception as exc:
                messagebox.showerror("Editar linha", str(exc), parent=dialog)
                return
            dialog.destroy()
            if self.tree.exists(new_line_id):
                self.tree.selection_set(new_line_id)
                self.tree.see(new_line_id)
            self.status_var.set(f"Linha atualizada: {new_line_id}")

        ttk.Button(actions, text="Cancelar", command=dialog.destroy).grid(row=0, column=0, sticky="ew", padx=(0, 5))
        ttk.Button(actions, text="SALVAR ALTERAÇÃO", command=save).grid(row=0, column=1, sticky="ew", padx=(5, 0))

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
