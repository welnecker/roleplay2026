from __future__ import annotations

import ast
import os
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "cloudflare" / "landing" / "dist"


def _https_url(variable: str, default: str) -> str:
    value = os.getenv(variable, default).strip().rstrip("/")
    if not value.startswith("https://"):
        raise ValueError(f"{variable} deve começar com https://")
    return value


def _landing_template() -> str:
    source_path = PROJECT_ROOT / "flet_api" / "landing_routes.py"
    module = ast.parse(source_path.read_text(encoding="utf-8"))
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name == "landing_page_html":
            for statement in node.body:
                if isinstance(statement, ast.Assign):
                    if any(isinstance(target, ast.Name) and target.id == "html" for target in statement.targets):
                        value = ast.literal_eval(statement.value)
                        if isinstance(value, str):
                            return value
    raise RuntimeError("Template da landing não encontrado")


def _string_constant(name: str) -> str:
    source_path = PROJECT_ROOT / "flet_api" / "landing_routes.py"
    module = ast.parse(source_path.read_text(encoding="utf-8"))
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            value = ast.literal_eval(node.value)
            if isinstance(value, str):
                return value
    raise RuntimeError(f"Constante {name} não encontrada")


def _legal_html(
    *,
    title: str,
    description: str,
    path: str,
    body: str,
    site_url: str,
    media_url: str,
    contact_email: str,
) -> str:
    return (
        _string_constant("LEGAL_PAGE_TEMPLATE")
        .replace("__LEGAL_TITLE__", title)
        .replace("__LEGAL_DESCRIPTION__", description)
        .replace("__LEGAL_PATH__", path)
        .replace("__LEGAL_BODY__", body)
        .replace("__SITE_URL__", site_url)
        .replace("__MEDIA_BASE_URL__", media_url)
        .replace("__CONTACT_EMAIL__", contact_email)
    )


def build() -> Path:
    site_url = _https_url("ENTRECENAS_SITE_URL", "https://entrecenas-roleplay.com.br")
    app_url = _https_url(
        "ENTRECENAS_APP_URL", "https://app.entrecenas-roleplay.com.br/app"
    )
    media_url = _https_url("ENTRECENAS_MEDIA_URL", "https://midia.entrecenas-roleplay.com.br")
    contact_email = os.getenv(
        "ENTRECENAS_CONTACT_EMAIL", "contato@entrecenas-roleplay.com.br"
    ).strip()
    if "@" not in contact_email:
        raise ValueError("ENTRECENAS_CONTACT_EMAIL deve ser um e-mail válido")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    html = (
        _landing_template()
        .replace("__APP_URL__", app_url + "/")
        .replace("__MEDIA_BASE_URL__", media_url)
        .replace("__SITE_URL__", site_url)
    )
    (OUTPUT_DIR / "index.html").write_text(html, encoding="utf-8")
    legal_pages = {
        "politica-de-privacidade": _legal_html(
            title="Política de Privacidade",
            description="Política de Privacidade do EntreCenas e informações sobre o tratamento de dados pessoais.",
            path="/politica-de-privacidade/",
            body=_string_constant("PRIVACY_POLICY_BODY"),
            site_url=site_url,
            media_url=media_url,
            contact_email=contact_email,
        ),
        "termos-de-uso": _legal_html(
            title="Termos de Uso",
            description="Termos de Uso do EntreCenas, incluindo compra unitária por card e regras da plataforma.",
            path="/termos-de-uso/",
            body=_string_constant("TERMS_OF_USE_BODY"),
            site_url=site_url,
            media_url=media_url,
            contact_email=contact_email,
        ),
    }
    for directory, page_html in legal_pages.items():
        destination = OUTPUT_DIR / directory
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "index.html").write_text(page_html, encoding="utf-8")
    source_dir = PROJECT_ROOT / "cloudflare" / "landing"
    for filename in ("_headers", "_redirects"):
        shutil.copy2(source_dir / filename, OUTPUT_DIR / filename)
    return OUTPUT_DIR


if __name__ == "__main__":
    print(build())
