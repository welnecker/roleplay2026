from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path

from services.v2_schema_initializer import initialize_v2_sheet_schemas


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cria e valida as abas das três planilhas da arquitetura v2."
    )
    parser.add_argument(
        "--secrets",
        default=".streamlit/secrets.toml",
        help="Caminho do arquivo TOML com os IDs e a conta de serviço.",
    )
    args = parser.parse_args()

    secrets_path = Path(args.secrets)
    if not secrets_path.is_file():
        print(f"Arquivo de secrets não encontrado: {secrets_path}", file=sys.stderr)
        return 2

    with secrets_path.open("rb") as handle:
        secrets = tomllib.load(handle)

    try:
        results = initialize_v2_sheet_schemas(secrets)
    except Exception as exc:
        print(f"Falha ao inicializar as planilhas: {exc}", file=sys.stderr)
        return 1

    for result in results:
        created = ", ".join(result.created_sheets) or "nenhuma"
        existing = ", ".join(result.existing_sheets) or "nenhuma"
        print(result.spreadsheet_name)
        print(f"  criadas: {created}")
        print(f"  já existentes: {existing}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
