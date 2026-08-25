from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox

from app_image_first import load_project
from app_image_first_timeline_gallery import ScriptEditor as GalleryScriptEditor
from project_image_restore import restore_project_image_state


class ScriptEditor(GalleryScriptEditor):
    """Galeria atual com recuperação resiliente das imagens de projetos salvos."""

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
        if restored:
            self.status_var.set(
                f"Projeto aberto: {path} — {restored} imagem(ns) restaurada(s)."
            )
        else:
            self.status_var.set(f"Projeto aberto: {path} — nenhuma imagem local encontrada.")


if __name__ == "__main__":
    app = ScriptEditor()
    app.mainloop()
