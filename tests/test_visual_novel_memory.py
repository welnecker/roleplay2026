from services.visual_novel_history import current_assistant_messages


def test_player_exibe_apenas_quadro_atual_sem_apagar_historico() -> None:
    messages = [
        {"role": "assistant", "content": "quadro 1", "editorial_node": "q1"},
        {"role": "assistant", "content": "quadro 2", "editorial_node": "q2"},
        {"role": "assistant", "content": "quadro 3", "editorial_node": "q3"},
    ]

    visible = current_assistant_messages(messages)

    assert len(messages) == 3
    assert visible == (messages[-1],)


def test_player_ignora_eventual_mensagem_nao_visual_apos_quadro() -> None:
    messages = [
        {"role": "assistant", "content": "quadro atual"},
        {"role": "system", "content": "metadado"},
    ]

    assert current_assistant_messages(messages) == (messages[0],)


def test_player_sem_quadro_retorna_colecao_vazia() -> None:
    assert current_assistant_messages([{"role": "system", "content": "x"}]) == ()


def test_html_da_imagem_nao_duplica_payload_base64(tmp_path) -> None:
    from services.editorial_scene_images import zoomable_image_html

    image = tmp_path / "cena.png"
    image.write_bytes(b"imagem-unica")

    html = zoomable_image_html(image)

    assert html.count("data:image/png;base64,") == 1
    assert "zoomed.src=thumb.src" in html
