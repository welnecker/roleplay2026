from __future__ import annotations

from pathlib import Path

from packages.loader import load_manifest
from services.editorial_beat_context import build_beat_context, render_beat_context
from services.editorial_package_loader import compile_editorial_package
from services.editorial_runtime import EditorialState, decide_editorial_turn


CARD_ROOT = Path("installed_stories/casada_frustrada")
FIXTURE_ROOT = Path("tests/fixtures/editorial_cards/encontro_no_cafe")


def _card_script():
    return compile_editorial_package(load_manifest(CARD_ROOT / "manifest.yaml"))


def test_todo_turno_recebe_contrato_de_beat() -> None:
    script = compile_editorial_package(load_manifest(FIXTURE_ROOT / "manifest.yaml"))
    previous = EditorialState()
    turn = decide_editorial_turn(script, previous, "Olá, prazer em conhecer você.")

    context = build_beat_context(script, previous, turn)
    rendered = render_beat_context(context)

    assert context.target_beat_id == turn.target_id
    assert "CONTRATO DO BEAT ATUAL" in rendered
    assert "Movimento obrigatório" in rendered
    assert "FATOS CONFIRMADOS" in rendered
    assert "FATOS DESCONHECIDOS" in rendered
    assert any(
        "reagir brevemente ao sentido do conteúdo mais recente do usuário" in item
        for item in context.required_outcomes
    )


def test_compilador_preserva_contrato_factual_estruturado() -> None:
    script = _card_script()
    beat = script.beats["reencontro_fila_007"]

    assert "allowed_topics" in beat
    assert "confirmed_facts" in beat
    assert "unknown_facts" in beat
    assert "o pedido para esperar" in beat["allowed_topics"]
    assert "Mary está no caixa do supermercado" in beat["confirmed_facts"]
    assert "o lugar exato onde o usuário deve esperar" in beat["unknown_facts"]
    assert "o conteúdo, a quantidade e o peso das compras" in beat["unknown_facts"]


def test_todos_os_beats_recebem_contrato_factual_derivado() -> None:
    script = _card_script()

    assert script.beats
    for beat_id, beat in script.beats.items():
        assert beat["factual_contract_mode"] == "explicit+derived", beat_id
        assert beat["allowed_topics"], beat_id
        assert beat["confirmed_facts"], beat_id
        assert beat["unknown_facts"], beat_id
        assert any(
            item.startswith("conteúdo semântico autorizado pela linha canônica:")
            for item in beat["confirmed_facts"]
        ), beat_id
        assert (
            "ações, decisões, falas, pensamentos e intenções do usuário que não tenham sido declarados"
            in beat["unknown_facts"]
        ), beat_id
        assert (
            "acontecimentos, decisões ou resultados pertencentes a beats futuros"
            in beat["unknown_facts"]
        ), beat_id


def test_contrato_explicito_especializa_sem_perder_regras_universais() -> None:
    script = _card_script()
    beat = script.beats["reencontro_fila_007"]

    assert "Mary está no caixa do supermercado" in beat["confirmed_facts"]
    assert "o lugar exato onde o usuário deve esperar" in beat["unknown_facts"]
    assert (
        "localização exata, distância ou deslocamento que não tenham sido declarados"
        in beat["unknown_facts"]
    )
    assert any(
        item.startswith("movimento autorizado neste beat:")
        for item in beat["confirmed_facts"]
    )


def test_beat_sem_patch_explicito_renderiza_base_factual_completa() -> None:
    script = _card_script()
    previous = EditorialState(node_id="encontro_acidental_001")
    turn = decide_editorial_turn(script, previous, "Tudo bem, não me machuquei.")

    context = build_beat_context(script, previous, turn)
    rendered = render_beat_context(context)

    assert context.confirmed_facts
    assert context.unknown_facts
    assert context.allowed_topics
    assert "conteúdo semântico autorizado pela linha canônica" in rendered
    assert "ações, decisões, falas, pensamentos e intenções do usuário" in rendered


def test_adiamento_declara_resultados_sem_prompt_artesanal() -> None:
    script = _card_script()
    previous = EditorialState(node_id="reencontro_fila_007")
    turn = decide_editorial_turn(script, previous, "Agora não, talvez daqui a pouco.")

    assert turn.target_id == "reencontro_fila_007"
    assert "CONTRATO DO BEAT ATUAL" in turn.system_prompt
    assert "reconhecer o adiamento sem tratá-lo como recusa" in turn.system_prompt
    assert "encerrar o encontro" in turn.system_prompt
    assert "Sem pressa... você consegue" not in turn.system_prompt


def test_pergunta_recebe_fatos_confirmados_e_desconhecidos_separados() -> None:
    script = _card_script()
    previous = EditorialState(node_id="reencontro_fila_007")
    turn = decide_editorial_turn(script, previous, "Por que você precisa de ajuda?")

    assert turn.target_id == "reencontro_fila_007"
    assert "responder brevemente à pergunta usando apenas fatos confirmados" in turn.system_prompt
    assert "concretizar qualquer fato declarado como desconhecido" in turn.system_prompt
    assert "FATOS CONFIRMADOS" in turn.system_prompt
    assert "Mary está com compras e um carrinho de compras" in turn.system_prompt
    assert "FATOS DESCONHECIDOS" in turn.system_prompt
    assert "o lugar exato onde o usuário deve esperar" in turn.system_prompt
    assert "roupas e calçados" in turn.system_prompt
    assert "ASSUNTOS PERMITIDOS" in turn.system_prompt
    assert "solicitar uma decisão explícita" in turn.system_prompt


def test_transicoes_nao_declaram_fallback_narrativo() -> None:
    script = _card_script()
    beat = script.beats["reencontro_fila_007"]

    for rule in beat["transition_rules"]:
        assert rule.fallback == ""
        assert rule.prompt == ""
