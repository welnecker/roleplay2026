from __future__ import annotations

import os
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from app_image_first import load_project, normalize_image_name
from app_image_first_timeline_gallery import ScriptEditor as GalleryScriptEditor
from project_image_restore import restore_project_image_state
from reference_gallery_allocation import (
    archive_reference,
    is_archived_reference,
    restore_reference,
)


class ScriptEditor(GalleryScriptEditor):
    """Galeria com restauração de projetos e separação de imagens atribuídas."""

    def __init__(self) -> None:
        self.assigned_reference_origins: dict[str, str] = {}
        super().__init__()
        self._install_assignment_controls()

    @staticmethod
    def _path_key(value: str | Path) -> str:
        return os.path.normcase(os.path.abspath(str(value)))

    def _install_assignment_controls(self) -> None:
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
                widget.configure(text="Galeria de referências — somente disponíveis")
                break

    def _remove_reference_file(self, source: str) -> None:
        key = self._path_key(source)
        old_index = self.reference_index
        self.reference_files = [
            item for item in self.reference_files if self._path_key(item) != key
        ]
        if self.reference_files:
            self.reference_index = max(0, min(old_index, len(self.reference_files) - 1))
            self.show_reference()
        else:
            self.reference_index = -1
            self.preview_image = None
            self.preview_label.configure(
                image="",
                text="Nenhuma imagem disponível.\n\nAbra outro lote ou remova uma atribuição para devolver a imagem à galeria.",
            )
            self.reference_name_var.set("Nenhuma imagem disponível")
            self.reference_count_var.set("Todas as imagens abertas já foram atribuídas.")

    def _add_reference_file(self, source: str) -> None:
        key = self._path_key(source)
        if all(self._path_key(item) != key for item in self.reference_files):
            self.reference_files.append(source)
        if self.reference_index < 0 and self.reference_files:
            self.reference_index = 0
            self.show_reference()

    def _sync_binding_source(self, image_id: str, source: str) -> None:
        for binding in self.description_bindings.values():
            if str(binding.get("image_id", "") or "") == image_id:
                binding["source"] = source

    def _archive_image_source(self, image_id: str, source: str) -> str:
        archived, original = archive_reference(source)
        archived_text = str(archived)
        self.image_sources[image_id] = archived_text
        self.assigned_reference_origins[image_id] = str(original)
        self._sync_binding_source(image_id, archived_text)
        self._remove_reference_file(source)
        self._refresh_reference_gallery()
        return archived_text

    def _source_used_by_other_image(self, image_id: str, source: str) -> bool:
        source_key = self._path_key(source)
        for other_id, other_source in self.image_sources.items():
            if other_id == image_id:
                continue
            if self._path_key(other_source) == source_key:
                return True
        return False

    def _release_image_source(
        self,
        image_id: str,
        *,
        source_override: str = "",
        origin_override: str = "",
    ) -> str:
        source = source_override or str(self.image_sources.get(image_id, "") or "")
        origin = origin_override or str(self.assigned_reference_origins.get(image_id, "") or "")
        restored_source = ""

        if source and not self._source_used_by_other_image(image_id, source):
            source_path = Path(source)
            managed = bool(origin) or is_archived_reference(source_path)
            if managed and source_path.exists() and source_path.is_file():
                restored_source = str(
                    restore_reference(source_path, Path(origin) if origin else None)
                )
                self._add_reference_file(restored_source)
            elif source_path.exists() and source_path.is_file():
                # Projeto antigo: não move o arquivo sem conhecer sua origem,
                # mas o devolve à galeria se ele já for uma referência válida.
                restored_source = str(source_path)
                self._add_reference_file(restored_source)

        self.image_sources.pop(image_id, None)
        self.assigned_reference_origins.pop(image_id, None)
        self._refresh_reference_gallery()
        return restored_source

    def allocate_binding(self, ordinal: int, source: str):
        previous = dict(self.description_bindings.get(ordinal, {}))
        previous_id = str(previous.get("image_id", "") or "")
        previous_source = str(self.image_sources.get(previous_id, "") or previous.get("source", "") or "")
        previous_origin = str(self.assigned_reference_origins.get(previous_id, "") or "")

        super().allocate_binding(ordinal, source)
        current = self.description_bindings[ordinal]
        image_id = str(current.get("image_id", "") or "")
        try:
            archived = self._archive_image_source(image_id, source)
            current["source"] = archived
        except Exception:
            self.description_bindings.pop(ordinal, None)
            self.image_sources.pop(image_id, None)
            if previous:
                self.description_bindings[ordinal] = previous
                if previous_id and previous_source:
                    self.image_sources[previous_id] = previous_source
                if previous_id and previous_origin:
                    self.assigned_reference_origins[previous_id] = previous_origin
            raise

        if previous_id and previous_id != image_id:
            self._release_image_source(
                previous_id,
                source_override=previous_source,
                origin_override=previous_origin,
            )

    def bind_reference_to_selected_line(self) -> None:
        source = self.current_reference()
        if not source:
            messagebox.showinfo("Imagem", "Selecione uma imagem disponível na galeria.")
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

        old_map = dict(self.image_map)
        old_sources = dict(self.image_sources)
        old_bindings = {int(key): dict(value) for key, value in self.description_bindings.items()}
        old_origins = dict(self.assigned_reference_origins)

        previous_id = str(self.image_map.get(line_id, "") or row.get("image_id", "") or "")
        previous_source = str(self.image_sources.get(previous_id, "") or "") if previous_id else ""
        previous_origin = str(self.assigned_reference_origins.get(previous_id, "") or "") if previous_id else ""

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
            self.image_map = old_map
            self.image_sources = old_sources
            self.description_bindings = old_bindings
            self.assigned_reference_origins = old_origins
            self.compile_current()
            return

        try:
            archived = self._archive_image_source(image_id, source)
            self._sync_binding_source(image_id, archived)
            if previous_id and previous_id != image_id:
                self._release_image_source(
                    previous_id,
                    source_override=previous_source,
                    origin_override=previous_origin,
                )
        except Exception as exc:
            self.image_map = old_map
            self.image_sources = old_sources
            self.description_bindings = old_bindings
            self.assigned_reference_origins = old_origins
            self.compile_current()
            messagebox.showerror("Imagem", f"Não foi possível reorganizar a galeria:\n{exc}")
            return

        if self.tree.exists(line_id):
            self.tree.selection_set(line_id)
            self.tree.see(line_id)
        self.status_var.set(
            f"{line_id} → {image_id}. A referência saiu da galeria e foi para _atribuidas."
        )

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
        old_bindings = {int(key): dict(value) for key, value in self.description_bindings.items()}
        old_origins = dict(self.assigned_reference_origins)
        source = str(self.image_sources.get(image_id, "") or "")
        origin = str(self.assigned_reference_origins.get(image_id, "") or "")

        self.image_map.pop(line_id, None)
        for ordinal, binding in list(self.description_bindings.items()):
            if str(binding.get("image_id", "") or "") == image_id:
                self.description_bindings.pop(ordinal, None)

        if not self.compile_current():
            self.image_map = old_map
            self.image_sources = old_sources
            self.description_bindings = old_bindings
            self.assigned_reference_origins = old_origins
            self.compile_current()
            return

        try:
            restored = self._release_image_source(
                image_id,
                source_override=source,
                origin_override=origin,
            )
        except Exception as exc:
            self.image_map = old_map
            self.image_sources = old_sources
            self.description_bindings = old_bindings
            self.assigned_reference_origins = old_origins
            self.compile_current()
            messagebox.showerror("Remover imagem", f"Não foi possível devolver a imagem à galeria:\n{exc}")
            return

        if self.tree.exists(line_id):
            self.tree.selection_set(line_id)
            self.tree.see(line_id)
        name = Path(restored or source).name if (restored or source) else image_id
        self.status_var.set(
            f"Imagem removida de {line_id}. {name} voltou para a galeria disponível."
        )

    def project_payload(self):
        payload = super().project_payload()
        payload["format"] = "roleplay2026-editor-desktop-image-first-v3"
        payload["assigned_reference_origins"] = dict(self.assigned_reference_origins)
        return payload

    def apply_project(self, data):
        raw_origins = data.get("assigned_reference_origins") or {}
        if isinstance(raw_origins, dict):
            self.assigned_reference_origins = {
                str(image_id): str(origin)
                for image_id, origin in raw_origins.items()
                if str(image_id or "").strip() and str(origin or "").strip()
            }
        else:
            self.assigned_reference_origins = {}
        super().apply_project(data)
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
        self._refresh_reference_gallery()

        restored = len(self.image_sources)
        available = len(self.reference_files)
        if restored:
            self.status_var.set(
                f"Projeto aberto: {path} — {restored} imagem(ns) atribuída(s), "
                f"{available} disponível(is) na galeria."
            )
        else:
            self.status_var.set(f"Projeto aberto: {path} — nenhuma imagem local encontrada.")

    def new_project(self):
        super().new_project()
        if (
            not self.draft.get("1.0", "end-1c").strip()
            and not self.image_sources
            and not self.rows
        ):
            self.assigned_reference_origins = {}


if __name__ == "__main__":
    app = ScriptEditor()
    app.mainloop()
