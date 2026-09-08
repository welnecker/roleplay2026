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

from core import compile_rows, export_package, load_project, normalize_image_name, save_project, slugify  # noqa: E402
from image_sequence import next_image_number as calculate_next_image_number  # noqa: E402

try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None

APP_TITLE = "Editor de Roteiros ROLEPLAY2026 — Imagem primeiro"
IMAGE_TYPES = [("Imagens", "*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff"), ("Todos os arquivos", "*.*")]


class ScriptEditor(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1540x920")
        self.minsize(1220, 760)

        self.rows: list[dict[str, object]] = []
        self.image_map: dict[str, str] = {}
        self.image_sources: dict[str, str] = {}
        self.description_bindings: dict[int, dict[str, str]] = {}
        self.reference_files: list[str] = []
        self.reference_index = -1
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
        self.reference_name_var = tk.StringVar(value="Nenhuma imagem aberta")
        self.reference_count_var = tk.StringVar(value="Abra uma imagem para começar a escrever.")
        self.status_var = tk.StringVar(value="Abra uma imagem de referência.")

        self._build_style()
        self._build_ui()
        self._refresh_actor_values()

    def _build_style(self) -> None:
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Treeview", rowheight=25)
        style.configure("Header.TLabel", font=("Segoe UI", 11, "bold"))
        style.configure("Big.TButton", font=("Segoe UI", 10, "bold"), padding=(10, 7))

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(1, weight=1)

        top = ttk.Frame(self, padding=10)
        top.grid(row=0, column=0, columnspan=2, sticky="ew")
        for i in range(8):
            top.columnconfigure(i, weight=1)

        self._entry(top, "package_id", self.package_var, 0, 0, 2)
        self._entry(top, "script_version", self.version_var, 0, 2)
        self._entry(top, "Prefixo dos quadros", self.frame_prefix_var, 0, 3)
        self._spin(top, "Primeira order", self.start_order_var, 0, 4, 0, 999999, 10)
        self._spin(top, "Intervalo", self.order_step_var, 0, 5, 1, 1000, 1)
        self._spin(top, "Primeiro quadro", self.start_frame_var, 0, 6, 1, 99999, 1)
        ttk.Button(top, text="Novo projeto", command=self.new_project).grid(row=0, column=7, padx=4, pady=(19, 0), sticky="ew")

        self._entry(top, "Personagens (vírgulas)", self.actors_var, 1, 0, 2)
        ttk.Button(top, text="Atualizar atores", command=self._refresh_actor_values).grid(row=1, column=2, padx=4, pady=(19, 0), sticky="ew")
        self._entry(top, "Prefixo das imagens", self.image_prefix_var, 1, 3)
        self._spin(top, "Primeira imagem", self.image_start_var, 1, 4, 1, 99999, 1)
        self._spin(top, "Qualidade WebP", self.quality_var, 1, 5, 1, 100, 1)
        self._spin(top, "Máx. lado (px)", self.max_side_var, 1, 6, 256, 8000, 64)
        ttk.Button(top, text="Salvar projeto", command=self.save_project_dialog).grid(row=1, column=7, padx=4, pady=(19, 0), sticky="ew")

        left = ttk.Frame(self, padding=(10, 0, 5, 10))
        left.grid(row=1, column=0, sticky="nsew")
        left.columnconfigure(0, weight=1)
        left.rowconfigure(2, weight=3)
        left.rowconfigure(5, weight=2)

        ttk.Label(left, text="Roteiro V2 — escreva olhando para a imagem", style="Header.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 5))
        toolbar = ttk.Frame(left)
        toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        ttk.Button(toolbar, text="+ DESCRIÇÃO DESTA IMAGEM", command=self.insert_description_from_reference, style="Big.TButton").pack(side="left", padx=(0, 8))
        ttk.Label(toolbar, text="Ator:").pack(side="left", padx=(4, 3))
        self.actor_combo = ttk.Combobox(toolbar, textvariable=self.actor_var, state="readonly", width=16)
        self.actor_combo.pack(side="left", padx=(0, 4))
        ttk.Button(toolbar, text="+ FALA", command=lambda: self.insert_actor_tag("FALA")).pack(side="left", padx=3)
        ttk.Button(toolbar, text="+ PENSAMENTO", command=lambda: self.insert_actor_tag("PENSAMENTO")).pack(side="left", padx=3)
        for token in ("{{nome}}", "{{*nome}}", "{{**nome}}"):
            ttk.Button(
                toolbar,
                text=f"+ {token}",
                command=lambda value=token: self.insert_tag(value, spacing=False),
            ).pack(side="left", padx=3)
        ttk.Button(toolbar, text="Validar / atualizar", command=self.compile_current).pack(side="right")

        text_frame = ttk.Frame(left)
        text_frame.grid(row=2, column=0, sticky="nsew")
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        self.draft = tk.Text(text_frame, wrap="word", undo=True, font=("Segoe UI", 11), padx=10, pady=10)
        self.draft.grid(row=0, column=0, sticky="nsew")
        sc = ttk.Scrollbar(text_frame, orient="vertical", command=self.draft.yview)
        sc.grid(row=0, column=1, sticky="ns")
        self.draft.configure(yscrollcommand=sc.set)

        table_toolbar = ttk.Frame(left)
        table_toolbar.grid(row=3, column=0, sticky="ew", pady=(8, 5))
        ttk.Label(table_toolbar, text="Linhas geradas", style="Header.TLabel").pack(side="left")
        ttk.Button(table_toolbar, text="Usar imagem atual na DESCRIÇÃO selecionada", command=self.bind_reference_to_selected_description).pack(side="right")

        table_frame = ttk.Frame(left)
        table_frame.grid(row=5, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        columns = ("order", "line_id", "instruction", "image_id")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        for col, text in [("order", "order"), ("line_id", "line_id"), ("instruction", "instruction"), ("image_id", "image_id")]:
            self.tree.heading(col, text=text)
        self.tree.column("order", width=65, anchor="center", stretch=False)
        self.tree.column("line_id", width=280, stretch=False)
        self.tree.column("instruction", width=620)
        self.tree.column("image_id", width=160, stretch=False)
        self.tree.grid(row=0, column=0, sticky="nsew")
        sy = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        sy.grid(row=0, column=1, sticky="ns")
        sx = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        sx.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)

        right = ttk.Frame(self, padding=(5, 0, 10, 10))
        right.grid(row=1, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(3, weight=1)

        ttk.Label(right, text="Imagem de referência", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(right, textvariable=self.reference_name_var, wraplength=520).grid(row=1, column=0, sticky="ew", pady=(3, 1))
        ttk.Label(right, textvariable=self.reference_count_var).grid(row=2, column=0, sticky="ew", pady=(0, 5))

        box = ttk.Frame(right, relief="sunken", borderwidth=1)
        box.grid(row=3, column=0, sticky="nsew")
        box.columnconfigure(0, weight=1)
        box.rowconfigure(0, weight=1)
        self.preview_label = ttk.Label(box, text="ABRA UMA IMAGEM PRIMEIRO\n\nEla ficará aqui enquanto você escreve o roteiro.", anchor="center", justify="center")
        self.preview_label.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

        nav = ttk.Frame(right)
        nav.grid(row=4, column=0, sticky="ew", pady=(8, 4))
        for i in range(4): nav.columnconfigure(i, weight=1)
        ttk.Button(nav, text="ABRIR IMAGEM", command=self.open_reference_image, style="Big.TButton").grid(row=0, column=0, columnspan=2, padx=(0, 3), sticky="ew")
        ttk.Button(nav, text="ABRIR LOTE", command=self.open_reference_batch).grid(row=0, column=2, columnspan=2, padx=(3, 0), sticky="ew")
        ttk.Button(nav, text="← Anterior", command=lambda: self.move_reference(-1)).grid(row=1, column=0, columnspan=2, padx=(0, 3), pady=5, sticky="ew")
        ttk.Button(nav, text="Próxima →", command=lambda: self.move_reference(1)).grid(row=1, column=2, columnspan=2, padx=(3, 0), pady=5, sticky="ew")

        ttk.Label(right, text="A imagem acima é apenas sua referência de autoria. Ela só recebe image_id quando você cria ou associa uma [DESCRIÇÃO].", wraplength=520, justify="left").grid(row=5, column=0, sticky="ew", pady=(3, 8))

        actions = ttk.Frame(right)
        actions.grid(row=6, column=0, sticky="ew")
        actions.columnconfigure(0, weight=1); actions.columnconfigure(1, weight=1)
        ttk.Button(actions, text="Abrir projeto", command=self.open_project_dialog).grid(row=0, column=0, padx=(0, 4), pady=3, sticky="ew")
        ttk.Button(actions, text="Salvar projeto", command=self.save_project_dialog).grid(row=0, column=1, padx=(4, 0), pady=3, sticky="ew")
        ttk.Button(actions, text="EXPORTAR ROTEIRO + IMAGENS", command=self.export_dialog, style="Big.TButton").grid(row=1, column=0, columnspan=2, pady=6, sticky="ew")

        status = ttk.Label(self, textvariable=self.status_var, relief="sunken", anchor="w", padding=(8, 3))
        status.grid(row=2, column=0, columnspan=2, sticky="ew")

    def _entry(self, parent, label, variable, row, column, span=1):
        f = ttk.Frame(parent); f.grid(row=row, column=column, columnspan=span, sticky="ew", padx=4, pady=3); f.columnconfigure(0, weight=1)
        ttk.Label(f, text=label).grid(row=0, column=0, sticky="w"); ttk.Entry(f, textvariable=variable).grid(row=1, column=0, sticky="ew")

    def _spin(self, parent, label, variable, row, column, minimum, maximum, increment):
        f = ttk.Frame(parent); f.grid(row=row, column=column, sticky="ew", padx=4, pady=3); f.columnconfigure(0, weight=1)
        ttk.Label(f, text=label).grid(row=0, column=0, sticky="w"); ttk.Spinbox(f, textvariable=variable, from_=minimum, to=maximum, increment=increment).grid(row=1, column=0, sticky="ew")

    def _refresh_actor_values(self):
        values=[]
        for raw in self.actors_var.get().replace(";", ",").split(","):
            actor=slugify(raw.strip(), fallback="")
            if actor and actor not in values: values.append(actor)
        if "usuario" not in values: values.append("usuario")
        self.actor_combo["values"] = values or ["usuario"]
        if self.actor_var.get() not in values: self.actor_var.set((values or ["usuario"])[0])

    def current_reference(self) -> str:
        if 0 <= self.reference_index < len(self.reference_files): return self.reference_files[self.reference_index]
        return ""

    def open_reference_image(self):
        source=filedialog.askopenfilename(title="Abrir imagem de referência", filetypes=IMAGE_TYPES)
        if source:
            self.reference_files=[source]; self.reference_index=0; self.show_reference()

    def open_reference_batch(self):
        files=filedialog.askopenfilenames(title="Abrir imagens de referência", filetypes=IMAGE_TYPES)
        if files:
            self.reference_files=[str(x) for x in files]; self.reference_index=0; self.show_reference()

    def move_reference(self, delta: int):
        if not self.reference_files: return
        self.reference_index=max(0, min(len(self.reference_files)-1, self.reference_index+delta)); self.show_reference()

    def show_reference(self):
        source=self.current_reference()
        if not source: return
        p=Path(source); self.reference_name_var.set(p.name)
        self.reference_count_var.set(f"Imagem {self.reference_index+1} de {len(self.reference_files)}")
        if Image is None or ImageTk is None:
            self.preview_label.configure(text=source); return
        try:
            with Image.open(p) as image:
                image.thumbnail((570, 590), Image.Resampling.LANCZOS)
                preview=ImageTk.PhotoImage(image.copy())
            self.preview_image=preview; self.preview_label.configure(image=preview, text="")
            self.status_var.set("Imagem aberta. Agora descreva o que você vê.")
        except Exception as exc:
            self.preview_label.configure(image="", text=f"Não foi possível abrir:\n{exc}")

    def count_descriptions_before_cursor(self) -> int:
        before=self.draft.get("1.0", tk.INSERT)
        return before.upper().count("[DESCRIÇÃO]")

    def allocate_binding(self, ordinal: int, source: str):
        if ordinal in self.description_bindings:
            old=self.description_bindings[ordinal].get("image_id", "")
            if old: self.image_sources.pop(old, None)
        number=self.next_image_number()
        image_id=normalize_image_name(self.image_prefix_var.get(), number)
        self.description_bindings[ordinal]={"source":source, "image_id":image_id}
        self.image_sources[image_id]=source

    def insert_description_from_reference(self):
        source=self.current_reference()
        if not source:
            messagebox.showinfo("Imagem primeiro", "Abra uma imagem de referência antes de criar a DESCRIÇÃO."); return
        ordinal=self.count_descriptions_before_cursor()+1
        self.allocate_binding(ordinal, source)
        self.insert_tag("[DESCRIÇÃO] ")
        self.status_var.set(f"Descrição {ordinal} ligada visualmente a {Path(source).name}. Escreva a cena.")

    def insert_tag(self, text: str, spacing=True):
        index=self.draft.index(tk.INSERT); prefix=""
        if spacing:
            before=self.draft.get("1.0", index)
            if before and not before.endswith("\n"): prefix="\n\n"
            elif before.endswith("\n") and not before.endswith("\n\n"): prefix="\n"
        self.draft.insert(index, prefix+text); self.draft.focus_set()

    def insert_actor_tag(self, kind: str):
        self.insert_tag(f"[{kind} {slugify(self.actor_var.get(), 'usuario')}] ")

    def next_image_number(self) -> int:
        return calculate_next_image_number(
            slugify(self.image_prefix_var.get(), "imagem"),
            int(self.image_start_var.get()),
            image_source_ids=self.image_sources,
            mapped_image_ids=self.image_map.values(),
            binding_image_ids=(
                binding.get("image_id", "")
                for binding in self.description_bindings.values()
            ),
        )

    def build_image_map(self, rows):
        result=dict(self.image_map)
        descriptions=[r for r in rows if str(r.get("line_id", "")).endswith("_descricao")]
        for ordinal, binding in self.description_bindings.items():
            if 1 <= ordinal <= len(descriptions): result[str(descriptions[ordinal-1]["line_id"])]=binding["image_id"]
        return result

    def compile_current(self) -> bool:
        try:
            base=compile_rows(self.draft.get("1.0", "end-1c"), package_id=self.package_var.get(), script_version=self.version_var.get(), frame_prefix=self.frame_prefix_var.get(), start_order=self.start_order_var.get(), order_step=self.order_step_var.get(), start_frame_number=self.start_frame_var.get(), image_map={})
            self.image_map=self.build_image_map(base)
            self.rows=compile_rows(self.draft.get("1.0", "end-1c"), package_id=self.package_var.get(), script_version=self.version_var.get(), frame_prefix=self.frame_prefix_var.get(), start_order=self.start_order_var.get(), order_step=self.order_step_var.get(), start_frame_number=self.start_frame_var.get(), image_map=self.image_map)
        except Exception as exc:
            messagebox.showerror("Roteiro inválido", str(exc)); self.status_var.set("Há erros no roteiro."); return False
        self.refresh_tree(); self.status_var.set(f"Roteiro válido: {len(self.rows)} linhas."); return True

    def refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for r in self.rows:
            lid=str(r["line_id"]); self.tree.insert("", "end", iid=lid, values=(r["order"], lid, r["instruction"], r.get("image_id", "")))

    def bind_reference_to_selected_description(self):
        source=self.current_reference(); sel=self.tree.selection()
        if not source: messagebox.showinfo("Imagem", "Abra uma imagem de referência primeiro."); return
        if not sel: messagebox.showinfo("Descrição", "Selecione uma linha [DESCRIÇÃO]."); return
        lid=str(sel[0])
        descriptions=[r for r in self.rows if str(r.get("line_id", "")).endswith("_descricao")]
        ids=[str(r["line_id"]) for r in descriptions]
        if lid not in ids: messagebox.showinfo("Descrição", "A linha selecionada não é uma [DESCRIÇÃO]."); return
        ordinal=ids.index(lid)+1; self.allocate_binding(ordinal, source); self.compile_current(); self.tree.selection_set(lid)

    def project_payload(self):
        return {"format":"roleplay2026-editor-desktop-image-first-v2","package_id":self.package_var.get(),"script_version":self.version_var.get(),"frame_prefix":self.frame_prefix_var.get(),"start_order":self.start_order_var.get(),"order_step":self.order_step_var.get(),"start_frame_number":self.start_frame_var.get(),"actors":self.actors_var.get(),"image_prefix":self.image_prefix_var.get(),"image_start":self.image_start_var.get(),"quality":self.quality_var.get(),"max_side":self.max_side_var.get(),"draft":self.draft.get("1.0","end-1c"),"image_map":self.image_map,"image_sources":self.image_sources,"description_bindings":self.description_bindings,"reference_files":self.reference_files,"reference_index":self.reference_index}

    def save_project_dialog(self):
        if self.draft.get("1.0","end-1c").strip() and not self.compile_current(): return
        initial=self.project_path.name if self.project_path else f"{slugify(self.package_var.get().split('.')[-1], 'roteiro')}_projeto.json"
        path=filedialog.asksaveasfilename(title="Salvar projeto", defaultextension=".json", initialfile=initial, filetypes=[("Projeto JSON","*.json")])
        if path:
            save_project(Path(path), self.project_payload()); self.project_path=Path(path); self.status_var.set(f"Projeto salvo: {path}")

    def open_project_dialog(self):
        path=filedialog.askopenfilename(title="Abrir projeto", filetypes=[("Projeto JSON","*.json"),("Todos","*.*")])
        if not path: return
        try: self.apply_project(load_project(Path(path)))
        except Exception as exc: messagebox.showerror("Abrir projeto", str(exc)); return
        self.project_path=Path(path); self.status_var.set(f"Projeto aberto: {path}")

    def apply_project(self, d):
        self.package_var.set(str(d.get("package_id","roleplay2026.historia"))); self.version_var.set(str(d.get("script_version","200"))); self.frame_prefix_var.set(str(d.get("frame_prefix","encontro")))
        self.start_order_var.set(int(d.get("start_order",10))); self.order_step_var.set(int(d.get("order_step",10))); self.start_frame_var.set(int(d.get("start_frame_number",1)))
        self.actors_var.set(str(d.get("actors","usuario"))); self.image_prefix_var.set(str(d.get("image_prefix","imagem"))); self.image_start_var.set(int(d.get("image_start",1))); self.quality_var.set(int(d.get("quality",88))); self.max_side_var.set(int(d.get("max_side",1800)))
        self.draft.delete("1.0","end"); self.draft.insert("1.0",str(d.get("draft","")))
        self.image_map={str(k):str(v) for k,v in dict(d.get("image_map",{})).items()}; self.image_sources={str(k):str(v) for k,v in dict(d.get("image_sources",{})).items()}
        raw=dict(d.get("description_bindings",{})); self.description_bindings={int(k):{str(a):str(b) for a,b in dict(v).items()} for k,v in raw.items()}
        self.reference_files=[str(x) for x in d.get("reference_files",[])]; self.reference_index=int(d.get("reference_index",-1)); self._refresh_actor_values()
        if self.reference_files: self.reference_index=max(0,min(len(self.reference_files)-1,self.reference_index)); self.show_reference()
        if self.draft.get("1.0","end-1c").strip(): self.compile_current()

    def export_dialog(self):
        if not self.compile_current(): return
        missing=[iid for iid,src in self.image_sources.items() if not Path(src).exists()]
        if missing: messagebox.showerror("Exportação","Imagens originais não encontradas:\n"+"\n".join(missing[:8])); return
        destination=filedialog.askdirectory(title="Escolha a pasta da exportação")
        if not destination: return
        target=Path(destination)/f"{slugify(self.package_var.get().split('.')[-1], 'roteiro')}_pronto"
        if target.exists() and any(target.iterdir()) and not messagebox.askyesno("Pasta existente",f"{target} já existe. Atualizar?"): return
        try: export_package(target, rows=self.rows, image_sources=self.image_sources, quality=self.quality_var.get(), max_side=self.max_side_var.get(), project_payload=self.project_payload())
        except Exception as exc: messagebox.showerror("Exportação",str(exc)); return
        messagebox.showinfo("Concluído",f"Roteiro e imagens preparados em:\n\n{target}")
        try: os.startfile(target)  # type: ignore[attr-defined]
        except Exception: pass

    def new_project(self):
        if self.draft.get("1.0","end-1c").strip() and not messagebox.askyesno("Novo projeto","Limpar o projeto atual?"): return
        self.rows=[]; self.image_map={}; self.image_sources={}; self.description_bindings={}; self.reference_files=[]; self.reference_index=-1; self.project_path=None
        self.draft.delete("1.0","end"); self.tree.delete(*self.tree.get_children()); self.preview_image=None; self.preview_label.configure(image="",text="ABRA UMA IMAGEM PRIMEIRO\n\nEla ficará aqui enquanto você escreve o roteiro.")
        self.reference_name_var.set("Nenhuma imagem aberta"); self.reference_count_var.set("Abra uma imagem para começar a escrever."); self.status_var.set("Novo projeto iniciado.")


if __name__ == "__main__":
    ScriptEditor().mainloop()
