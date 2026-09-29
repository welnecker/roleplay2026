from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from core import (
    CardDraft,
    CardEditorError,
    NewCardSpec,
    apply_card_draft,
    create_card_package,
    import_cover_into_package,
    load_manifest,
    manifest_to_draft,
    new_manifest,
    relative_cover_path,
    save_manifest,
    sync_starter_files,
)

try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None


class CardEditorApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Configurador de Cards • EntreCenas")
        self.geometry("1240x820")
        self.minsize(1040, 720)

        self.mode = "idle"
        self.manifest_path: Path | None = None
        self.new_parent_dir: Path | None = None
        self.payload: dict = {}
        self.cover_photo = None
        self.pending_cover_source: Path | None = None

        self.vars = {
            "package_id": tk.StringVar(),
            "version": tk.StringVar(value="1.0.0"),
            "author_id": tk.StringVar(value="welnecker"),
            "author_name": tk.StringVar(value="Welnecker"),
            "title": tk.StringVar(),
            "subtitle": tk.StringVar(),
            "genres": tk.StringVar(),
            "chapter_label": tk.StringVar(value="História completa"),
            "cover": tk.StringVar(),
            "profile_name": tk.StringVar(),
            "price_brl": tk.StringVar(value="9,90"),
            "replay_policy": tk.StringVar(value="new_purchase"),
        }
        self.status = tk.StringVar(
            value="Escolha NOVO CARD para criar um pacote ou ABRIR MANIFEST.YAML para editar."
        )
        self._build()

    def _build(self) -> None:
        toolbar = ttk.Frame(self, padding=10)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="NOVO CARD", command=self.new_card).pack(side="left")
        ttk.Button(
            toolbar,
            text="ABRIR MANIFEST.YAML",
            command=self.open_manifest,
        ).pack(side="left", padx=8)
        ttk.Button(
            toolbar,
            text="ESCOLHER CAPA",
            command=self.choose_cover,
        ).pack(side="left")
        self.save_button = ttk.Button(
            toolbar,
            text="SALVAR CARD",
            command=self.save,
        )
        self.save_button.pack(side="right")

        info = ttk.Frame(self, padding=(10, 0, 10, 8))
        info.pack(fill="x")
        self.mode_label = ttk.Label(info, text="Nenhum card aberto")
        self.mode_label.pack(side="left")
        ttk.Label(
            info,
            text="  •  O card abre grátis; o Pix é acionado pela tag [PAGAMENTO].",
        ).pack(side="left")

        body = ttk.Panedwindow(self, orient="horizontal")
        body.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        form_container = ttk.Frame(body)
        preview = ttk.Frame(body, padding=12)
        body.add(form_container, weight=3)
        body.add(preview, weight=2)

        canvas = tk.Canvas(form_container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(form_container, orient="vertical", command=canvas.yview)
        self.form = ttk.Frame(canvas, padding=12)
        self.form.bind(
            "<Configure>",
            lambda _e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=self.form, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._build_form(self.form)
        self._build_preview(preview)

        ttk.Label(
            self,
            textvariable=self.status,
            anchor="w",
            padding=(10, 6),
        ).pack(fill="x")

        for var in self.vars.values():
            var.trace_add("write", lambda *_: self.refresh_preview())

    def _entry(self, parent, label, key, row, *, structural=False) -> ttk.Entry:
        ttk.Label(parent, text=label).grid(
            row=row,
            column=0,
            sticky="w",
            pady=(7, 2),
        )
        entry = ttk.Entry(parent, textvariable=self.vars[key])
        entry.grid(row=row + 1, column=0, sticky="ew")
        if structural:
            setattr(self, f"{key}_entry", entry)
        return entry

    def _text(self, parent, label, row, height=4) -> tk.Text:
        ttk.Label(parent, text=label).grid(
            row=row,
            column=0,
            sticky="w",
            pady=(7, 2),
        )
        widget = tk.Text(parent, height=height, wrap="word")
        widget.grid(row=row + 1, column=0, sticky="nsew")
        return widget

    def _build_form(self, parent) -> None:
        parent.columnconfigure(0, weight=1)

        ttk.Label(
            parent,
            text="ESTRUTURA DO PACOTE",
            font=("Segoe UI", 11, "bold"),
        ).grid(row=0, column=0, sticky="w")
        self._entry(parent, "package_id", "package_id", 1, structural=True)
        self._entry(parent, "Versão", "version", 3, structural=True)
        self._entry(parent, "ID do autor", "author_id", 5, structural=True)
        self._entry(parent, "Nome do autor", "author_name", 7, structural=True)

        ttk.Separator(parent).grid(row=9, column=0, sticky="ew", pady=12)
        ttk.Label(
            parent,
            text="FRENTE DO CARD",
            font=("Segoe UI", 11, "bold"),
        ).grid(row=10, column=0, sticky="w")
        self._entry(parent, "Título", "title", 11)
        self._entry(parent, "Subtítulo", "subtitle", 13)
        self.description = self._text(parent, "Descrição da frente", 15, 4)
        self._entry(parent, "Gêneros (separados por vírgula)", "genres", 17)
        self._entry(parent, "Rótulo do capítulo", "chapter_label", 19)
        self._entry(parent, "Capa (caminho no pacote)", "cover", 21)

        ttk.Separator(parent).grid(row=23, column=0, sticky="ew", pady=12)
        ttk.Label(
            parent,
            text="VERSO / PERFIL",
            font=("Segoe UI", 11, "bold"),
        ).grid(row=24, column=0, sticky="w")
        self._entry(parent, "Nome do perfil", "profile_name", 25)
        self.identity = self._text(parent, "Quem é", 27, 3)
        self.personality = self._text(parent, "Como é", 29, 3)
        self.intention = self._text(parent, "O que pretende com você", 31, 3)

        commerce = ttk.LabelFrame(parent, text="Comércio", padding=10)
        commerce.grid(row=33, column=0, sticky="ew", pady=12)
        commerce.columnconfigure(1, weight=1)
        ttk.Label(commerce, text="Preço (R$)").grid(row=0, column=0, sticky="w")
        ttk.Entry(
            commerce,
            textvariable=self.vars["price_brl"],
            width=14,
        ).grid(row=0, column=1, sticky="w", padx=8)
        ttk.Label(commerce, text="Política de replay").grid(
            row=1,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        ttk.Combobox(
            commerce,
            textvariable=self.vars["replay_policy"],
            state="readonly",
            values=("new_purchase", "reuse_access"),
            width=20,
        ).grid(row=1, column=1, sticky="w", padx=8, pady=(8, 0))

        ttk.Label(
            parent,
            text=(
                "O manifesto comercial permanece access=paid. Isso não cobra na abertura: "
                "o usuário avança gratuitamente até [PAGAMENTO]."
            ),
            wraplength=650,
        ).grid(row=34, column=0, sticky="w", pady=(0, 8))

        for widget in (
            self.description,
            self.identity,
            self.personality,
            self.intention,
        ):
            widget.bind("<KeyRelease>", lambda _e: self.refresh_preview())

        self._set_structural_state(editable=False)

    def _build_preview(self, parent) -> None:
        ttk.Label(
            parent,
            text="PRÉVIA DO CARD",
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w")
        self.cover_label = ttk.Label(parent, text="Sem capa", anchor="center")
        self.cover_label.pack(fill="x", pady=10)

        tabs = ttk.Notebook(parent)
        tabs.pack(fill="both", expand=True)
        front = ttk.Frame(tabs, padding=18)
        back = ttk.Frame(tabs, padding=18)
        tabs.add(front, text="FRENTE")
        tabs.add(back, text="VERSO")

        self.front_title = ttk.Label(
            front,
            font=("Segoe UI", 20, "bold"),
            wraplength=400,
        )
        self.front_title.pack(anchor="w")
        self.front_subtitle = ttk.Label(front, font=("Segoe UI", 11), wraplength=400)
        self.front_subtitle.pack(anchor="w", pady=(6, 10))
        self.front_genres = ttk.Label(front, wraplength=400)
        self.front_genres.pack(anchor="w")
        self.front_description = ttk.Label(front, wraplength=400, justify="left")
        self.front_description.pack(anchor="w", pady=12)
        ttk.Label(
            front,
            text="COMECE GRÁTIS",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", pady=(12, 0))
        ttk.Label(front, text="Abrir história").pack(anchor="w", pady=(4, 0))

        self.back_name = ttk.Label(
            back,
            font=("Segoe UI", 18, "bold"),
            wraplength=400,
        )
        self.back_name.pack(anchor="w")
        self.back_identity = ttk.Label(back, wraplength=400, justify="left")
        self.back_identity.pack(anchor="w", pady=10)
        self.back_personality = ttk.Label(back, wraplength=400, justify="left")
        self.back_personality.pack(anchor="w", pady=10)
        self.back_intention = ttk.Label(back, wraplength=400, justify="left")
        self.back_intention.pack(anchor="w", pady=10)
        self.back_price = ttk.Label(back, font=("Segoe UI", 11, "bold"))
        self.back_price.pack(anchor="w", pady=(18, 0))

    def _set_structural_state(self, *, editable: bool) -> None:
        state = "normal" if editable else "readonly"
        for key in ("package_id", "version", "author_id", "author_name"):
            getattr(self, f"{key}_entry").configure(state=state)

    @staticmethod
    def _get_text(widget: tk.Text) -> str:
        return widget.get("1.0", "end").strip()

    @staticmethod
    def _set_text(widget: tk.Text, value: str) -> None:
        widget.delete("1.0", "end")
        widget.insert("1.0", value or "")

    def _clear_card_fields(self) -> None:
        defaults = {
            "package_id": "roleplay2026.",
            "version": "1.0.0",
            "author_id": "welnecker",
            "author_name": "Welnecker",
            "title": "",
            "subtitle": "",
            "genres": "",
            "chapter_label": "História completa",
            "cover": "",
            "profile_name": "",
            "price_brl": "9,90",
            "replay_policy": "new_purchase",
        }
        for key, value in defaults.items():
            self.vars[key].set(value)
        for widget in (
            self.description,
            self.identity,
            self.personality,
            self.intention,
        ):
            self._set_text(widget, "")
        self.pending_cover_source = None
        self.cover_photo = None
        self.cover_label.configure(image="", text="Sem capa")

    def new_card(self) -> None:
        parent = filedialog.askdirectory(
            title="Escolha a pasta onde o novo pacote será criado"
        )
        if not parent:
            return
        self.mode = "new"
        self.manifest_path = None
        self.new_parent_dir = Path(parent)
        self.payload = {}
        self._clear_card_fields()
        self._set_structural_state(editable=True)
        self.mode_label.configure(text="NOVO CARD")
        self.save_button.configure(text="GERAR NOVO CARD")
        self.status.set(
            "Preencha o card. O manifest.yaml será criado somente ao clicar em GERAR NOVO CARD."
        )
        self.package_id_entry.focus_set()
        self.refresh_preview()

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

        self.mode = "edit"
        self.new_parent_dir = None
        self.manifest_path = Path(filename)
        self.payload = payload
        self.pending_cover_source = None

        self.vars["package_id"].set(str(payload.get("package_id", "") or ""))
        self.vars["version"].set(str(payload.get("version", "") or ""))
        author = dict(payload.get("author") or {})
        self.vars["author_id"].set(str(author.get("id", "") or ""))
        self.vars["author_name"].set(str(author.get("name", "") or ""))
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

        self._set_structural_state(editable=False)
        self.mode_label.configure(
            text=f"EDITANDO • {payload.get('package_id', '—')}"
        )
        self.save_button.configure(text="SALVAR CARD")
        self.status.set(f"Aberto: {self.manifest_path}")
        self.refresh_preview()
        self.refresh_cover()

    def choose_cover(self) -> None:
        if self.mode == "idle":
            messagebox.showinfo(
                "Card",
                "Escolha NOVO CARD ou abra um manifest.yaml primeiro.",
            )
            return
        filename = filedialog.askopenfilename(
            title="Selecione a capa",
            filetypes=[("Imagens", "*.webp *.png *.jpg *.jpeg")],
        )
        if not filename:
            return
        source = Path(filename)
        self.pending_cover_source = source

        if self.mode == "new":
            self.vars["cover"].set(f"assets/capas/capa{source.suffix.lower()}")
        elif self.manifest_path is not None:
            self.vars["cover"].set(relative_cover_path(self.manifest_path, source))
        self.refresh_cover(source)

    def _resolve_cover(self) -> Path | None:
        if self.pending_cover_source and self.pending_cover_source.is_file():
            return self.pending_cover_source
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
            image.thumbnail((420, 270))
            self.cover_photo = ImageTk.PhotoImage(image)
            self.cover_label.configure(image=self.cover_photo, text="")
        except Exception:
            self.cover_label.configure(
                image="",
                text="Não foi possível visualizar a capa.",
            )
            self.cover_photo = None

    def refresh_preview(self) -> None:
        if not hasattr(self, "front_title"):
            return
        self.front_title.configure(text=self.vars["title"].get() or "Título do card")
        self.front_subtitle.configure(text=self.vars["subtitle"].get())
        self.front_genres.configure(text=self.vars["genres"].get().strip())
        self.front_description.configure(
            text=self._get_text(self.description) if hasattr(self, "description") else ""
        )
        self.back_name.configure(
            text=self.vars["profile_name"].get() or self.vars["title"].get()
        )
        self.back_identity.configure(
            text="QUEM É\n"
            + (self._get_text(self.identity) if hasattr(self, "identity") else "")
        )
        self.back_personality.configure(
            text="COMO É\n"
            + (
                self._get_text(self.personality)
                if hasattr(self, "personality")
                else ""
            )
        )
        self.back_intention.configure(
            text="O QUE PRETENDE COM VOCÊ\n"
            + (self._get_text(self.intention) if hasattr(self, "intention") else "")
        )
        self.back_price.configure(
            text=f"Continuação: R$ {self.vars['price_brl'].get() or '0,00'}"
        )

    def _draft(self) -> CardDraft:
        return CardDraft(
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

    def _new_spec(self) -> NewCardSpec:
        return NewCardSpec(
            package_id=self.vars["package_id"].get(),
            version=self.vars["version"].get(),
            author_id=self.vars["author_id"].get(),
            author_name=self.vars["author_name"].get(),
        )

    def save(self) -> None:
        if self.mode == "idle":
            messagebox.showinfo(
                "Card",
                "Escolha NOVO CARD ou abra um manifest.yaml primeiro.",
            )
            return

        draft = self._draft()
        try:
            if self.mode == "new":
                if self.new_parent_dir is None:
                    raise CardEditorError("Escolha a pasta de destino do novo card.")
                spec = self._new_spec()
                # Valida tudo antes de criar qualquer pasta em disco.
                preview_payload = apply_card_draft(new_manifest(spec), draft)
                manifest_path, _base_payload = create_card_package(
                    self.new_parent_dir,
                    spec,
                )
                self.manifest_path = manifest_path
                updated = preview_payload
                if self.pending_cover_source is not None:
                    updated["card"]["cover"] = import_cover_into_package(
                        manifest_path,
                        self.pending_cover_source,
                    )
                save_manifest(manifest_path, updated)
                sync_starter_files(manifest_path, updated)
                self.payload = updated
                self.mode = "edit"
                self.new_parent_dir = None
                self.pending_cover_source = None
                self._set_structural_state(editable=False)
                self.mode_label.configure(
                    text=f"EDITANDO • {updated['package_id']}"
                )
                self.save_button.configure(text="SALVAR CARD")
                self.vars["cover"].set(str(updated["card"].get("cover", "") or ""))
                self.status.set(f"Novo pacote criado em {manifest_path.parent}")
                messagebox.showinfo(
                    "EntreCenas",
                    "Novo card criado com manifest.yaml e estrutura inicial do pacote.",
                )
                return

            if self.manifest_path is None:
                raise CardEditorError("Manifesto não selecionado.")
            updated = apply_card_draft(self.payload, draft)
            if self.pending_cover_source is not None:
                updated["card"]["cover"] = import_cover_into_package(
                    self.manifest_path,
                    self.pending_cover_source,
                )
                self.vars["cover"].set(updated["card"]["cover"])
            save_manifest(self.manifest_path, updated)
            sync_starter_files(self.manifest_path, updated)
            self.payload = updated
            self.pending_cover_source = None
        except CardEditorError as exc:
            messagebox.showerror("Erro", str(exc))
            return

        self.status.set(f"Card salvo em {self.manifest_path}")
        messagebox.showinfo("EntreCenas", "Card atualizado com sucesso.")


def main() -> None:
    app = CardEditorApp()
    app.mainloop()


if __name__ == "__main__":
    main()
