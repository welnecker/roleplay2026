from __future__ import annotations

from flet_client.frame_state import FrameRevealController, parse_visual_frame


CONTENT = """[QUADRO encontro_001]
[DESCRIÇÃO]
Mary entra na sala.
[PENSAMENTO mary|Mary]
Preciso manter a coragem.
[FALA mary|Mary]
Olá... tem alguém aqui?
[FALA professor|Professor]
Pode entrar.
[/QUADRO]"""


def test_parser_flet_reutiliza_quadro_canonico_v2() -> None:
    frame = parse_visual_frame(CONTENT)

    assert frame.frame_id == "encontro_001"
    assert frame.description == "Mary entra na sala."
    assert [entry.kind for entry in frame.entries] == ["pensamento", "fala", "fala"]
    assert [entry.actor for entry in frame.entries] == ["mary", "mary", "professor"]
    assert [entry.visible_name for entry in frame.entries] == ["Mary", "Mary", "Professor"]


def test_controller_revela_entries_antes_de_liberar_proximo_quadro() -> None:
    controller = FrameRevealController(parse_visual_frame(CONTENT))

    assert controller.revealed_entries == 1
    assert len(controller.visible_entries) == 1
    assert controller.advance() is False
    assert controller.advance() is False
    assert controller.all_entries_visible is True
    assert controller.advance() is True


def test_parser_rejeita_conteudo_que_nao_e_quadro() -> None:
    try:
        parse_visual_frame("[DESCRIÇÃO] Cena sem quadro.")
    except ValueError as exc:
        assert "[QUADRO id]" in str(exc)
    else:
        raise AssertionError("Era esperado ValueError")

