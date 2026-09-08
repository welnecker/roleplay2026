from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_flet_player_nao_contem_quadro_ou_imagem_demonstrativos() -> None:
    source = (ROOT / "flet_client" / "main.py").read_text(encoding="utf-8")

    assert "DEMO_FRAME" not in source
    assert "DEMO_IMAGE" not in source
    assert "api_client.open_run" in source
    assert "api_client.advance_run" in source


def test_api_run_le_roteiros_do_runtime_e_persiste_interactions() -> None:
    source = (ROOT / "flet_api" / "runs.py").read_text(encoding="utf-8")

    assert "load_editorial_package" in source
    assert "open_persistent_runtime" in source
    assert "persist_assistant_message" in source
    assert "persist_frame_reveal" in source
