from __future__ import annotations

import logging

from services.editorial_diagnostics import log_editorial_exception
from services.editorial_response_evaluator import build_regeneration_prompt


def test_regeneracao_traduz_invented_detail_em_instrucao_factual() -> None:
    prompt = build_regeneration_prompt(
        base_prompt="Fatos confirmados: compras e carro.",
        violations=("invented_unconfirmed_detail",),
    )

    assert "Reconstrua a fala do zero" in prompt
    assert "Use somente os fatos confirmados" in prompt
    assert "peso, quantidade, roupa, risco, esforço, urgência" in prompt
    assert "Quando faltar um fato, formule de modo neutro" in prompt


def test_rejeicao_sintetica_nao_emite_none_type(caplog) -> None:
    with caplog.at_level(logging.ERROR, logger="roleplay2026.pilot"):
        log_editorial_exception(
            "editorial_response_rejected",
            RuntimeError("Resposta rejeitada"),
            attempts=2,
            violations=("invented_unconfirmed_detail",),
        )

    text = caplog.text
    assert "editorial_response_rejected" in text
    assert "Resposta rejeitada" in text
    assert "NoneType: None" not in text
