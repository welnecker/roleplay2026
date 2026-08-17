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


def test_prompt_declara_novela_continua_sem_confirmacao() -> None:
    movement = movement_from_script(_script(), "m1")
    prompt = build_novel_prompt(character_name="Camilly", user_name="João", movement=movement)
    assert "O roteiro controla O QUE acontece" in prompt
    assert "Não peça confirmação" in prompt
    assert "Hesitações previstas" in prompt
    assert "João" in prompt


def test_prompt_proibe_perguntas_que_travam_o_avanco() -> None:
    movement = movement_from_script(_script(), "m1")
    prompt = build_novel_prompt(character_name="Camilly", user_name="João", movement=movement)
    assert "Nunca termine a saída com pergunta" in prompt
    assert "o próximo movimento poderá assumir que isso aconteceu" in prompt
    assert "o que você acha?" in prompt
    assert "Pronto, agora que você parou" in prompt


def test_encerramento_antigo_vira_sentido_dramatico_nao_fala_obrigatoria() -> None:
    movement = movement_from_script(_script(), "fim")
    assert movement.is_ending is True
    assert "sem copiá-la literalmente" in movement.instruction
