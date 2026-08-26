from __future__ import annotations

from tkinter import ttk

from app_image_first import ScriptEditor as BaseScriptEditor, slugify


class ScriptEditor(BaseScriptEditor):
    """Extensão fina do editor imagem-primeiro com atalho para fala-balão."""

    def __init__(self) -> None:
        super().__init__()
        self._install_balloon_button()

    def insert_balloon_tag(self) -> None:
        actor = slugify(self.actor_var.get(), "usuario")
        if actor.endswith("_balao"):
            tagged_actor = actor
        else:
            tagged_actor = f"{actor}_balao"
        self.insert_tag(f"[FALA {tagged_actor}] ")

    def insert_speech_tag(self, delivery: str) -> None:
        actor = slugify(self.actor_var.get(), "usuario")
        self.insert_tag(f"[FALA {delivery} {actor}] ")

    def _install_balloon_button(self) -> None:
        fala_button = None
        for widget in self.winfo_children():
            for child in widget.winfo_children():
                for grandchild in child.winfo_children():
                    if isinstance(grandchild, ttk.Button) and grandchild.cget("text") == "+ FALA":
                        fala_button = grandchild
                        break
                if fala_button is not None:
                    break
            if fala_button is not None:
                break
        if fala_button is None:
            return

        toolbar = fala_button.master
        exact = ttk.Button(
            toolbar,
            text="+ FALA EXATA",
            command=lambda: self.insert_speech_tag("EXATA"),
        )
        exact.pack(side="left", padx=3, after=fala_button)
        interpreted = ttk.Button(
            toolbar,
            text="+ FALA INTERPRETADA",
            command=lambda: self.insert_speech_tag("INTERPRETADA"),
        )
        interpreted.pack(side="left", padx=3, after=exact)
        balloon = ttk.Button(toolbar, text="+ FALA BALÃO", command=self.insert_balloon_tag)
        balloon.pack(side="left", padx=3, after=interpreted)


if __name__ == "__main__":
    app = ScriptEditor()
    app.mainloop()
