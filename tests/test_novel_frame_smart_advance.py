from __future__ import annotations

from services import novel_frame_reveal_patch as reveal_patch


def test_quadro_novo_comeca_com_primeiro_card_visivel(monkeypatch) -> None:
    state: dict[str, object] = {}
    monkeypatch.setattr(reveal_patch.st, "session_state", state)

    reveal_patch.start_frame_reveal("encontro_001")

    assert state[reveal_patch.reveal_key("encontro_001")] == 1
    assert reveal_patch.reveal_index("encontro_001", 4) == 1
    assert reveal_patch.reveal_index("encontro_001", 1) == 1
    assert reveal_patch.reveal_index("encontro_001", 0) == 0


def test_um_card_exige_um_clique_para_avancar_quadro(monkeypatch) -> None:
    state: dict[str, object] = {
        "novel_frame_reveal:current": {"frame_id": "quadro_001", "entry_count": 1},
        reveal_patch.reveal_key("quadro_001"): 1,
    }
    monkeypatch.setattr(reveal_patch.st, "session_state", state)
    monkeypatch.setattr(reveal_patch, "_original_button", lambda *args, **kwargs: True)
    monkeypatch.setattr(reveal_patch, "_synchronize_remote_run", lambda **kwargs: False)
    monkeypatch.setattr(reveal_patch.time, "monotonic", lambda: 10.0)

    assert reveal_patch._button_wrapper("Avançar") is True


def test_quatro_cards_revelam_restantes_antes_de_avancar(monkeypatch) -> None:
    state: dict[str, object] = {
        "novel_frame_reveal:current": {"frame_id": "quadro_004", "entry_count": 4},
        reveal_patch.reveal_key("quadro_004"): 1,
    }
    reruns: list[bool] = []
    monkeypatch.setattr(reveal_patch.st, "session_state", state)
    monkeypatch.setattr(reveal_patch.st, "rerun", lambda: reruns.append(True))
    monkeypatch.setattr(reveal_patch, "_original_button", lambda *args, **kwargs: True)
    monkeypatch.setattr(reveal_patch, "_synchronize_remote_run", lambda **kwargs: False)
    clock = iter((10.0, 11.0, 12.0, 13.0))
    monkeypatch.setattr(reveal_patch.time, "monotonic", lambda: next(clock))

    key = reveal_patch.reveal_key("quadro_004")

    assert reveal_patch._button_wrapper("Avançar") is False
    assert state[key] == 2
    assert reveal_patch._button_wrapper("Avançar") is False
    assert state[key] == 3
    assert reveal_patch._button_wrapper("Avançar") is False
    assert state[key] == 4
    assert len(reruns) == 3

    # O quarto clique já encontra todos os cards visíveis e avança o runtime.
    assert reveal_patch._button_wrapper("Avançar") is True
    assert state[key] == 4


def test_duplo_clique_em_avancar_e_ignorado(monkeypatch) -> None:
    state: dict[str, object] = {
        "novel_frame_reveal:current": {"frame_id": "quadro_001", "entry_count": 2},
        reveal_patch.reveal_key("quadro_001"): 1,
    }
    reruns: list[bool] = []
    clock = iter((10.0, 10.2))
    monkeypatch.setattr(reveal_patch.st, "session_state", state)
    monkeypatch.setattr(reveal_patch.st, "rerun", lambda: reruns.append(True))
    monkeypatch.setattr(reveal_patch, "_original_button", lambda *args, **kwargs: True)
    monkeypatch.setattr(reveal_patch, "_synchronize_remote_run", lambda **kwargs: False)
    monkeypatch.setattr(reveal_patch.time, "monotonic", lambda: next(clock))

    key = reveal_patch.reveal_key("quadro_001")
    assert reveal_patch._button_wrapper("Avançar") is False
    assert state[key] == 2

    assert reveal_patch._button_wrapper("Avançar") is False
    assert state[key] == 2
    assert len(reruns) == 1
