from __future__ import annotations

from services.editorial_compiler import compile_editorial_document
from services.editorial_runtime import (
    EditorialScript,
    editorial_opening_text,
    editorial_scene_opening_text,
)
from services.spreadsheet_story_compiler import compile_spreadsheet_story
from services.story_profile import (
    opening_with_required_name,
    personalize_editorial_script,
    profile_tags,
    resolve_profile_text,
)


def _row(line_id: str, order: int, instruction: str) -> dict[str, object]:
    return {
        "line_id": line_id,
        "order": order,
        "instruction": instruction,
        "status": "active",
    }


def _script() -> EditorialScript:
    document = compile_spreadsheet_story(
        {
            "package_id": "roleplay2026.profile_test",
            "script_version": "1.0.0",
            "character": {"name": "Camilly", "age": 24},
            "blocks": [],
        },
        [
            _row("cena", 10, "[CENA quarto] Estou no quarto."),
            _row("beat", 20, "[BEAT] Eu recebo {{nome}}."),
            _row("pens_h", 30, "[PENSAMENTO HOMEM] Humm... gostei dele."),
            _row("pens_m", 40, "[PENSAMENTO MULHER] Humm... gostei dela."),
            _row(
                "pens_body_f",
                45,
                "[PENSAMENTO CORPO_FEMININO] Humm... conheço melhor esse corpo.",
            ),
            _row("fala_h", 50, "[FALA HOMEM] Oi, {{nome}}... meu lindo."),
            _row("fala_m", 60, "[FALA MULHER] Oi, {{nome}}... minha linda."),
            _row("fala_n", 70, "[FALA NEUTRA] Oi, {{nome}}... que prazer."),
            _row("fim", 80, "[FIM story_complete] Encerrar."),
        ],
        script_version="1.0.0",
    )
    return EditorialScript(compile_editorial_document(document))


def test_profile_tags_separa_tratamento_de_anatomia() -> None:
    assert profile_tags(
        {"story_gender": "Como mulher", "body_route": "Corpo masculino"}
    ) == ("MULHER", "CORPO_MASCULINO")


def test_placeholders_de_tratamento_masculino() -> None:
    rendered = resolve_profile_text(
        "{{nome}} viu {{*nome}}; depois, {{**nome}} entrou.",
        {"preferred_name": "Janio", "story_gender": "Como homem"},
    )
    assert rendered == "Janio viu o Janio; depois, ele entrou."


def test_placeholders_de_tratamento_feminino() -> None:
    rendered = resolve_profile_text(
        "{{nome}} viu {{*nome}}; depois, {{**nome}} entrou.",
        {"preferred_name": "Ana", "story_gender": "Como mulher"},
    )
    assert rendered == "Ana viu a Ana; depois, ela entrou."


def test_placeholders_neutros_usam_somente_o_nome() -> None:
    rendered = resolve_profile_text(
        "{{nome}} viu {{*nome}}; depois, {{**nome}} entrou.",
        {"preferred_name": "Alex", "story_gender": "De forma neutra"},
    )
    assert rendered == "Alex viu Alex; depois, Alex entrou."


def test_genero_ausente_tem_fallback_neutro_e_perfis_antigos_sao_aceitos() -> None:
    assert resolve_profile_text(
        "{{*nome}} disse que {{**nome}} volta.",
        {"preferred_name": "Dani"},
    ) == "Dani disse que Dani volta."
    assert resolve_profile_text(
        "{{*nome}} disse que {{**nome}} volta.",
        {"preferred_name": "Bia", "gender": "Mulher"},
    ) == "a Bia disse que ela volta."


def test_variante_corporal_e_mais_especifica_que_tratamento() -> None:
    personalized = personalize_editorial_script(
        _script(),
        {
            "preferred_name": "Alex",
            "story_gender": "Como homem",
            "body_route": "Corpo feminino",
        },
    )
    opening = editorial_opening_text(personalized)
    assert "meu lindo" in opening
    assert "conheço melhor esse corpo" in opening
    assert "gostei dele" not in opening


def test_script_personalizado_entrega_somente_a_variante_escolhida() -> None:
    personalized = personalize_editorial_script(
        _script(),
        {
            "preferred_name": "Janio",
            "story_gender": "Como homem",
            "body_route": "Corpo masculino",
        },
    )
    opening = editorial_opening_text(personalized)

    assert "Oi, Janio... meu lindo." in opening
    assert "Humm... gostei dele." in opening
    assert "minha linda" not in opening
    assert "{{nome}}" not in opening


def test_abertura_inclui_nome_mesmo_quando_roteiro_nao_tem_placeholder() -> None:
    opening = opening_with_required_name(
        "Que bom ter você aqui.",
        {"preferred_name": "Janio"},
    )
    assert opening == "Oi, Janio... que prazer ter você aqui. Que bom ter você aqui."


def test_cena_e_primeiro_beat_personalizam_nome_independentemente() -> None:
    personalized = personalize_editorial_script(
        _script(),
        {
            "preferred_name": "Doni",
            "story_gender": "Como homem",
            "body_route": "Corpo masculino",
        },
    )

    assert editorial_scene_opening_text(personalized) == "Estou no quarto."
    assert "Oi, Doni... meu lindo." in editorial_opening_text(personalized)
    assert "{{nome}}" not in editorial_opening_text(personalized)
