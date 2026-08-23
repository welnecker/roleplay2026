from __future__ import annotations

import json
import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

HERE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from core import (  # noqa: E402
    COLUMNS,
    EditorError,
    compile_rows,
    export_package,
    load_project,
    normalize_image_name,
    save_project,
    slugify,
)

try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None


APP_TITLE = "Editor de Roteiros ROLEPLAY2026"


class ScriptEditor(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1500x900")
        self.minsize(1180, 720)

        self.rows: list[dict[str, object]] = []
        self.image_map: dict[str, str] = {}
        self.image_sources: dict[str, str] = {}
        self.preview_image = None
        self.project_path: Path | None = None

        self.package_var = tk.StringVar(value="roleplay2026.camilly")
        self.version_var = tk.StringVar(value="200")
        self.frame_prefix_var = tk.StringVar(value="encontro")
        self.start_order_var = tk.IntVar(value=10)
        self.order_step_var = tk.IntVar(value=10)
        self.start_frame_var = tk.IntVar(value=1)
        self.actors_var = tk.StringVar(value="camilly, usuario")
        self.actor_var = tk.StringVar(value="camilly")
        self.image_prefix_var = tk.StringVar(value="camilly")
        self.image_start_var = tk.IntVar(value=1)
        self.quality_var = tk.IntVar(value=88)
        self.max_side_var = tk.IntVar(value=1800)
        self.status_var = tk.StringVar(value="Pronto.")

        self._build_style()
        self._build_ui()
        self._refresh_actor_values()

    def _build_style(self) -> None:
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Treeview", rowheight=26)
        style.configure("Header.TLabel", font=("Segoe UI", 11, "bold"))

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(1, weight=1)

        top = ttk.Frame(self, padding=10)
        top.grid(row=0, column=0, columnspan=2, sticky="ew")
        for index in range(8):
            top.columnconfigure(index, weight=1)

        self._labeled_entry(top, "package_id", self.package_var, 0, 0, 2)
        self._labeled_entry(top, "script_version", self.version_var, 0, 2)
        self._labeled_entry(top, "Prefixo dos quadros", self.frame_prefix_var, 0, 3)
        self._labeled_spin(top, "Primeira order", self.start_order_var, 0, 4, 0, 999999, 10)
        self._labeled_spin(top, "Intervalo", self.order_step_var, 0, 5, 1, 1000, 1)
        self._labeled_spin(top, "Primeiro quadro", self.start_frame_var, 0, 6, 1, 99999, 1)

        ttk.Button(top, text="Novo projeto", command=self.new_project).grid(row=0, column=7, padx=4, pady=(19, 0), sticky="ew")

        self._labeled_entry(top, "Personagens (vírgulas)", self.actors_var, 1, 0, 2)
        ttk.Button(top, text="Atualizar atores", command=self._refresh_actor_values).grid(row=1, column=2, padx=4, pady=(19, 0), sticky="ew")
        self._labeled_entry(top, "Prefixo das imagens", self.image_prefix_var, 1, 3)
        self._labeled_spin(top, "Primeira imagem", self.image_start_var, 1, 4, 1, 99999, 1)
        self._labeled_spin(top, "Qualidade WebP", self.quality_var, 1, 5, 1, 100, 1)
        self._labeled_spin(top, "Máx. lado (px)", self.max_side_var, 1, 6, 256, 8000, 64)
        ttk.Button(top, text="Salvar projeto", command=self.save_project_dialog).grid(row=1, column=7, padx=4, pady=(19, 0), sticky="ew")

        left = ttk.Frame(self, padding=(10, 0, 5, 10))
        left.grid(row=1, column=0, sticky="nsew")
        left.columnconfigure(0, weight=1)
        left.rowconfigure(2, weight=2)
        left.rowconfigure(5, weight=2)

        ttk.Label(left, text="Roteiro V2", style="Header.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 5))

        toolbar = ttk.Frame(left)
        toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        ttk.Button(toolbar, text="+ DESCRIÇÃO", command=lambda: self.insert_tag("[DESCRIÇÃO] ")).pack(side="left", padx=(0, 4))
        ttk.Label(toolbar, text="Ator:").pack(side="left", padx=(8, 3))
        self.actor_combo = ttk.Combobox(toolbar, textvariable=self.actor_var, state="readonly", width=18)
        self.actor_combo.pack(side="left", padx=(0, 4))
        ttk.Button(toolbar, text="+ FALA", command=lambda: self.insert_actor_tag("FALA")).pack(side="left", padx=3)
        ttk.Button(toolbar, text="+ PENSAMENTO", command=lambda: self.insert_actor_tag("PENSAMENTO")).pack(side="left", padx=3)
        ttk.Button(toolbar, text="+ {{nome}}", command=lambda: self.insert_tag("{{nome}}", spacing=False)).pack(side="left", padx=8)
        ttk.Button(toolbar, text="Validar / atualizar linhas", command=self.compile_current, style="Accent.TButton").pack(side="right")

        text_frame = ttk.Frame(left)
        text_frame.grid(row=2, column=0, sticky="nsew")
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        self.draft = tk.Text(text_frame, wrap="word", undo=True, font=("Segoe UI", 11), padx=10, pady=10)
        self.draft.grid(row=0, column=0, sticky="nsew")
        draft_scroll = ttk.Scrollbar(text_frame, orient="vertical", command=self.draft.yview)
        draft_scroll.grid(row=0, column=1, sticky="ns")
        self.draft.configure(yscrollcommand=draft_scroll.set)

        table_toolbar = ttk.Frame(left)
        table_toolbar.grid(row=3, column=0, sticky="ew", pady=(8, 5))
        ttk.Label(table_toolbar, text="Linhas geradas", style="Header.TLabel").pack(side="left")
        ttk.Button(table_toolbar, text="Atribuir imagens às DESCRIÇÕES", command=self.bulk_assign_descriptions).pack(side="right", padx=3)
        ttk.Button(table_toolbar, text="Remover imagem", command=self.remove_selected_image).pack(side="right", padx=3)
        ttk.Button(table_toolbar, text="Imagem nesta linha", command=self.assign_selected_image).pack(side="right", padx=3)

        table_frame = ttk.Frame(left)
        table_frame.grid(row=5, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        columns = ("order", "line_id", "instruction", "image_id")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("order", text="order")
        self.tree.heading("line_id", text="line_id")
        self.tree.heading("instruction", text="instruction")
        self.tree.heading("image_id", text="image_id")
        self.tree.column("order", width=70, anchor="center", stretch=False)
        self.tree.column("line_id", width=300, stretch=False)
        self.tree.column("instruction", width=650)
        self.tree.column("image_id", width=170, stretch=False)
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        table_scroll_y = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        table_scroll_y.grid(row=0, column=1, sticky="ns")
        table_scroll_x = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        table_scroll_x.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=table_scroll_y.set, xscrollcommand=table_scroll_x.set)

        right = ttk.Frame(self, padding=(5, 0, 10, 10))
        right.grid(row=1, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(2, weight=1)

        ttk.Label(right, text="Imagem da linha selecionada", style="Header.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.selected_line_label = ttk.Label(right, text="Nenhuma linha selecionada", wraplength=520)
        self.selected_line_label.grid(row=1, column=0, sticky="ew", pady=(0, 5))

        preview_box = ttk.Frame(right, relief="sunken", borderwidth=1)
        preview_box.grid(row=2, column=0, sticky="nsew")
        preview_box.columnconfigure(0, weight=1)
        preview_box.rowconfigure(0, weight=1)
        self.preview_label = ttk.Label(preview_box, text="Selecione uma linha e atribua uma imagem.", anchor="center")
        self.preview_label.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

        actions = ttk.Frame(right)
        actions.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        for i in range(2):
            actions.columnconfigure(i, weight=1)
        ttk.Button(actions, text="Abrir projeto", command=self.open_project_dialog).grid(row=0, column=0, padx=(0, 4), pady=3, sticky="ew")
        ttk.Button(actions, text="Salvar projeto", command=self.save_project_dialog).grid(row=0, column=1, padx=(4, 0), pady=3, sticky="ew")
        ttk.Button(actions, text="EXPORTAR ROTEIRO + IMAGENS", command=self.export_dialog).grid(row=1, column=0, columnspan=2, pady=6, sticky="ew")

        ttk.Separator(right).grid(row=4, column=0, sticky="ew", pady=10)
        ttk.Label(
            right,
            text="Saída: roteiro.xlsx + roteiro.csv + roteiro.tsv + projeto_roteiro.json + pasta imagens/ com WebP numerados.",
            wraplength=520,
            justify="left",
        ).grid(row=5, column=0, sticky="ew")

        status = ttk.Label(self, textvariable=self.status_var, relief="sunken", anchor="w", padding=(8, 3))
        status.grid(row=2, column=0, columnspan=2, sticky="ew")

    def _labeled_entry(self, parent, label, variable, row, column, span=1) -> None:
        box = ttk.Frame(parent)
        box.grid(row=row, column=column, columnspan=span, sticky="ew", padx=4, pady=3)
        box.columnconfigure(0, weight=1)
        ttk.Label(box, text=label).grid(row=0, column=0, sticky="w")
        ttk.Entry(box, textvariable=variable).grid(row=1, column=0, sticky="ew")

    def _labeled_spin(self, parent, label, variable, row, column, minimum, maximum, increment) -> None:
        box = ttk.Frame(parent)
        box.grid(row=row, column=column, sticky="ew", padx=4, pady=3)
        box.columnconfigure(0, weight=1)
        ttk.Label(box, text=label).grid(row=0, column=0, sticky="w")
        ttk.Spinbox(box, textvariable=variable, from_=minimum, to=maximum, increment=increment).grid(row=1, column=0, sticky="ew")

    def _refresh_actor_values(self) -> None:
        values: list[str] = []
        for raw in self.actors_var.get().replace(";", ",").split(","):
            actor = slugify(raw.strip(), fallback="")
            if actor and actor not in values:
                values.append(actor)
        if "usuario" not in values:
            values.append("usuario")
        if not values:
            values = ["usuario"]
        self.actor_combo["values"] = values
        if self.actor_var.get() not in values:
            self.actor_var.set(values[0])
        if self.image_prefix_var.get().strip() in {"", "imagem"}:
            suffix = self.package_var.get().split(".")[-1]
            self.image_prefix_var.set(slugify(suffix, "imagem"))

    def insert_tag(self, text: str, spacing: bool = True) -> None:
        index = self.draft.index(tk.INSERT)
        prefix = ""
        if spacing:
            before = self.draft.get("1.0", index)
            if before and not before.endswith("\n"):
                prefix = "\n\n"
            elif before.endswith("\n") and not before.endswith("\n\n"):
                prefix = "\n"
        self.draft.insert(index, prefix + text)
        self.draft.focus_set()

    def insert_actor_tag(self, kind: str) -> None:
        actor = slugify(self.actor_var.get(), "usuario")
        self.insert_tag(f"[{kind} {actor}] ")

    def compile_current(self) -> bool:
        try:
            self.rows = compile_rows(
                self.draft.get("1.0", "end-1c"),
                package_id=self.package_var.get(),
                script_version=self.version_var.get(),
                frame_prefix=self.frame_prefix_var.get(),
                start_order=self.start_order_var.get(),
                order_step=self.order_step_var.get(),
                start_frame_number=self.start_frame_var.get(),
                image_map=self.image_map,
            )
        except Exception as exc:
            messagebox.showerror("Roteiro inválido", str(exc))
            self.status_var.set("Há erros no roteiro.")
            return False
        self._refresh_tree()
        self.status_var.set(f"Roteiro válido: {len(self.rows)} linhas.")
        return True

    def _refresh_tree(self) -> None:
        selected_line = self.selected_line_id()
        self.tree.delete(*self.tree.get_children())
        for row in self.rows:
            line_id = str(row["line_id"])
            self.tree.insert("", "end", iid=line_id, values=(row["order"], line_id, row["instruction"], row.get("image_id", "")))
        if selected_line and self.tree.exists(selected_line):
            self.tree.selection_set(selected_line)
            self.tree.see(selected_line)

    def selected_line_id(self) -> str:
        selection = self.tree.selection()
        return str(selection[0]) if selection else ""

    def selected_row(self) -> dict[str, object] | None:
        line_id = self.selected_line_id()
        for row in self.rows:
            if row.get("line_id") == line_id:
                return row
        return None

    def next_image_number(self) -> int:
        prefix = slugify(self.image_prefix_var.get(), "imagem")
        start = int(self.image_start_var.get())
        used: list[int] = []
        pattern = re_compile = __import__("re").compile(rf"^{__import__('re').escape(prefix)}(\d+)\.webp$", __import__("re").IGNORECASE)
        for image_id in self.image_sources:
            match = pattern.match(image_id)
            if match:
                used.append(int(match.group(1)))
        return max([start - 1, *used]) + 1

    def assign_selected_image(self) -> None:
        if not self.rows and not self.compile_current():
            return
        line_id = self.selected_line_id()
        if not line_id:
            messagebox.showinfo("Imagem", "Selecione uma linha primeiro.")
            return
        source = filedialog.askopenfilename(title="Escolher imagem", filetypes=[("Imagens", "*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff"), ("Todos os arquivos", "*.*")])
        if not source:
            return
        image_id = normalize_image_name(self.image_prefix_var.get(), self.next_image_number())
        old = self.image_map.get(line_id)
        if old:
            self.image_sources.pop(old, None)
        self.image_map[line_id] = image_id
        self.image_sources[image_id] = source
        self.compile_current()
        self.tree.selection_set(line_id)
        self.on_tree_select()
        self.status_var.set(f"{line_id} → {image_id}")

    def bulk_assign_descriptions(self) -> None:
        if not self.rows and not self.compile_current():
            return
        description_rows = [row for row in self.rows if str(row.get("line_id", "")).endswith("_descricao")]
        if not description_rows:
            messagebox.showinfo("Imagens", "Não há [DESCRIÇÃO] no roteiro.")
            return
        files = filedialog.askopenfilenames(title="Escolher imagens na ordem das DESCRIÇÕES", filetypes=[("Imagens", "*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff"), ("Todos os arquivos", "*.*")])
        if not files:
            return
        if len(files) > len(description_rows):
            if not messagebox.askyesno("Imagens extras", f"Foram escolhidas {len(files)} imagens para {len(description_rows)} descrições. Usar apenas as primeiras {len(description_rows)}?"):
                return
        number = self.next_image_number()
        assigned = 0
        for row, source in zip(description_rows, files):
            line_id = str(row["line_id"])
            image_id = normalize_image_name(self.image_prefix_var.get(), number)
            number += 1
            old = self.image_map.get(line_id)
            if old:
                self.image_sources.pop(old, None)
            self.image_map[line_id] = image_id
            self.image_sources[image_id] = str(source)
            assigned += 1
        self.compile_current()
        self.status_var.set(f"{assigned} imagens atribuídas às DESCRIÇÕES.")

    def remove_selected_image(self) -> None:
        line_id = self.selected_line_id()
        if not line_id:
            return
        image_id = self.image_map.pop(line_id, "")
        if image_id:
            self.image_sources.pop(image_id, None)
        self.compile_current()
        self.preview_label.configure(image="", text="Imagem removida desta linha.")
        self.preview_image = None

    def on_tree_select(self, _event=None) -> None:
        row = self.selected_row()
        if not row:
            return
        line_id = str(row["line_id"])
        self.selected_line_label.configure(text=f"{line_id}\n{row['instruction']}")
        image_id = str(row.get("image_id", "") or "")
        source = self.image_sources.get(image_id, "")
        self._show_preview(source, image_id)

    def _show_preview(self, source: str, image_id: str) -> None:
        if not source:
            self.preview_image = None
            self.preview_label.configure(image="", text="Esta linha não possui image_id.")
            return
        path = Path(source)
        if not path.exists():
            self.preview_image = None
            self.preview_label.configure(image="", text=f"{image_id}\nArquivo original não encontrado:\n{source}")
            return
        if Image is None or ImageTk is None:
            self.preview_label.configure(text=f"{image_id}\n{source}")
            return
        try:
            with Image.open(path) as image:
                image.thumbnail((540, 560), Image.Resampling.LANCZOS)
                preview = ImageTk.PhotoImage(image.copy())
            self.preview_image = preview
            self.preview_label.configure(image=preview, text=image_id, compound="top")
        except Exception as exc:
            self.preview_label.configure(image="", text=f"Não foi possível abrir a imagem:\n{exc}")

    def project_payload(self) -> dict[str, object]:
        return {
            "format": "roleplay2026-editor-desktop-v1",
            "package_id": self.package_var.get(),
            "script_version": self.version_var.get(),
            "frame_prefix": self.frame_prefix_var.get(),
            "start_order": self.start_order_var.get(),
            "order_step": self.order_step_var.get(),
            "start_frame_number": self.start_frame_var.get(),
            "actors": self.actors_var.get(),
            "image_prefix": self.image_prefix_var.get(),
            "image_start": self.image_start_var.get(),
            "quality": self.quality_var.get(),
            "max_side": self.max_side_var.get(),
            "draft": self.draft.get("1.0", "end-1c"),
            "image_map": self.image_map,
            "image_sources": self.image_sources,
        }

    def save_project_dialog(self) -> None:
        if not self.compile_current():
            return
        initial = self.project_path.name if self.project_path else f"{slugify(self.package_var.get().split('.')[-1], 'roteiro')}_projeto.json"
        path = filedialog.asksaveasfilename(title="Salvar projeto", defaultextension=".json", initialfile=initial, filetypes=[("Projeto JSON", "*.json")])
        if not path:
            return
        try:
            save_project(Path(path), self.project_payload())
        except Exception as exc:
            messagebox.showerror("Salvar projeto", str(exc))
            return
        self.project_path = Path(path)
        self.status_var.set(f"Projeto salvo: {path}")

    def open_project_dialog(self) -> None:
        path = filedialog.askopenfilename(title="Abrir projeto", filetypes=[("Projeto JSON", "*.json"), ("Todos os arquivos", "*.*")])
        if not path:
            return
        try:
            data = load_project(Path(path))
            self._apply_project(data)
        except Exception as exc:
            messagebox.showerror("Abrir projeto", str(exc))
            return
        self.project_path = Path(path)
        self.status_var.set(f"Projeto aberto: {path}")

    def _apply_project(self, data: dict[str, object]) -> None:
        self.package_var.set(str(data.get("package_id", "roleplay2026.historia")))
        self.version_var.set(str(data.get("script_version", "200")))
        self.frame_prefix_var.set(str(data.get("frame_prefix", "encontro")))
        self.start_order_var.set(int(data.get("start_order", 10)))
        self.order_step_var.set(int(data.get("order_step", 10)))
        self.start_frame_var.set(int(data.get("start_frame_number", 1)))
        self.actors_var.set(str(data.get("actors", "usuario")))
        self.image_prefix_var.set(str(data.get("image_prefix", "imagem")))
        self.image_start_var.set(int(data.get("image_start", 1)))
        self.quality_var.set(int(data.get("quality", 88)))
        self.max_side_var.set(int(data.get("max_side", 1800)))
        self.draft.delete("1.0", "end")
        self.draft.insert("1.0", str(data.get("draft", "")))
        raw_map = data.get("image_map", {})
        raw_sources = data.get("image_sources", {})
        self.image_map = {str(k): str(v) for k, v in raw_map.items()} if isinstance(raw_map, dict) else {}
        self.image_sources = {str(k): str(v) for k, v in raw_sources.items()} if isinstance(raw_sources, dict) else {}
        self._refresh_actor_values()
        self.compile_current()

    def export_dialog(self) -> None:
        if not self.compile_current():
            return
        missing = [image_id for image_id, source in self.image_sources.items() if not Path(source).exists()]
        if missing:
            messagebox.showerror("Exportação", "Existem imagens originais não encontradas:\n" + "\n".join(missing[:8]))
            return
        destination = filedialog.askdirectory(title="Escolha a pasta onde será criada a exportação")
        if not destination:
            return
        folder_name = f"{slugify(self.package_var.get().split('.')[-1], 'roteiro')}_pronto"
        target = Path(destination) / folder_name
        if target.exists() and any(target.iterdir()):
            if not messagebox.askyesno("Pasta existente", f"A pasta {target} já existe. Atualizar os arquivos nela?"):
                return
        try:
            export_package(
                target,
                rows=self.rows,
                image_sources=self.image_sources,
                quality=self.quality_var.get(),
                max_side=self.max_side_var.get(),
                project_payload=self.project_payload(),
            )
        except Exception as exc:
            messagebox.showerror("Exportação", str(exc))
            return
        self.status_var.set(f"Exportação concluída: {target}")
        messagebox.showinfo("Concluído", f"Roteiro e imagens preparados em:\n\n{target}")
        try:
            os.startfile(target)  # type: ignore[attr-defined]
        except Exception:
            pass

    def new_project(self) -> None:
        if self.draft.get("1.0", "end-1c").strip():
            if not messagebox.askyesno("Novo projeto", "Limpar o roteiro atual e começar outro?"):
                return
        self.rows = []
        self.image_map = {}
        self.image_sources = {}
        self.project_path = None
        self.draft.delete("1.0", "end")
        self.tree.delete(*self.tree.get_children())
        self.preview_label.configure(image="", text="Selecione uma linha e atribua uma imagem.")
        self.preview_image = None
        self.status_var.set("Novo projeto iniciado.")


if __name__ == "__main__":
    app = ScriptEditor()
    app.mainloop()
