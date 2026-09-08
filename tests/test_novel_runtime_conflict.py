from __future__ import annotations

from services.novel_runtime_conflict import persisted_movement_at_sequence


def test_adota_movimento_ja_persistido_na_mesma_sequencia() -> None:
    persisted = {
        "role": "assistant",
        "sequence": 1,
        "editorial_node": "abertura_001",
        "content": "Quadro salvo pela primeira sessão",
    }

    assert persisted_movement_at_sequence(
        [persisted], sequence=1, target_id="abertura_001"
    ) is persisted


def test_nao_mascara_colisao_entre_movimentos_diferentes() -> None:
    persisted = {
        "role": "assistant",
        "sequence": 2,
        "beat_id": "quadro_002",
        "content": "Outro movimento",
    }

    assert (
        persisted_movement_at_sequence(
            [persisted], sequence=2, target_id="quadro_003"
        )
        is None
    )
