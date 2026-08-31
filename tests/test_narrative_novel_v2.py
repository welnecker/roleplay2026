from narrative_v2.models import CharacterProfile
from narrative_v2.novel import (
    ADVANCE_LABEL,
    MovementDefinition,
    NovelPackage,
    NovelRunState,
    advance_run,
    build_scene_messages,
    next_movement,
)


def _character() -> CharacterProfile:
    return CharacterProfile(
        character_id="camilly",
        name="Camilly",
        age=25,
        physical_profile=("mulher adulta brasileira",),
        psychological_profile=("espontânea", "expressiva"),
        speech_style=("português brasileiro natural",),
    )


def _package() -> NovelPackage:
    return NovelPackage(
        package_id="roleplay2026.camilly",
        script_version="novel-1",
        title="Camilly",
        introduction="Uma história contínua.",
        character=_character(),
        movements=(
            MovementDefinition(
                movement_id="encontro_001",
                scene_id="encontro",
                order=10,
                instruction=(
                    "Eu reconheço {{nome}} no carro, fico contente com a coincidência "
                    "e me aproximo chamando por ele."
                ),
                dramatic_direction="Espontaneidade e alegria genuína.",
            ),
            MovementDefinition(
                movement_id="encontro_002",
                scene_id="encontro",
                order=20,
                instruction=(
                    "Eu conto que estou indo à praia. {{nome}} hesita por alguns "
                    "segundos antes de aceitar me levar; transformo a hesitação em "
                    "brincadeira e a situação se resolve."
                ),
            ),
            MovementDefinition(
                movement_id="carro_001",
                scene_id="carro",
                order=30,
                instruction="Já no carro, eu agradeço e puxo uma conversa leve.",
                transition="Alguns minutos depois, no trânsito em direção à praia.",
            ),
        ),
    )


def test_novel_run_comeca_no_primeiro_movimento_por_order() -> None:
    package = _package()

    run = NovelRunState.start(
        run_id="run-1",
        package=package,
        user_name="João",
    )

    assert run.current_movement_id == "encontro_001"
    assert run.sequence == 1
    assert run.status == "active"


def test_avancar_e_deterministico_e_nao_consulta_intencao_do_usuario() -> None:
    package = _package()
    run = NovelRunState.start(run_id="run-1", package=package, user_name="João")

    result = advance_run(run, package)

    assert ADVANCE_LABEL == "Avançar"
    assert result.rendered_movement_id == "encontro_001"
    assert result.next_movement_id == "encontro_002"
    assert result.completed is False
    assert run.current_movement_id == "encontro_002"
    assert run.sequence == 2
    assert run.status == "active"


def test_hesitacao_e_dramatica_e_nunca_encerra_a_historia() -> None:
    package = _package()
    run = NovelRunState.start(run_id="run-1", package=package, user_name="João")
    advance_run(run, package)

    assert "hesita" in package.get_movement(run.current_movement_id).instruction

    result = advance_run(run, package)

    assert result.completed is False
    assert run.current_movement_id == "carro_001"
    assert run.status == "active"


def test_ultimo_movimento_conclui_normalmente() -> None:
    package = _package()
    run = NovelRunState.start(run_id="run-1", package=package, user_name="João")
    advance_run(run, package)
    advance_run(run, package)

    result = advance_run(run, package)

    assert result.completed is True
    assert result.next_movement_id == ""
    assert run.status == "completed"


def test_next_movement_pode_declarar_salto_explicito() -> None:
    character = _character()
    package = NovelPackage(
        package_id="pkg",
        script_version="1",
        title="Teste",
        introduction="",
        character=character,
        movements=(
            MovementDefinition(
                movement_id="a",
                scene_id="s1",
                order=10,
                instruction="Eu começo a cena.",
                next_movement_id="c",
            ),
            MovementDefinition(
                movement_id="b",
                scene_id="s1",
                order=20,
                instruction="Eu sou um movimento intermediário opcional.",
            ),
            MovementDefinition(
                movement_id="c",
                scene_id="s2",
                order=30,
                instruction="Eu continuo a história.",
            ),
        ),
    )

    assert next_movement(package, "a").movement_id == "c"


def test_prompt_recebe_so_movimento_atual_e_nome_do_protagonista() -> None:
    package = _package()
    run = NovelRunState.start(run_id="run-1", package=package, user_name="João")

    messages = build_scene_messages(
        package=package,
        run=run,
        continuity=("Camilly ainda está a caminho do ponto de ônibus.",),
    )

    system = messages[0]["content"]
    prompt = messages[1]["content"]

    assert "O ROTEIRO decide o que acontece" in system
    assert "Hesitações" in system
    assert "PROTAGONISTA: João" in prompt
    assert "encontro_001" not in prompt
    assert "reconheço {{nome}}" in prompt
    assert "indo à praia" not in prompt
    assert "Já no carro" not in prompt


def test_ids_e_ordens_de_movimento_sao_unicos() -> None:
    character = _character()

    try:
        NovelPackage(
            package_id="pkg",
            script_version="1",
            title="Teste",
            introduction="",
            character=character,
            movements=(
                MovementDefinition("a", "s", 10, "Eu começo."),
                MovementDefinition("a", "s", 20, "Eu continuo."),
            ),
        )
    except ValueError as exc:
        assert "movement_id duplicado" in str(exc)
    else:
        raise AssertionError("Era esperado rejeitar movement_id duplicado.")
