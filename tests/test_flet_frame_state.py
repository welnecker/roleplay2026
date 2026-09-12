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


def test_parser_preserva_diretiva_balao_como_estilo_visual_da_fala() -> None:
    frame = parse_visual_frame("""[QUADRO encontro_003]
[DESCRIÇÃO]
Mary se assusta.
[FALA mary_balao|Mary]
Ai! Que susto!
[/QUADRO]""")

    entry = frame.entries[0]
    assert entry.actor == "mary_balao"
    assert entry.visible_name == "Mary"
    assert entry.impact_balloon is True


def test_parser_anexa_smack_a_fala_seguinte_sem_criar_entry() -> None:
    frame = parse_visual_frame("""[QUADRO mascara_001]
[DESCRIÇÃO]
O professor beija o ombro de Mary.
[ONOMATOPEIA smack x=69 y=48 delay=350 duracao=1200 dx=32 dy=-10]
[FALA mary|Mary]
Ai!!! Que susto, prof... rsrs
[/QUADRO]""")

    assert len(frame.entries) == 1
    effect = frame.entries[0].effects_before[0]
    assert effect.text == "SMACK!"
    assert effect.x == 69
    assert effect.y == 48
    assert effect.delay == 350


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
