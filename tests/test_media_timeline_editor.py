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


def test_frame_accurate_index_capture_and_dib(tmp_path: Path) -> None:
    ffmpeg = core.ffmpeg_executable()
    source = tmp_path / "frames.mp4"
    generated = subprocess.run(
        [
            ffmpeg, "-y", "-f", "lavfi", "-i",
            "testsrc=size=160x90:rate=12:duration=1", "-pix_fmt", "yuv420p",
            str(source),
        ],
        capture_output=True,
        check=False,
    )
    if generated.returncode != 0:
        pytest.skip("O FFmpeg disponível não possui os codecs de teste.")

    info = core.probe_media(source)
    previews = core.extract_precision_frames(source, tmp_path / "precision", max_width=120)
    capture = core.extract_frame_at_index(source, tmp_path / "capture.png", 5)

    from PIL import Image

    assert info.fps == pytest.approx(12, abs=0.1)
    assert info.frame_count == 12
    assert len(previews) == 12
    assert core.frame_time(6, info.fps) == pytest.approx(0.5, abs=0.01)
    with Image.open(capture) as image:
        assert image.size == (160, 90)
    dib = core.image_dib_bytes(capture)
    assert len(dib) > 40
    assert dib[:4] == (40).to_bytes(4, "little")


def test_export_audio_track_as_wav(tmp_path: Path) -> None:
    ffmpeg = core.ffmpeg_executable()
    source = tmp_path / "tone.mp3"
    generated = subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=330:duration=2", str(source)],
        capture_output=True,
        check=False,
    )
    if generated.returncode != 0:
        pytest.skip("O FFmpeg disponível não possui encoder MP3.")
    destination = tmp_path / "track.wav"
    result = core.export_audio_clip(source, destination, start=0.25, end=1.25)
    assert result == destination
    assert destination.is_file()
    assert core.probe_media(destination).duration == pytest.approx(1.0, abs=0.08)
