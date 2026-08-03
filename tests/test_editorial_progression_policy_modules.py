from __future__ import annotations

from pathlib import Path

from services.editorial_message_policy import classify_contextual_editorial_message
from services.editorial_response_policy import clean_editorial_progression_response


IMPLEMENTATION = Path("services/editorial_progression_impl.py")


def test_progressao_ativa_importa_politicas_especializadas() -> None:
    source = IMPLEMENTATION.read_text(encoding="utf-8")

    assert "from services.editorial_message_policy import" in source
    assert "from services.editorial_response_policy import" in source
    assert "_support.classify_contextual_user_message" not in source
    assert "_support.clean_supermarket_script_v2_response" not in source


def test_abuso_direto_permanece_hostil() -> None:
    assert classify_contextual_editorial_message("você é uma vadia") == "hostile"


def test_insulto_contextual_em_interacao_sexual_permanece_engajado() -> None:
    assert classify_contextual_editorial_message("vem, sua vadia gostosa") == "engaged"


def test_limpeza_editorial_preserva_fallback_para_resposta_vazia() -> None:
    fallback = "Fala segura do beat."

    assert clean_editorial_progression_response("", fallback) == fallback
