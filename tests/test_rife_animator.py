from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from tools.rife_animator import core
from tools.rife_animator.core import AnimatorError, RenderSettings, cycle_sequence, prepare_keyframes


def make_image(path: Path, size=(101, 99), color="red") -> Path:
    Image.new("RGB", size, color).save(path)
    return path


def test_loop_fecha_na_primeira_imagem(tmp_path: Path) -> None:
    images = [make_image(tmp_path / f"{index}.png") for index in range(3)]
    sequence = cycle_sequence(images, "loop")
    assert sequence == [*images, images[0]]


def test_pingpong_retorna_ate_a_primeira_imagem(tmp_path: Path) -> None:
    images = [make_image(tmp_path / f"{index}.png") for index in range(4)]
    sequence = cycle_sequence(images, "pingpong")
    assert sequence == [images[0], images[1], images[2], images[3], images[2], images[1], images[0]]


def test_preparo_padroniza_dimensoes_pares_sem_alterar_originais(tmp_path: Path) -> None:
    first = make_image(tmp_path / "a.png", (101, 99))
    second = make_image(tmp_path / "b.png", (80, 120), "blue")
    output = tmp_path / "prepared"
    written = prepare_keyframes([first, second], "loop", output)
    assert len(written) == 3
    assert Image.open(written[0]).size == (100, 98)
    assert Image.open(written[1]).size == (100, 98)
    assert Image.open(first).size == (101, 99)


def test_exige_entre_duas_e_doze_imagens(tmp_path: Path) -> None:
    image = make_image(tmp_path / "only.png")
    with pytest.raises(AnimatorError, match="entre 2 e 12"):
        cycle_sequence([image], "loop")


def test_configuracao_inicial_de_12_segundos_e_valida() -> None:
    RenderSettings().validate()


def test_vulkan_gera_ciclo_de_dois_segundos_e_mp4_de_doze(
    tmp_path: Path, monkeypatch
) -> None:
    images = [make_image(tmp_path / f"{index}.png") for index in range(4)]
    rife = tmp_path / "rife.exe"
    ffmpeg = tmp_path / "ffmpeg.exe"
    rife.touch()
    ffmpeg.touch()
    commands: list[list[str]] = []
    monkeypatch.setattr(core, "_run", lambda command, **_kwargs: commands.append(command))

    output = core.render_with_vulkan(
        images,
        rife_executable=rife,
        ffmpeg=ffmpeg,
        output=tmp_path / "scene.mp4",
        settings=RenderSettings(duration_seconds=12, cycle_seconds=2, fps=24),
    )

    assert output.name == "scene.mp4"
    assert commands[0][commands[0].index("-n") + 1] == "49"
    assert commands[1][commands[1].index("-t") + 1] == "12.000"
    assert "+faststart" in commands[1]
