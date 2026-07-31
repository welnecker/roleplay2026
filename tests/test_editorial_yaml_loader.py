from __future__ import annotations

from services.editorial_content import load_editorial_yaml_text


def test_protege_fala_canonica_com_dois_pontos() -> None:
    raw = load_editorial_yaml_text(
        """beats:\n- beat_id: teste\n  canonical_line: Vou mandar mensagem pra ele: Oi... tô saindo agora...\n"""
    )

    assert raw["beats"][0]["canonical_line"] == (
        "Vou mandar mensagem pra ele: Oi... tô saindo agora..."
    )


def test_mantem_scalar_ja_cotado() -> None:
    raw = load_editorial_yaml_text(
        'beats:\n- beat_id: teste\n  canonical_line: "Oi: tudo bem?"\n'
    )

    assert raw["beats"][0]["canonical_line"] == "Oi: tudo bem?"
