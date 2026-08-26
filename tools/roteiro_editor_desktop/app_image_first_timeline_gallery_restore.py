from __future__ import annotations

import os
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from app_image_first import IMAGE_TYPES, load_project
from app_image_first_timeline_gallery import ScriptEditor as GalleryScriptEditor
from project_image_restore import restore_project_image_state
from reference_folder import (
    DEFAULT_REFERENCE_DIR,
    existing_initial_directory,
    reference_directory_from_project,
    reference_images_from_directory,
)


class ScriptEditor(GalleryScriptEditor):
    """Galeria com restauração de projetos e filtro lógico das imagens atribuídas."""

    def __init__(self) -> None:
        super().__init__()
        self.reference_directory_var = tk.StringVar(self, value="Nenhuma pasta informada")
        self._install_assignment_controls()
        self._load_default_reference_directory()
        self._refresh_reference_gallery()

    @staticmethod
    def _path_key(value: str | Path) -> str:
        return os.path.normcase(os.path.abspath(str(value)))

    def _dialog_initial_directory(self) -> str:
        return existing_initial_directory(
            self.reference_directory_var.get(),
            fallbacks=(DEFAULT_REFERENCE_DIR,),
        )

    def _set_reference_directory(self, directory: str | Path) -> int:
        root = Path(directory)
        files = reference_images_from_directory(root)
        self.reference_directory_var.set(str(root))
        self.reference_files = files
        self.reference_index = 0 if files else -1
        self._select_first_available_reference()
        self._refresh_reference_gallery()
        self.status_var.set(
            f"Pasta de imagens: {root} — {len(files)} imagem(ns) encontrada(s)."
        )
        return len(files)

    def select_reference_directory(self) -> None:
        directory = filedialog.askdirectory(
            title="Informe a pasta onde estão as imagens do roteiro",
            initialdir=self._dialog_initial_directory(),
            mustexist=True,
        )
        if directory:
            self._set_reference_directory(directory)

    def _load_default_reference_directory(self) -> None:
        if DEFAULT_REFERENCE_DIR.is_dir():
            self._set_reference_directory(DEFAULT_REFERENCE_DIR)

    def open_reference_image(self):
        source = filedialog.askopenfilename(
            title="Abrir imagem de referência",
            initialdir=self._dialog_initial_directory(),
            filetypes=IMAGE_TYPES,
        )
        if source:
            self.reference_directory_var.set(str(Path(source).parent))
            self.reference_files = [str(source)]
            self.reference_index = 0
            self.show_reference()
            self._refresh_reference_gallery()

    def open_reference_batch(self):
        files = filedialog.askopenfilenames(
            title="Abrir imagens de referência",
            initialdir=self._dialog_initial_directory(),
            filetypes=IMAGE_TYPES,
        )
        if files:
            parents = {str(Path(item).parent) for item in files}
            self.reference_directory_var.set(
                parents.pop() if len(parents) == 1 else "Seleção de várias pastas"
            )
            self.reference_files = [str(item) for item in files]
            self.reference_index = 0
            self._select_first_available_reference()
            self._refresh_reference_gallery()

    def _install_assignment_controls(self) -> None:
        # Mantém a experiência já conhecida do editor: um botão explícito
        # para procurar/carregar um lote de imagens.
        batch = self._find_button("ABRIR LOTE")
        if batch is not None:
            batch.configure(
                text="INFORMAR PASTA DE IMAGENS",
                command=self.select_reference_directory,
                style="Big.TButton",
            )

        assign = self._find_button("USAR IMAGEM ATUAL NESTA LINHA")
        if assign is not None:
            assign.configure(
                text="TROCAR / ATRIBUIR IMAGEM",
                command=self.bind_reference_to_selected_line,
            )
            toolbar = assign.master
            remove = ttk.Button(
                toolbar,
                text="REMOVER IMAGEM DA LINHA",
                command=self.remove_image_from_selected_line,
            )
            remove.pack(side="right", padx=(0, 8), before=assign)

        for widget in self._walk_widgets(self):
            if isinstance(widget, ttk.LabelFrame) and widget.cget("text") == "Galeria de referencias":
                widget.configure(text="Galeria de referências — disponíveis")
                widget.rowconfigure(0, weight=0)
                widget.rowconfigure(1, weight=1)
                for child in widget.winfo_children():
                    info = child.grid_info()
                    if info:
                        child.grid_configure(row=int(info.get("row", 0)) + 1)
                folder_bar = ttk.Frame(widget)
                folder_bar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
                folder_bar.columnconfigure(1, weight=1)
                ttk.Label(folder_bar, text="Pasta das imagens:").grid(row=0, column=0, sticky="w")
                ttk.Label(
                    folder_bar,
                    textvariable=self.reference_directory_var,
                    anchor="w",
                ).grid(row=0, column=1, sticky="ew", padx=(6, 8))
                ttk.Button(
                    folder_bar,
                    text="ALTERAR PASTA",
                    command=self.select_reference_directory,
                ).grid(row=0, column=2, sticky="e")
                break

    def _available_reference_indexes(self) -> list[int]:
        used = {
            self._path_key(source)
            for source in self.image_sources.values()
            if str(source or "").strip()
        }
        return [
            index
            for index, source in enumerate(self.reference_files)
            if self._path_key(source) not in used
        ]

    def _select_first_available_reference(self) -> None:
        available = self._available_reference_indexes()
        if available:
            if self.reference_index not in available:
                self.reference_index = available[0]
            self.show_reference()
        else:
            self.reference_index = -1
            self.preview_image = None
            self.preview_label.configure(
                image="",
                text=(
                    "Nenhuma imagem disponível.\n\n"
                    "Todas as imagens deste lote já foram atribuídas."
                ),
            )
            self.reference_name_var.set("Nenhuma imagem disponível")
            self.reference_count_var.set("Todas as imagens deste lote já foram atribuídas.")

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
                text="Clique em INFORMAR PASTA DE IMAGENS para carregar a galeria.",
                anchor="center",
            ).grid(row=0, column=0, padx=8, pady=24, sticky="ew")
            return

        available = self._available_reference_indexes()
        if not available:
            ttk.Label(
                self._gallery_inner,
                text="Todas as imagens deste lote já foram atribuídas.",
                anchor="center",
            ).grid(row=0, column=0, padx=8, pady=24, sticky="ew")
            if self._gallery_canvas is not None:
                self._gallery_canvas.update_idletasks()
                self._gallery_canvas.configure(scrollregion=self._gallery_canvas.bbox("all"))
            return

        for column in range(self.GALLERY_COLUMNS):
            self._gallery_inner.columnconfigure(column, weight=1)

        for visible_index, source_index in enumerate(available):
            source = self.reference_files[source_index]
            path = Path(source)
            thumb = self._gallery_thumbnail(source)
            row, column = divmod(visible_index, self.GALLERY_COLUMNS)

            button = ttk.Button(
                self._gallery_inner,
                text=path.name,
                image=thumb if thumb is not None else "",
                compound="top",
                command=lambda i=source_index: self._select_gallery_reference(i),
                width=16,
            )
            button.grid(row=row, column=column, padx=4, pady=4, sticky="nsew")
            self._gallery_buttons[source_index] = button

        self._refresh_gallery_selection()
        if self._gallery_canvas is not None:
            self._gallery_canvas.update_idletasks()
            self._gallery_canvas.configure(scrollregion=self._gallery_canvas.bbox("all"))

    def bind_reference_to_selected_line(self) -> None:
        source = self.current_reference()
        if not source:
            messagebox.showinfo("Imagem", "Selecione uma imagem disponível na galeria.")
            return

        super().bind_reference_to_selected_line()

        # A imagem continua fisicamente no mesmo local, mas some da galeria
        # porque agora está registrada em image_sources como atribuída.
        self._select_first_available_reference()
        self._refresh_reference_gallery()

    def remove_image_from_selected_line(self) -> None:
        if not self.rows and not self.compile_current():
            return
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Remover imagem", "Selecione uma linha da timeline.")
            return

        line_id = str(selection[0])
        row = self._row_by_id(line_id)
        if row is None:
            messagebox.showinfo("Remover imagem", "Selecione uma linha narrativa válida.")
            return

        image_id = str(self.image_map.get(line_id, "") or row.get("image_id", "") or "")
        if not image_id:
            messagebox.showinfo(
                "Remover imagem",
                "Esta linha não possui uma imagem própria para remover.",
            )
            return

        old_map = dict(self.image_map)
        old_sources = dict(self.image_sources)
        old_bindings = {
            int(key): dict(value) for key, value in self.description_bindings.items()
        }
        source = str(self.image_sources.get(image_id, "") or "")

        self.image_map.pop(line_id, None)
        self.image_sources.pop(image_id, None)
        for ordinal, binding in list(self.description_bindings.items()):
            if str(binding.get("image_id", "") or "") == image_id:
                self.description_bindings.pop(ordinal, None)

        if not self.compile_current():
            self.image_map = old_map
            self.image_sources = old_sources
            self.description_bindings = old_bindings
            self.compile_current()
            return

        if source:
            source_key = self._path_key(source)
            for index, candidate in enumerate(self.reference_files):
                if self._path_key(candidate) == source_key:
                    self.reference_index = index
                    break

        self._select_first_available_reference()
        self._refresh_reference_gallery()

        if self.tree.exists(line_id):
            self.tree.selection_set(line_id)
            self.tree.see(line_id)

        name = Path(source).name if source else image_id
        self.status_var.set(
            f"Imagem removida de {line_id}. {name} voltou para a galeria disponível."
        )

    def project_payload(self):
        payload = super().project_payload()
        payload["format"] = "roleplay2026-editor-desktop-image-first-v3"
        directory = self.reference_directory_var.get().strip()
        payload["reference_directory"] = (
            "" if directory == "Nenhuma pasta informada" else directory
        )
        return payload

    def apply_project(self, data):
        # Compatibilidade com a versão anterior que chegou a registrar origens
        # para mover arquivos. O novo fluxo não move nada no disco.
        data = dict(data)
        data.pop("assigned_reference_origins", None)
        reference_directory = reference_directory_from_project(data)
        super().apply_project(data)
        self.reference_directory_var.set(reference_directory or "Nenhuma pasta informada")
        if reference_directory and Path(reference_directory).is_dir():
            self.reference_files = reference_images_from_directory(reference_directory)
        self._select_first_available_reference()
        self._refresh_reference_gallery()

    def open_project_dialog(self):
        path = filedialog.askopenfilename(
            title="Abrir projeto",
            filetypes=[("Projeto JSON", "*.json"), ("Todos", "*.*")],
        )
        if not path:
            return

        project_path = Path(path)
        try:
            payload = load_project(project_path)
            payload = restore_project_image_state(
                payload,
                project_path=project_path,
            )
            self.apply_project(payload)
        except Exception as exc:
            messagebox.showerror("Abrir projeto", str(exc))
            return

        self.project_path = project_path
        self._image_prefix_snapshot = self.image_prefix_var.get().strip()
        self._select_first_available_reference()
        self._refresh_reference_gallery()

        assigned = len(self.image_sources)
        available = len(self._available_reference_indexes())
        self.status_var.set(
            f"Projeto aberto: {path} — {assigned} imagem(ns) atribuída(s), "
            f"{available} disponível(is) na galeria."
        )

    def new_project(self):
        super().new_project()
        self.reference_directory_var.set("Nenhuma pasta informada")
        self._load_default_reference_directory()
        self._refresh_reference_gallery()


if __name__ == "__main__":
    app = ScriptEditor()
    app.mainloop()
