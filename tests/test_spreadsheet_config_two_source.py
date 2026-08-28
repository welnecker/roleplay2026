from persistence.spreadsheet_config import read_spreadsheet_ids


def test_editorial_id_usa_runtime_sem_terceira_planilha_obrigatoria() -> None:
    ids = read_spreadsheet_ids(
        {
            "ROLEPLAY_ACCOUNTS_BILLING_SPREADSHEET_ID": "accounts",
            "ROLEPLAY_RUNTIME_SPREADSHEET_ID": "runtime",
        }
    )

    assert ids.accounts_billing == "accounts"
    assert ids.runtime == "runtime"
    assert ids.editorial == "runtime"


def test_editorial_id_explicito_permanece_compativel() -> None:
    ids = read_spreadsheet_ids(
        {
            "ROLEPLAY_ACCOUNTS_BILLING_SPREADSHEET_ID": "accounts",
            "ROLEPLAY_RUNTIME_SPREADSHEET_ID": "runtime",
            "ROLEPLAY_EDITORIAL_SPREADSHEET_ID": "editorial-legado",
        }
    )

    assert ids.editorial == "editorial-legado"
