from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "tools" / "media_timeline_editor" / "core.py"
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


def test_export_generates_multiframe_webp_and_equal_audio_duration(
    tmp_path: Path,
) -> None:
    ffmpeg = core.ffmpeg_executable()
    source = tmp_path / "source.mp4"
    generated = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=160x90:rate=12:duration=2",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
            "-shortest",
            "-pix_fmt",
            "yuv420p",
            str(source),
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
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=220:duration=1",
            str(source),
        ],
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
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=160x90:rate=12:duration=1",
            "-pix_fmt",
            "yuv420p",
            str(source),
        ],
        capture_output=True,
        check=False,
    )
    if generated.returncode != 0:
        pytest.skip("O FFmpeg disponível não possui os codecs de teste.")

    info = core.probe_media(source)
    previews = core.extract_precision_frames(
        source, tmp_path / "precision", max_width=120
    )
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
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=330:duration=2",
            str(source),
        ],
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


def test_audio_segment_can_be_split_moved_trimmed_and_renamed() -> None:
    original = core.create_audio_segment(6.0, name="dialogo", timeline_start=1.0)
    left, right = core.split_audio_segment(original, 3.5)

    assert left.source_start == 0
    assert left.source_end == pytest.approx(2.5)
    assert left.timeline_start == pytest.approx(1.0)
    assert right.source_start == pytest.approx(2.5)
    assert right.timeline_start == pytest.approx(3.5)

    moved = core.move_audio_segment(right, 5.0)
    trimmed = core.trim_audio_segment(moved, source_start=3.0, source_end=5.5)
    renamed = core.rename_audio_segments([left, trimmed], "camilly fala")

    assert trimmed.timeline_start == pytest.approx(5.0)
    assert trimmed.duration == pytest.approx(2.5)
    assert [item.name for item in renamed] == [
        "camilly_fala_01",
        "camilly_fala_02",
    ]


def test_split_rejects_cut_too_close_to_segment_edges() -> None:
    segment = core.create_audio_segment(2.0)
    with pytest.raises(core.MediaEditorError):
        core.split_audio_segment(segment, 0.05)


def test_export_audio_segments_creates_individual_files(tmp_path: Path) -> None:
    ffmpeg = core.ffmpeg_executable()
    source = tmp_path / "dialogue.mp3"
    generated = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=330:duration=3",
            str(source),
        ],
        capture_output=True,
        check=False,
    )
    if generated.returncode != 0:
        pytest.skip("O FFmpeg disponível não possui encoder MP3.")

    segments = [
        core.AudioSegment("fala_01", 0.0, 1.0, 0.0),
        core.AudioSegment("fala_02", 1.25, 2.75, 1.0),
    ]
    results = core.export_audio_segments(source, tmp_path / "parts", segments)

    assert [path.name for path in results] == ["fala_01.mp3", "fala_02.mp3"]
    assert core.probe_media(results[0]).duration == pytest.approx(1.0, abs=0.08)
    assert core.probe_media(results[1]).duration == pytest.approx(1.5, abs=0.08)


def test_export_synchronized_segment_uses_audio_source_range_and_timeline_position(
    tmp_path: Path,
) -> None:
    ffmpeg = core.ffmpeg_executable()
    video = tmp_path / "visual.mp4"
    audio = tmp_path / "dialogue.mp3"
    video_result = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=160x90:rate=10:duration=4",
            "-pix_fmt",
            "yuv420p",
            str(video),
        ],
        capture_output=True,
        check=False,
    )
    audio_result = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=5",
            str(audio),
        ],
        capture_output=True,
        check=False,
    )
    if video_result.returncode != 0 or audio_result.returncode != 0:
        pytest.skip("O FFmpeg disponível não possui os codecs de teste.")

    segment = core.AudioSegment("fala_01", 2.0, 3.5, 1.0)
    result = core.export_synchronized_segment(
        video,
        audio,
        segment,
        tmp_path / "out",
        "camilly_01",
        fps=8,
        max_side=120,
    )

    assert result.duration == pytest.approx(1.5)
    assert result.webp_path.name == "camilly_01_motion.webp"
    assert result.audio_path is not None
    assert core.probe_media(result.audio_path).duration == pytest.approx(1.5, abs=0.08)
