from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from app_image_first_timeline_gallery_restore import ScriptEditor as GalleryScriptEditor
from core import (
    EditorError,
    cast_members_from_legacy_actors,
    normalize_cast_members,
    slugify,
    validate_draft_cast,
)


_GENDER_LABELS = {
    "feminine": "Feminino",
    "masculine": "Masculino",
    "neutral": "Neutro",
}
_LABEL_GENDERS = {label: value for value, label in _GENDER_LABELS.items()}


def default_cast_members() -> list[dict[str, str]]:
    return [
        {
            "actor_id": "camilly",
            "label": "A personagem",
            "default_name": "Camilly",
            "gender": "feminine",
        },
        {
            "actor_id": "usuario",
            "label": "O participante",
            "default_name": "Usuário",
            "gender": "neutral",
        },
    ]


class ScriptEditor(GalleryScriptEditor):
    """Editor V2 com elenco ilimitado e nomes personalizáveis por run."""

    def __init__(self) -> None:
        self.cast_members = default_cast_members()
        super().__init__()
        self.title("Editor de Roteiros ROLEPLAY2026 — Elenco personalizável")
        self._install_cast_controls()
        self._refresh_actor_values()

    def _install_cast_controls(self) -> None:
        configure = self._find_button("Atualizar atores")
        if configure is not None:
            configure.configure(
                text="CONFIGURAR ELENCO",
                command=self.open_cast_editor,
                style="Big.TButton",
            )

        for widget in self._walk_widgets(self):
            if isinstance(widget, ttk.Label) and widget.cget("text") == "Personagens (vírgulas)":
                widget.configure(text="Elenco (IDs estruturais)")
                for sibling in widget.master.winfo_children():
                    if isinstance(sibling, ttk.Entry):
                        sibling.configure(state="readonly")
                break

        name_button = self._find_button("+ {{nome}}")
        if name_button is not None:
            name_button.configure(
                text="+ NOME DO ATOR",
                command=self.insert_selected_actor_name,
            )
        for legacy in ("+ {{*nome}}", "+ {{**nome}}"):
            button = self._find_button(legacy)
            if button is not None:
                button.pack_forget()

        validate_button = self._find_button("Validar / atualizar")
        if validate_button is not None:
            ttk.Button(
                validate_button.master,
                text="+ SMACK!",
                command=lambda: self.insert_tag("[ONOMATOPEIA smack x=69 y=48 delay=350]"),
            ).pack(side="right", padx=4, before=validate_button)
            ttk.Button(
                validate_button.master,
                text="+ FIM DA HISTÓRIA",
                command=lambda: self.insert_tag("[FIM_HISTORIA]"),
            ).pack(side="right", padx=4, before=validate_button)

    def _refresh_actor_values(self) -> None:
        try:
            members = normalize_cast_members(self.cast_members)
        except (AttributeError, EditorError):
            members = cast_members_from_legacy_actors(self.actors_var.get())
            self.cast_members = members
        actor_ids = [member["actor_id"] for member in members]
        self.actors_var.set(", ".join(actor_ids))
        self.actor_combo["values"] = actor_ids
        if self.actor_var.get() not in actor_ids:
            self.actor_var.set(actor_ids[0])

    def insert_selected_actor_name(self) -> None:
        actor_id = slugify(self.actor_var.get(), fallback="")
        if not actor_id:
            messagebox.showinfo("Nome do personagem", "Selecione um personagem do elenco.")
            return
        self.insert_tag(f"{{{{nome:{actor_id}}}}}", spacing=False)

    def compile_current(self) -> bool:
        try:
            self.cast_members = validate_draft_cast(
                self.draft.get("1.0", "end-1c"),
                self.cast_members,
            )
        except Exception as exc:
            messagebox.showerror("Elenco inválido", str(exc))
            self.status_var.set("Há erros no elenco ou nas tags de personagens.")
            return False
        return super().compile_current()

    def project_payload(self):
        payload = super().project_payload()
        payload["format"] = "roleplay2026-editor-desktop-cast-v1"
        payload["cast_members"] = normalize_cast_members(self.cast_members)
        payload["actors"] = ", ".join(
            member["actor_id"] for member in payload["cast_members"]
        )
        return payload

    def apply_project(self, data):
        data = dict(data)
        raw_cast = data.get("cast_members")
        self.cast_members = (
            normalize_cast_members(raw_cast)
            if raw_cast
            else cast_members_from_legacy_actors(data.get("actors", "usuario"))
        )
        data["actors"] = ", ".join(
            member["actor_id"] for member in self.cast_members
        )
        super().apply_project(data)
        self._refresh_actor_values()

    def open_cast_editor(self) -> None:
        working = [dict(member) for member in normalize_cast_members(self.cast_members)]

        dialog = tk.Toplevel(self)
        dialog.title("Elenco personalizável da história")
        dialog.transient(self)
        dialog.grab_set()
        dialog.geometry("900x610")
        dialog.minsize(760, 540)
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=1)

        ttk.Label(
            dialog,
            text=(
                "Cadastre quantos personagens a trama precisar. O ID permanece no roteiro; "
                "o nome inicial poderá ser trocado pelo usuário antes de uma nova run."
            ),
            wraplength=850,
        ).grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))

        columns = ("label", "default_name", "gender", "actor_id")
        list_frame = ttk.Frame(dialog)
        list_frame.grid(row=1, column=0, sticky="nsew", padx=14)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
        )
        tree.heading("label", text="Papel na trama")
        tree.heading("default_name", text="Nome inicial")
        tree.heading("gender", text="Gênero estrutural")
        tree.heading("actor_id", text="ID estrutural / tags")
        tree.column("label", width=250)
        tree.column("default_name", width=170)
        tree.column("gender", width=140)
        tree.column("actor_id", width=190)
        tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        tree.configure(yscrollcommand=scrollbar.set)

        form = ttk.LabelFrame(dialog, text="Personagem", padding=10)
        form.grid(row=2, column=0, sticky="ew", padx=14, pady=10)
        for column in range(4):
            form.columnconfigure(column, weight=1)

        label_var = tk.StringVar()
        name_var = tk.StringVar()
        gender_var = tk.StringVar(value="Neutro")
        actor_var = tk.StringVar()

        def field(title, variable, column, *, values=None):
            ttk.Label(form, text=title).grid(row=0, column=column, sticky="w", padx=4)
            if values is None:
                control = ttk.Entry(form, textvariable=variable)
            else:
                control = ttk.Combobox(
                    form,
                    textvariable=variable,
                    values=values,
                    state="readonly",
                )
            control.grid(row=1, column=column, sticky="ew", padx=4, pady=(3, 0))
            return control

        field("Papel (ex.: A vizinha)", label_var, 0)
        field("Nome inicial (ex.: Sandra)", name_var, 1)
        field("Gênero", gender_var, 2, values=tuple(_LABEL_GENDERS))
        actor_entry = field("ID (ex.: vizinha)", actor_var, 3)

        selected_index: int | None = None

        def refresh_tree(select: int | None = None) -> None:
            tree.delete(*tree.get_children())
            for index, member in enumerate(working):
                tree.insert(
                    "",
                    "end",
                    iid=str(index),
                    values=(
                        member["label"],
                        member["default_name"],
                        _GENDER_LABELS[member["gender"]],
                        member["actor_id"],
                    ),
                )
            if select is not None and tree.exists(str(select)):
                tree.selection_set(str(select))
                tree.see(str(select))

        def clear_form() -> None:
            nonlocal selected_index
            selected_index = None
            label_var.set("")
            name_var.set("")
            gender_var.set("Neutro")
            actor_var.set("")
            actor_entry.configure(state="normal")
            tree.selection_remove(tree.selection())

        def load_selection(_event=None) -> None:
            nonlocal selected_index
            selection = tree.selection()
            if not selection:
                return
            selected_index = int(selection[0])
            member = working[selected_index]
            label_var.set(member["label"])
            name_var.set(member["default_name"])
            gender_var.set(_GENDER_LABELS[member["gender"]])
            actor_var.set(member["actor_id"])
            actor_entry.configure(state="readonly")

        def save_member() -> None:
            nonlocal selected_index
            candidate = {
                "actor_id": actor_var.get() or slugify(name_var.get() or label_var.get(), ""),
                "label": label_var.get(),
                "default_name": name_var.get(),
                "gender": _LABEL_GENDERS.get(gender_var.get(), "neutral"),
            }
            proposal = [dict(member) for member in working]
            if selected_index is None:
                proposal.append(candidate)
                target = len(proposal) - 1
            else:
                proposal[selected_index] = candidate
                target = selected_index
            try:
                normalized = normalize_cast_members(proposal)
            except EditorError as exc:
                messagebox.showerror("Personagem inválido", str(exc), parent=dialog)
                return
            working[:] = normalized
            refresh_tree(target)
            load_selection()

        def remove_member() -> None:
            selection = tree.selection()
            if not selection:
                return
            if len(working) == 1:
                messagebox.showinfo(
                    "Elenco",
                    "A história precisa manter ao menos um personagem.",
                    parent=dialog,
                )
                return
            working.pop(int(selection[0]))
            refresh_tree()
            clear_form()

        tree.bind("<<TreeviewSelect>>", load_selection)
        refresh_tree(0)
        load_selection()

        editor_actions = ttk.Frame(dialog)
        editor_actions.grid(row=3, column=0, sticky="ew", padx=14)
        ttk.Button(editor_actions, text="NOVO PERSONAGEM", command=clear_form).pack(side="left")
        ttk.Button(editor_actions, text="REMOVER", command=remove_member).pack(side="left", padx=6)
        ttk.Button(editor_actions, text="ADICIONAR / ATUALIZAR", command=save_member).pack(side="right")

        footer = ttk.Frame(dialog)
        footer.grid(row=4, column=0, sticky="ew", padx=14, pady=14)
        footer.columnconfigure(0, weight=1)
        footer.columnconfigure(1, weight=1)

        def apply_cast() -> None:
            try:
                normalized = normalize_cast_members(working)
                draft = self.draft.get("1.0", "end-1c")
                if draft.strip():
                    validate_draft_cast(draft, normalized)
            except EditorError as exc:
                messagebox.showerror("Elenco inválido", str(exc), parent=dialog)
                return
            self.cast_members = normalized
            self._refresh_actor_values()
            dialog.destroy()
            self.status_var.set(
                f"Elenco atualizado: {len(normalized)} personagem(ns)."
            )

        ttk.Button(footer, text="Cancelar", command=dialog.destroy).grid(
            row=0, column=0, sticky="ew", padx=(0, 5)
        )
        ttk.Button(footer, text="SALVAR ELENCO", command=apply_cast).grid(
            row=0, column=1, sticky="ew", padx=(5, 0)
        )


if __name__ == "__main__":
    ScriptEditor().mainloop()
