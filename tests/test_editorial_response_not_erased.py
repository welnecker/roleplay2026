from __future__ import annotations

import json
import subprocess
import sys


def _clean(response: str, fallback: str) -> str:
    script = (
        "import json; "
        "from services.editorial_response_policy import clean_editorial_progression_response; "
        f"print(json.dumps(clean_editorial_progression_response({response!r}, {fallback!r}), ensure_ascii=False))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return str(json.loads(completed.stdout.strip()))


def test_fala_natural_nao_e_apagada_por_regex_de_narracao() -> None:
    response = (
        "[PENSAMENTO]\n"
        "Ele não esquece o beijo, mas eu preciso garantir que a gente se fale de novo.\n"
        "[/PENSAMENTO]\n\n"
        "Eu queria seu número. Você me passa?"
    )

    assert _clean(response, "") == response


def test_ocorrencia_de_ela_nao_apaga_resposta() -> None:
    response = "Não sei se ela apareceria aqui, mas prefiro falar com você depois."

    assert _clean(response, "") == response


def test_vazamento_tecnico_ainda_usa_fallback() -> None:
    assert _clean("<END_RUN>", "fala segura") == "fala segura"


def test_resposta_realmente_vazia_usa_fallback() -> None:
    assert _clean("   ", "fala segura") == "fala segura"
