from __future__ import annotations

from services.editorial_beat_context import build_beat_context
from services.editorial_compiler import compile_editorial_document
from services.editorial_progression import prepare_editorial_script
from services.editorial_routing import resolve_declared_editorial_target
from services.editorial_runtime_impl import PilotScript, PilotState
from services.editorial_runtime_types import EditorialTurn
from services.editorial_transaction import PendingEditorialTurn, commit_editorial_turn
from services.organic_interaction import extract_assistant_facts, extract_user_facts


def _script() -> PilotScript:
    document = {
        "format_version": 3,
        "package_id": "test.semantic-introduction",
        "introduction": "Teste.",
        "blocks": [
            {
                "block_id": "main",
                "order": 1,
                "entry_beat_id": "before",
                "beats": [
                    {
                        "beat_id": "before",
                        "order": 1,
                        "type": "dialogue",
                        "required_movement": "Preparar a apresentação.",
                        "canonical_line": "Ainda nem nos apresentamos.",
                        "next_beat_id": "introduction",
                        "allowed_transitions": {"engaged": "introduction"},
                    },
                    {
                        "beat_id": "introduction",
                        "order": 2,
                        "type": "dialogue",
                        "required_movement": "Trocar os dois nomes.",
                        "canonical_line": "Eu sou a Mary. E você?",
                        "dramatic_direction": "Cumprir somente a parte pendente.",
                        "next_beat_id": "after",
                        "skip_when_facts": {
                            "mutual_introduction_completed": "after"
                        },
                        "constraints": {
                            "fact_variants": [
                                {
                                    "when_all_facts": ["mary_introduced_herself"],
                                    "when_no_facts": ["user_introduced_himself"],
                                    "required_movement": "Pedir somente o nome do usuário.",
                                    "canonical_line": "E você? Ainda nem me disse seu nome.",
                                    "dramatic_direction": "Não repetir o nome de Mary.",
                                },
                                {
                                    "when_all_facts": ["user_introduced_himself"],
                                    "when_no_facts": ["mary_introduced_herself"],
                                    "required_movement": "Apresentar somente Mary.",
                                    "canonical_line": "Prazer em saber seu nome. Eu sou a Mary.",
                                },
                            ]
                        },
                        "allowed_transitions": {"engaged": "after"},
                    },
                    {
                        "beat_id": "after",
                        "order": 3,
                        "type": "dialogue",
                        "required_movement": "Continuar.",
                        "canonical_line": "Vamos continuar.",
                        "allowed_transitions": {"engaged": "after"},
                    },
                ],
            }
        ],
    }
    return prepare_editorial_script(PilotScript(compile_editorial_document(document)))


def test_apresentacao_falada_por_mary_vira_fato_sem_usar_pensamento() -> None:
    facts = extract_assistant_facts(
        "[PENSAMENTO]Meu nome é Mary, mas não vou dizer ainda.[/PENSAMENTO]\n\nEu sou a Mary.",
        {},
    )

    assert facts["mary_name"] == "Mary"
    assert facts["mary_introduced_herself"] == "true"


def test_nome_de_mary_apenas_no_pensamento_nao_conta_como_apresentacao() -> None:
    facts = extract_assistant_facts(
        "[PENSAMENTO]Eu sou a Mary e ele ainda não sabe.[/PENSAMENTO]\n\nPrazer em conhecer você.",
        {},
    )

    assert "mary_introduced_herself" not in facts


def test_apresentacoes_separadas_derivam_conclusao_mutua() -> None:
    facts = extract_assistant_facts("Pode me chamar de Mary.", {})
    facts = extract_user_facts("Ah, sim, eu sou Janio. Prazer.", facts)

    assert facts["mary_introduced_herself"] == "true"
    assert facts["user_introduced_himself"] == "true"
    assert facts["user_name"] == "Janio"
    assert facts["mutual_introduction_completed"] == "true"


def test_commit_registra_apresentacao_somente_depois_da_resposta_aprovada() -> None:
    script = _script()
    state = PilotState(node_id="before")
    turn = EditorialTurn(
        engagement="engaged",
        target_id="before",
        visible_fallback="",
        system_prompt="",
        state=PilotState(node_id="before"),
    )
    context = build_beat_context(script, state, turn)
    pending = PendingEditorialTurn(state, turn.state, turn, context, "")

    committed = commit_editorial_turn(pending, "Eu sou a Mary.")

    assert "mary_introduced_herself" not in state.facts
    assert committed.state.facts["mary_introduced_herself"] == "true"


def test_beat_usa_variante_parcial_quando_mary_ja_se_apresentou() -> None:
    script = _script()
    previous = PilotState(node_id="before")
    proposed = PilotState(
        node_id="introduction",
        facts={"mary_introduced_herself": "true", "mary_name": "Mary"},
    )
    turn = EditorialTurn(
        engagement="engaged",
        target_id="introduction",
        visible_fallback="",
        system_prompt="",
        state=proposed,
    )

    context = build_beat_context(script, previous, turn)

    assert context.objective == "Pedir somente o nome do usuário."
    assert context.canonical_line == "E você? Ainda nem me disse seu nome."
    assert context.dramatic_direction == "Não repetir o nome de Mary."


def test_beat_de_apresentacao_e_pulado_quando_ambos_ja_se_apresentaram() -> None:
    script = _script()
    target, skipped = resolve_declared_editorial_target(
        script,
        "introduction",
        {
            "mary_introduced_herself": "true",
            "user_introduced_himself": "true",
            "mutual_introduction_completed": "true",
        },
    )

    assert target == "after"
    assert skipped == ("introduction",)
