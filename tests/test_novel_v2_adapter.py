from __future__ import annotations

from types import SimpleNamespace

from services.novel_v2_adapter import build_novel_prompt, movement_from_script, next_movement_id


def _script():
    return SimpleNamespace(
        first_beat_id="m1",
        beats={
            "m1": {
                "objective": "Eu reconheço {{nome}} no carro e me aproximo.",
                "block_id": "encontro",
                "units": [
                    {
                        "kind": "dialogue",
                        "anchor": "Oi, {{nome}}... tô indo aí...",
                        "instruction": "A aproximação é espontânea e alegre.",
                    },
                    {"kind": "wait_user"},
                ],
                "on_user": {"engaged": "m2", "hostile": "end_hostile"},
                "decision_gate": {"suggested_response": "Claro, entra aí."},
            },
            "m2": {
                "objective": "Eu conto que estou indo à praia e consigo a carona.",
                "block_id": "encontro",
                "units": [],
                "on_user": {"engaged": "fim"},
            },
        },
        endings={
            "fim": {
                "block_id": "encontro",
                "visible_delivery": {"text": "Eu me despeço e sigo meu caminho."},
            },
            "end_hostile": {
                "block_id": "encontro",
                "visible_delivery": {"text": "Encerramento antigo."},
            },
        },
    )


def test_primeiro_avanco_vai_direto_ao_primeiro_movimento() -> None:
    assert next_movement_id(_script(), "") == "m1"


def test_avanco_ignora_hostilidade_e_decision_gate_do_motor_antigo() -> None:
    assert next_movement_id(_script(), "m1") == "m2"


def test_adaptador_ignora_anchor_e_fala_exata() -> None:
    movement = movement_from_script(_script(), "m1")
    assert movement.instruction == "Eu reconheço {{nome}} no carro e me aproximo."
    assert "Oi, {{nome}}" not in movement.dramatic_direction
    assert "espontânea" in movement.dramatic_direction


def test_prompt_declara_continuidade_incremental() -> None:
    movement = movement_from_script(_script(), "m1")
    prompt = build_novel_prompt(character_name="Camilly", user_name="João", movement=movement)
    assert "O roteiro controla O QUE acontece" in prompt
    assert "conversa já em andamento" in prompt
    assert "Entregue o delta narrativo" in prompt
    assert "Não reabra, reexplique nem resuma beats anteriores" in prompt


def test_prompt_proibe_perguntas_e_espera_do_usuario() -> None:
    movement = movement_from_script(_script(), "m1")
    prompt = build_novel_prompt(character_name="Camilly", user_name="João", movement=movement)
    assert "Nunca termine com pergunta" in prompt
    assert "Não existe turno de resposta do protagonista" in prompt
    assert "O próximo clique presume a continuidade necessária" in prompt


def test_prompt_reduz_nome_e_verborragia() -> None:
    movement = movement_from_script(_script(), "m1")
    prompt = build_novel_prompt(character_name="Camilly", user_name="João", movement=movement)
    assert "três falas mais recentes" in prompt
    assert "normalmente 1 ou 2 frases curtas" in prompt
    assert "Se o beat cabe em uma frase" in prompt
    assert "sinônimos em série" in prompt


def test_prompt_pode_suprimir_nome_explicitamente() -> None:
    movement = movement_from_script(_script(), "m1")
    prompt = build_novel_prompt(
        character_name="Camilly",
        user_name="João",
        movement=movement,
        suppress_user_name=True,
    )
    assert "Não use o nome João nesta fala" in prompt


def test_encerramento_antigo_vira_sentido_dramatico_nao_fala_obrigatoria() -> None:
    movement = movement_from_script(_script(), "fim")
    assert movement.is_ending is True
    assert "sem copiá-la literalmente" in movement.instruction
