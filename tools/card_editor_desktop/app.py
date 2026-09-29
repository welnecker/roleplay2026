from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from core import CardDraft, CardEditorError, apply_card_draft, load_manifest, manifest_to_draft, relative_cover_path, save_manifest

try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None


class CardEditorApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Configurador de Cards • EntreCenas")
        self.geometry("1180x760")
        self.minsize(980, 680)
        self.manifest_path: Path | None = None
        self.payload: dict = {}
        self.cover_photo = None

        self.vars = {
            "title": tk.StringVar(),
            "subtitle": tk.StringVar(),
            "genres": tk.StringVar(),
            "chapter_label": tk.StringVar(),
            "cover": tk.StringVar(),
            "profile_name": tk.StringVar(),
            "price_brl": tk.StringVar(value="9,90"),
            "replay_policy": tk.StringVar(value="new_purchase"),
        }
        self.status = tk.StringVar(value="Abra um manifest.yaml para começar.")
        self._build()

    def _build(self) -> None:
        toolbar = ttk.Frame(self, padding=10)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="ABRIR MANIFEST.YAML", command=self.open_manifest).pack(side="left")
        ttk.Button(toolbar, text="ESCOLHER CAPA", command=self.choose_cover).pack(side="left", padx=8)
        ttk.Button(toolbar, text="SALVAR CARD", command=self.save).pack(side="right")

        info = ttk.Frame(self, padding=(10, 0, 10, 8))
        info.pack(fill="x")
        self.package_label = ttk.Label(info, text="package_id: —")
        self.package_label.pack(side="left")
        ttk.Label(
            info,
            text="  •  Card abre grátis; Pix é acionado pela tag [PAGAMENTO] do roteiro.",
        ).pack(side="left")

        body = ttk.Panedwindow(self, orient="horizontal")
        body.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        form = ttk.Frame(body, padding=12)
        preview = ttk.Frame(body, padding=12)
        body.add(form, weight=3)
        body.add(preview, weight=2)

        self._build_form(form)
        self._build_preview(preview)

        ttk.Label(self, textvariable=self.status, anchor="w", padding=(10, 6)).pack(fill="x")

        for var in self.vars.values():
            var.trace_add("write", lambda *_: self.refresh_preview())

    def _entry(self, parent, label, key, row) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=(7, 2))
        ttk.Entry(parent, textvariable=self.vars[key]).grid(row=row + 1, column=0, sticky="ew")

    def _text(self, parent, label, row, height=4):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=(7, 2))
        widget = tk.Text(parent, height=height, wrap="word")
        widget.grid(row=row + 1, column=0, sticky="nsew")
        return widget

    def _build_form(self, parent) -> None:
        parent.columnconfigure(0, weight=1)
        self._entry(parent, "Título", "title", 0)
        self._entry(parent, "Subtítulo", "subtitle", 2)
        self.description = self._text(parent, "Descrição da frente", 4, 4)
        self._entry(parent, "Gêneros (separados por vírgula)", "genres", 6)
        self._entry(parent, "Rótulo do capítulo", "chapter_label", 8)
        self._entry(parent, "Capa (caminho no pacote)", "cover", 10)

        ttk.Separator(parent).grid(row=12, column=0, sticky="ew", pady=12)
        ttk.Label(parent, text="VERSO / PERFIL", font=("Segoe UI", 11, "bold")).grid(row=13, column=0, sticky="w")

        self._entry(parent, "Nome do perfil", "profile_name", 14)
        self.identity = self._text(parent, "Quem é", 16, 3)
        self.personality = self._text(parent, "Como é", 18, 3)
        self.intention = self._text(parent, "O que pretende com você", 20, 3)

        commerce = ttk.LabelFrame(parent, text="Comércio", padding=10)
        commerce.grid(row=22, column=0, sticky="ew", pady=12)
        commerce.columnconfigure(1, weight=1)
        ttk.Label(commerce, text="Preço (R$)").grid(row=0, column=0, sticky="w")
        ttk.Entry(commerce, textvariable=self.vars["price_brl"], width=14).grid(row=0, column=1, sticky="w", padx=8)
        ttk.Label(commerce, text="Nova compra ao rejogar").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Combobox(
            commerce,
            textvariable=self.vars["replay_policy"],
            state="readonly",
            values=("new_purchase", "reuse_access"),
            width=20,
        ).grid(row=1, column=1, sticky="w", padx=8, pady=(8, 0))

        ttk.Label(
            parent,
            text="O configurador mantém access=paid. O trecho inicial gratuito é controlado pelo roteiro até [PAGAMENTO].",
            wraplength=620,
        ).grid(row=23, column=0, sticky="w", pady=(0, 8))

        for text_widget in (self.description, self.identity, self.personality, self.intention):
            text_widget.bind("<KeyRelease>", lambda _e: self.refresh_preview())

    def _build_preview(self, parent) -> None:
        ttk.Label(parent, text="PRÉVIA DO CARD", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.cover_label = ttk.Label(parent, text="Sem capa", anchor="center")
        self.cover_label.pack(fill="x", pady=10)

        tabs = ttk.Notebook(parent)
        tabs.pack(fill="both", expand=True)
        front = ttk.Frame(tabs, padding=18)
        back = ttk.Frame(tabs, padding=18)
        tabs.add(front, text="FRENTE")
        tabs.add(back, text="VERSO")

        self.front_title = ttk.Label(front, font=("Segoe UI", 20, "bold"), wraplength=380)
        self.front_title.pack(anchor="w")
        self.front_subtitle = ttk.Label(front, font=("Segoe UI", 11), wraplength=380)
        self.front_subtitle.pack(anchor="w", pady=(6, 10))
        self.front_genres = ttk.Label(front, wraplength=380)
        self.front_genres.pack(anchor="w")
        self.front_description = ttk.Label(front, wraplength=380, justify="left")
        self.front_description.pack(anchor="w", pady=12)
        ttk.Label(front, text="COMECE GRÁTIS", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(12, 0))
        ttk.Label(front, text="Abrir história").pack(anchor="w", pady=(4, 0))

        self.back_name = ttk.Label(back, font=("Segoe UI", 18, "bold"), wraplength=380)
        self.back_name.pack(anchor="w")
        self.back_identity = ttk.Label(back, wraplength=380, justify="left")
        self.back_identity.pack(anchor="w", pady=10)
        self.back_personality = ttk.Label(back, wraplength=380, justify="left")
        self.back_personality.pack(anchor="w", pady=10)
        self.back_intention = ttk.Label(back, wraplength=380, justify="left")
        self.back_intention.pack(anchor="w", pady=10)
        self.back_price = ttk.Label(back, font=("Segoe UI", 11, "bold"))
        self.back_price.pack(anchor="w", pady=(18, 0))

    @staticmethod
    def _get_text(widget: tk.Text) -> str:
        return widget.get("1.0", "end").strip()

    @staticmethod
    def _set_text(widget: tk.Text, value: str) -> None:
        widget.delete("1.0", "end")
        widget.insert("1.0", value or "")

    def open_manifest(self) -> None:
        filename = filedialog.askopenfilename(
            title="Selecione o manifest.yaml do card",
            filetypes=[("Manifest YAML", "manifest.yaml"), ("YAML", "*.yaml *.yml")],
        )
        if not filename:
            return
        try:
            payload = load_manifest(Path(filename))
            draft = manifest_to_draft(payload)
        except CardEditorError as exc:
            messagebox.showerror("Erro", str(exc))
            return
        self.manifest_path = Path(filename)
        self.payload = payload
        self.vars["title"].set(draft.title)
        self.vars["subtitle"].set(draft.subtitle)
        self.vars["genres"].set(draft.genres)
        self.vars["chapter_label"].set(draft.chapter_label)
        self.vars["cover"].set(draft.cover)
        self.vars["profile_name"].set(draft.profile_name)
        self.vars["price_brl"].set(draft.price_brl)
        self.vars["replay_policy"].set(draft.replay_policy)
        self._set_text(self.description, draft.description)
        self._set_text(self.identity, draft.profile_identity)
        self._set_text(self.personality, draft.profile_personality)
        self._set_text(self.intention, draft.profile_intention)
        self.package_label.configure(text=f"package_id: {payload.get('package_id', '—')}")
        self.status.set(f"Aberto: {self.manifest_path}")
        self.refresh_preview()
        self.refresh_cover()

    def choose_cover(self) -> None:
        if self.manifest_path is None:
            messagebox.showinfo("Card", "Abra primeiro o manifest.yaml.")
            return
        filename = filedialog.askopenfilename(
            title="Selecione a capa",
            filetypes=[("Imagens", "*.webp *.png *.jpg *.jpeg")],
        )
        if not filename:
            return
        self.vars["cover"].set(relative_cover_path(self.manifest_path, Path(filename)))
        self.refresh_cover(Path(filename))

    def _resolve_cover(self) -> Path | None:
        if self.manifest_path is None:
            return None
        raw = self.vars["cover"].get().strip()
        if not raw or raw.startswith(("http://", "https://", "data:")):
            return None
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = self.manifest_path.parent / candidate
        return candidate if candidate.is_file() else None

    def refresh_cover(self, explicit: Path | None = None) -> None:
        target = explicit or self._resolve_cover()
        if not target or Image is None or ImageTk is None:
            self.cover_label.configure(image="", text="Capa externa ou não localizada")
            self.cover_photo = None
            return
        try:
            image = Image.open(target)
            image.thumbnail((400, 260))
            self.cover_photo = ImageTk.PhotoImage(image)
            self.cover_label.configure(image=self.cover_photo, text="")
        except Exception:
            self.cover_label.configure(image="", text="Não foi possível visualizar a capa.")
            self.cover_photo = None

    def refresh_preview(self) -> None:
        self.front_title.configure(text=self.vars["title"].get() or "Título do card")
        self.front_subtitle.configure(text=self.vars["subtitle"].get())
        genres = self.vars["genres"].get().strip()
        self.front_genres.configure(text=genres)
        self.front_description.configure(text=self._get_text(self.description) if hasattr(self, "description") else "")
        self.back_name.configure(text=self.vars["profile_name"].get() or self.vars["title"].get())
        self.back_identity.configure(text="QUEM É\n" + (self._get_text(self.identity) if hasattr(self, "identity") else ""))
        self.back_personality.configure(text="COMO É\n" + (self._get_text(self.personality) if hasattr(self, "personality") else ""))
        self.back_intention.configure(text="O QUE PRETENDE COM VOCÊ\n" + (self._get_text(self.intention) if hasattr(self, "intention") else ""))
        self.back_price.configure(text=f"Continuação: R$ {self.vars['price_brl'].get() or '0,00'}")

    def save(self) -> None:
        if self.manifest_path is None:
            messagebox.showinfo("Card", "Abra primeiro o manifest.yaml.")
            return
        draft = CardDraft(
            title=self.vars["title"].get(),
            subtitle=self.vars["subtitle"].get(),
            description=self._get_text(self.description),
            genres=self.vars["genres"].get(),
            chapter_label=self.vars["chapter_label"].get(),
            cover=self.vars["cover"].get(),
            profile_name=self.vars["profile_name"].get(),
            profile_identity=self._get_text(self.identity),
            profile_personality=self._get_text(self.personality),
            profile_intention=self._get_text(self.intention),
            price_brl=self.vars["price_brl"].get(),
            replay_policy=self.vars["replay_policy"].get(),
        )
        try:
            updated = apply_card_draft(self.payload, draft)
            save_manifest(self.manifest_path, updated)
        except CardEditorError as exc:
            messagebox.showerror("Erro", str(exc))
            return
        self.payload = updated
        self.status.set(f"Card salvo em {self.manifest_path}")
        messagebox.showinfo("EntreCenas", "Card atualizado com sucesso.")


def main() -> None:
    app = CardEditorApp()
    app.mainloop()


if __name__ == "__main__":
    main()
