from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "media_timeline_editor"
    / "core.py"
)
spec = importlib.util.spec_from_file_location("media_timeline_editor_core", MODULE_PATH)
assert spec and spec.loader
core = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = core
spec.loader.exec_module(core)


def test_interval_is_clamped_and_rejects_empty_selection() -> None:
    assert core.validate_interval(-2, 15, 10) == (0.0, 10.0)
    with pytest.raises(core.MediaEditorError):
        core.validate_interval(3, 3.1, 10)


def test_export_generates_multiframe_webp_and_equal_audio_duration(tmp_path: Path) -> None:
    ffmpeg = core.ffmpeg_executable()
    source = tmp_path / "source.mp4"
    generated = subprocess.run(
        [
            ffmpeg, "-y", "-f", "lavfi", "-i",
            "testsrc=size=160x90:rate=12:duration=2",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-shortest", "-pix_fmt", "yuv420p", str(source),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if generated.returncode != 0:
        pytest.skip("O FFmpeg disponível não possui os codecs de teste.")

    result = core.export_synchronized_clip(
        source,
        tmp_path / "output",
        "camilly1",
        start=0.25,
        end=1.75,
        fps=8,
        max_side=120,
        audio_offset_ms=200,
    )

    from PIL import Image

    assert result.webp_path.name == "camilly1_motion.webp"
    assert result.audio_path is not None
    assert result.audio_path.name == "camilly1_audio.mp3"
    assert result.duration == pytest.approx(1.5)
    assert result.frame_count >= 10
    with Image.open(result.webp_path) as image:
        assert image.format == "WEBP"
        assert image.n_frames == result.frame_count
        assert max(image.size) <= 120
    audio_info = core.probe_media(result.audio_path)
    assert audio_info.duration == pytest.approx(result.duration, abs=0.08)


def test_waveform_returns_requested_number_of_points(tmp_path: Path) -> None:
    ffmpeg = core.ffmpeg_executable()
    source = tmp_path / "tone.mp3"
    generated = subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=220:duration=1", str(source)],
        capture_output=True,
        check=False,
    )
    if generated.returncode != 0:
        pytest.skip("O FFmpeg disponível não possui encoder MP3.")
    peaks = core.waveform_peaks(source, start=0, duration=1, points=64)
    assert len(peaks) == 64
    assert max(peaks) > 0
