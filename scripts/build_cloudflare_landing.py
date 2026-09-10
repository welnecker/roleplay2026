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


def build() -> Path:
    site_url = _https_url("ENTRECENAS_SITE_URL", "https://entrecenas-roleplay.com.br")
    app_url = _https_url(
        "ENTRECENAS_APP_URL", "https://app.entrecenas-roleplay.com.br/app"
    )
    media_url = _https_url("ENTRECENAS_MEDIA_URL", "https://midia.entrecenas-roleplay.com.br")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    html = (
        _landing_template()
        .replace("__APP_URL__", app_url + "/")
        .replace("__MEDIA_BASE_URL__", media_url)
        .replace("__SITE_URL__", site_url)
    )
    (OUTPUT_DIR / "index.html").write_text(html, encoding="utf-8")
    source_dir = PROJECT_ROOT / "cloudflare" / "landing"
    for filename in ("_headers", "_redirects"):
        shutil.copy2(source_dir / filename, OUTPUT_DIR / filename)
    return OUTPUT_DIR


if __name__ == "__main__":
    print(build())
