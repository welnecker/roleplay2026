from __future__ import annotations

from services.dialogue_presentation import (
    has_balanced_thought_markers,
    render_dialogue_html,
    split_dialogue,
    with_optional_thought_guidance,
    with_scripted_thought_guidance,
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


def test_pensamento_entre_aspas_ainda_cria_tarja() -> None:
    html = render_dialogue_html(
        "assistant",
        '"[PENSAMENTO]\nPreciso ser discreta.\n[/PENSAMENTO]\n\nJá levo a cerveja."',
    )

    assert "mary-thought" in html
    assert "Preciso ser discreta" in html
    assert "Já levo a cerveja" in html


def test_pensamento_em_cerca_markdown_ainda_cria_tarja() -> None:
    html = render_dialogue_html(
        "assistant",
        "```text\n[PENSAMENTO]\nPreciso ser discreta.\n[/PENSAMENTO]\n\nJá levo a cerveja.\n```",
    )

    assert "mary-thought" in html
    assert "Preciso ser discreta" in html


def test_bom_antes_do_marcador_nao_quebra_tarja() -> None:
    dialogue = split_dialogue(
        "\ufeff[PENSAMENTO]\nPreciso ser discreta.\n[/PENSAMENTO]\n\nJá levo a cerveja."
    )

    assert dialogue.thought == "Preciso ser discreta."
    assert dialogue.speech == "Já levo a cerveja."


def test_renderizacao_escapa_html_do_usuario() -> None:
    html = render_dialogue_html("user", "<script>alert('x')</script>")

    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_cena_tem_rotulo_narrativo_sem_pensamento_de_personagem() -> None:
    html = render_dialogue_html(
        "scene",
        "[PENSAMENTO]Texto de cena[/PENSAMENTO] Introdução.",
        character_name="Camilly",
    )

    assert "Cena" in html
    assert ">Camilly<" not in html
    assert "mary-thought" not in html


def test_orientacao_mantem_pensamento_opcional() -> None:
    prompt = with_optional_thought_guidance("PROMPT BASE")

    assert "não inclua pensamento" in prompt.casefold()
    assert "[PENSAMENTO]" in prompt
    assert "primeira pessoa" in prompt


def test_subtexto_reforca_desejo_sem_inventar_conflito_romantico() -> None:
    prompt = with_optional_thought_guidance("PROMPT BASE").casefold()

    assert "desejo sexual é motor da personagem" in prompt
    assert "não invente conflito moral" in prompt
    assert "o casamento só entra" in prompt
    assert "nunca atribua ao usuário intenção" in prompt
    assert "prefira uma contradição viva" not in prompt
    assert "carência, expectativa, cautela" not in prompt


def test_marcadores_precisam_ser_balanceados() -> None:
    assert has_balanced_thought_markers("[PENSAMENTO]Oi[/PENSAMENTO]\nFala") is True
    assert has_balanced_thought_markers("[PENSAMENTO]Oi\nFala") is False


def test_contrato_sem_pensamento_proibe_criacao_do_modelo() -> None:
    prompt = with_scripted_thought_guidance(
        "PROMPT BASE", authored_thought="", character_name="Camilly"
    )

    assert "não contém pensamento autoral" in prompt
    assert "somente a fala audível de Camilly" in prompt
    assert "Não crie pensamento" in prompt


def test_contrato_com_pensamento_exige_texto_autoral_sem_ampliacao() -> None:
    prompt = with_scripted_thought_guidance(
        "PROMPT BASE",
        authored_thought="Quero provocá-lo.",
        character_name="Camilly",
    )

    assert "pensamento autoral obrigatório" in prompt
    assert "Reproduza literalmente" in prompt
    assert "Não substitua, amplie nem acrescente" in prompt
