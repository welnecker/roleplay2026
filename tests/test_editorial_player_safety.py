from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_player_bootstrap_instala_somente_camadas_da_visual_novel_v2() -> None:
    source = (ROOT / "services" / "editorial_player.py").read_text(encoding="utf-8")

    assert "install_editorial_scene_image_hook" not in source
    assert "install_contextual_player_cycle" not in source
    assert "install_novel_frame_v2()" in source
    assert "install_novel_frame_reveal()" in source
    assert "install_novel_frame_presentation()" in source


def test_camada_visual_nao_substitui_chat_input() -> None:
    source = (ROOT / "services" / "editorial_scene_images.py").read_text(encoding="utf-8")

    assert "st.chat_input =" not in source
    assert "_ORIGINAL_CHAT_INPUT_ATTR" not in source
    assert "expanded=False" in source


def test_runtime_renderiza_imagem_explicitamente_antes_do_input() -> None:
    source = (ROOT / "services" / "editorial_player_runtime.py").read_text(encoding="utf-8")

    render_position = source.index("render_current_scene(editorial_state)")
    input_position = source.index('st.chat_input("Responda")')

    assert render_position < input_position
