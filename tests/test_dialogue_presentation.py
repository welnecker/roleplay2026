from __future__ import annotations

from services.dialogue_presentation import (
    has_balanced_thought_markers,
    render_dialogue_html,
    split_dialogue,
    with_optional_thought_guidance,
)


def test_mensagem_antiga_permanece_como_fala() -> None:
    dialogue = split_dialogue("Oi, vizinho.\n\nComo você se chama?")

    assert dialogue.thought == ""
    assert dialogue.speech.startswith("Oi, vizinho")


def test_pensamento_e_fala_sao_separados() -> None:
    dialogue = split_dialogue(
        "[PENSAMENTO]\nEle é tão charmoso...\n[/PENSAMENTO]\n\nComo você se chama?"
    )

    assert dialogue.thought == "Ele é tão charmoso..."
    assert dialogue.speech == "Como você se chama?"


def test_renderizacao_cria_tarja_e_paragrafos() -> None:
    html = render_dialogue_html(
        "assistant",
        "[PENSAMENTO]Será que ele percebeu?[/PENSAMENTO]\n\nPrimeiro parágrafo.\n\nSegundo parágrafo.",
    )

    assert "mary-thought" in html
    assert "pensamento" in html
    assert html.count("<p>") == 3


def test_renderizacao_escapa_html_do_usuario() -> None:
    html = render_dialogue_html("user", "<script>alert('x')</script>")

    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_orientacao_mantem_pensamento_opcional() -> None:
    prompt = with_optional_thought_guidance("PROMPT BASE")

    assert "Não inclua pensamento em toda resposta" in prompt
    assert "[PENSAMENTO]" in prompt
    assert "primeira pessoa" in prompt


def test_marcadores_precisam_ser_balanceados() -> None:
    assert has_balanced_thought_markers("[PENSAMENTO]Oi[/PENSAMENTO]\nFala") is True
    assert has_balanced_thought_markers("[PENSAMENTO]Oi\nFala") is False
