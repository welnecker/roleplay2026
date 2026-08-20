from __future__ import annotations

from pathlib import Path

from packages.loader import discover_packages
from platform_core.catalog import load_catalog
from services.editorial_package_loader import compile_editorial_package
from services.editorial_content import (
    LEGACY_EDITORIAL_PACKAGE_ID,
    load_source_document,
    require_editorial_package,
)
from services.editorial_diagnostics import finalize_editorial_model_response
from services.dialogue_presentation import render_dialogue_html, with_optional_thought_guidance
from services.editorial_runtime import EditorialState, decide_editorial_turn
from services.narrative_context import character_context


ROOT = Path(__file__).resolve().parents[1]
INSTALLED_STORIES = ROOT / "installed_stories"


def test_camilly_aparece_no_catalogo_com_runtime_editorial_pago() -> None:
    cards, errors = load_catalog(INSTALLED_STORIES)

    assert errors == []
    card = next(item for item in cards if item.package_id == "roleplay2026.camilly")
    assert card.title == "Camilly"
    assert card.profile_name == "Camilly"
    assert card.price_label == "R$ 1,00"
    assert card.replay_requires_purchase is True
    assert card.cover_url.startswith("data:image/webp;base64,")


def test_camilly_declara_capa_local_sem_compartilhar_assets_de_outro_pacote() -> None:
    packages, errors = discover_packages(INSTALLED_STORIES)

    assert errors == []
    package = next(
        item for item in packages if item.manifest.package_id == "roleplay2026.camilly"
    )
    assert package.manifest.card.cover == "assets/capas/capa.webp"
    assert package.root / package.manifest.card.cover == (
        INSTALLED_STORIES / "camilly" / "assets" / "capas" / "capa.webp"
    )


def test_camilly_compila_sem_depender_da_planilha() -> None:
    packages, errors = discover_packages(INSTALLED_STORIES)

    assert errors == []
    package = next(
        item for item in packages if item.manifest.package_id == "roleplay2026.camilly"
    )
    script = compile_editorial_package(package)
    assert script.raw["character"]["name"] == "Camilly"
    assert script.first_beat_id == "camilly_fallback_001"


def test_carregamento_expresso_isola_cada_historia_instalada() -> None:
    mary = load_source_document("roleplay2026.casada_frustrada")
    camilly = load_source_document("roleplay2026.camilly")

    assert mary["package_id"] == "roleplay2026.casada_frustrada"
    assert mary["character"]["name"] == "Mary"
    assert camilly["package_id"] == "roleplay2026.camilly"
    assert camilly["character"]["name"] == "Camilly"


def test_fachada_legada_tem_padrao_explicito_e_nao_depende_da_quantidade() -> None:
    assert LEGACY_EDITORIAL_PACKAGE_ID == "roleplay2026.casada_frustrada"
    assert load_source_document()["package_id"] == LEGACY_EDITORIAL_PACKAGE_ID


def test_pacote_desconhecido_falha_com_mensagem_clara() -> None:
    try:
        require_editorial_package("roleplay2026.inexistente")
    except ValueError as exc:
        assert "História editorial não encontrada" in str(exc)
        assert "roleplay2026.camilly" in str(exc)
    else:
        raise AssertionError("Era esperado erro para package_id desconhecido")


def test_diagnostico_da_camilly_nao_herda_limites_canonicos_da_mary() -> None:
    mary_motel_line = "Deixa eu ver se esse garotão subiu de novo..."
    raw = "Esta é uma resposta própria da Camilly."

    camilly_result = finalize_editorial_model_response(
        raw_response=raw,
        cleaned_response=raw,
        fallback=mary_motel_line,
        recent_assistant_messages=[],
        package_id="roleplay2026.camilly",
    )
    mary_result = finalize_editorial_model_response(
        raw_response=raw,
        cleaned_response=raw,
        fallback=mary_motel_line,
        recent_assistant_messages=[],
        package_id="roleplay2026.casada_frustrada",
    )

    assert camilly_result.guard_reason == "model_response_accepted"
    assert camilly_result.response == raw
    assert mary_result.guard_reason == "motel_canonical_boundary"
    assert mary_motel_line in mary_result.response


def test_prompt_e_apresentacao_da_camilly_nao_usam_identidade_da_mary() -> None:
    packages, errors = discover_packages(INSTALLED_STORIES)
    assert errors == []
    package = next(
        item for item in packages if item.manifest.package_id == "roleplay2026.camilly"
    )
    script = compile_editorial_package(package)
    turn = decide_editorial_turn(script, EditorialState(), "Oi, Camilly.")
    prompt = with_optional_thought_guidance(
        turn.system_prompt, character_name="Camilly"
    )
    html = render_dialogue_html("assistant", "Oi.", character_name="Camilly")

    assert "Você é Camilly" in prompt
    assert "Mary" not in prompt
    assert '<div class="dialogue-speaker">Camilly</div>' in html


def test_nucleo_da_camilly_inclui_ficha_e_regras_autorais_completas() -> None:
    document = load_source_document("roleplay2026.camilly")
    context = character_context(document)

    assert "NÚCLEO VIVO E AUTORITATIVO DE CAMILLY" in context
    assert "APARÊNCIA FÍSICA" in context
    assert "cabelos loiros" in context
    assert "corpo firme e bem cuidado" in context
    assert "PSICOLOGIA ESTÁVEL" in context
    assert "sente desejo sexual pelo usuário desde o início" in context
    assert "ESTILO DE FALA" in context
    assert "fala sexual, direta e espontânea" in context
    assert "INVARIANTES DA PERSONAGEM" in context
    assert "Pensamento e fala aparecem juntos na mesma resposta" in context
    assert "REGRAS DE INTERPRETAÇÃO" in context
    assert "Não antecipar o próximo beat" in context
    assert "REGRAS DO ROTEIRO" in context
    assert "O roteiro controla a ordem dos acontecimentos" in context
    assert "Mary" not in context
