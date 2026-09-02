from __future__ import annotations

from services.editorial_compiler import compile_editorial_document
from services.editorial_content import load_source_document
from services.editorial_progression import decide_editorial_progression_turn, prepare_editorial_script
from services.editorial_runtime_impl import PilotScript, PilotState
from services.narrative_context import build_narrative_context


def _script() -> PilotScript:
    document = load_source_document()
    return prepare_editorial_script(PilotScript(compile_editorial_document(document)))


def test_character_core_reflete_a_premissa_atual_no_prompt() -> None:
    document = load_source_document()

    assert document["character_core"]["summary"]
    context = build_narrative_context(document, [], {})

    assert "NÚCLEO VIVO E AUTORITATIVO DE MARY" in context
    assert "idade: 29 anos" in context
    assert "corpo feminino e sedutor" in context
    assert "Mary é uma mulher brasileira de 29 anos, casada com o Usuário" in context
    assert "o professor da faculdade é um terceiro personagem distinto do Usuário" in context
    assert "REGRAS DO PENSAMENTO INTERNO" in context
    assert "COMO ESTE NÚCLEO ORIENTA OS BEATS" in context
    assert "COMO ESTE NÚCLEO ORIENTA AS PONTES" in context
    assert "IDENTIDADE ESTÁVEL DE MARY" not in context
    assert "PERSONALIDADE ESTÁVEL" not in context


def test_beat_canonico_recebe_o_mesmo_character_core() -> None:
    script = _script()
    state = PilotState(node_id="encontro_acidental_001")

    turn = decide_editorial_progression_turn(script, state, "Tudo bem.")

    assert "NÚCLEO VIVO E AUTORITATIVO DE MARY" in turn.system_prompt
    assert "o beat define o que acontece" in turn.system_prompt.casefold()
    assert "o Usuário é o marido de Mary" in turn.system_prompt


def test_ponte_recebe_o_mesmo_character_core_sem_criar_outra_personagem() -> None:
    script = _script()
    state = PilotState(node_id="encontro_acidental_001")

    turn = decide_editorial_progression_turn(
        script,
        state,
        "Relaxa, não aconteceu nada. Você também está bem depois desse encontrão?",
    )

    assert turn.state.facts.get("_runtime_phase") == "bridge"
    assert "FASE ESTRUTURAL: PONTE NARRATIVA" in turn.system_prompt
    assert "NÚCLEO VIVO E AUTORITATIVO DE MARY" in turn.system_prompt
    assert "improvisar somente dentro do movimento atual" in turn.system_prompt
    assert "Beats e pontes são caminhos diferentes do mesmo personagem" in turn.system_prompt


def test_character_core_preserva_conflito_conjugal_sem_hedonismo_generico() -> None:
    document = load_source_document()
    context = build_narrative_context(document, [], {})

    assert "carência afetiva acumulada" in context
    assert "não transformar Mary em hedonista genérica" in context
    assert "não apagar o vínculo com o marido" in context
    assert "nem converter automaticamente a traição em desejo de separação" in context


def test_mary_define_intensidade_sexual_com_brevidade() -> None:
    document = load_source_document()
    context = build_narrative_context(document, [], {}, beat_id="reencontro_fila_001")

    assert "desejo sexual específico em poucas palavras" in context
    assert "pensamento é espontâneo, malicioso, sexual" in context
    assert "resposta deve ser curta, humana e sexualmente intensa" in context
    assert "Mary quer ocupar a cabeça do usuário e aumentar o desejo dele" in context


def test_caminho_de_mary_rejeita_intensidade_generica_e_prolixa() -> None:
    document = load_source_document()
    context = build_narrative_context(document, [], {}, beat_id="reencontro_fila_001")

    assert "desejo sexual específico em poucas palavras" in context
    assert "quero conhecê-lo melhor" in context
    assert "estou curiosa" in context
    assert "vontade física imediata" in context
