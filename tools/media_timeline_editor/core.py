from __future__ import annotations

import array
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


class MediaEditorError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class MediaInfo:
    duration: float
    width: int
    height: int
    fps: float
    has_audio: bool


@dataclass(frozen=True, slots=True)
class ExportResult:
    webp_path: Path
    audio_path: Path | None
    duration: float
    frame_count: int
    fps: int


_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_VIDEO_RE = re.compile(r"Video:.*?(\d{2,5})x(\d{2,5}).*?(\d+(?:\.\d+)?)\s*fps")


def ffmpeg_executable() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        resolved = shutil.which("ffmpeg")
        if resolved:
            return resolved
    raise MediaEditorError("FFmpeg não foi encontrado.")


def _run(command: list[str], *, binary: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        capture_output=True,
        text=not binary,
        check=False,
    )


def probe_media(source: Path) -> MediaInfo:
    if not source.is_file():
        raise MediaEditorError(f"Arquivo não encontrado: {source}")
    completed = _run([ffmpeg_executable(), "-hide_banner", "-i", str(source)])
    diagnostic = str(completed.stderr or "")
    duration_match = _DURATION_RE.search(diagnostic)
    if duration_match is None:
        raise MediaEditorError("Não foi possível determinar a duração da mídia.")
    hours, minutes, seconds = duration_match.groups()
    duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    video_match = _VIDEO_RE.search(diagnostic)
    width = int(video_match.group(1)) if video_match else 0
    height = int(video_match.group(2)) if video_match else 0
    fps = float(video_match.group(3)) if video_match else 0.0
    return MediaInfo(
        duration=duration,
        width=width,
        height=height,
        fps=fps,
        has_audio="Audio:" in diagnostic,
    )


def validate_interval(start: float, end: float, duration: float) -> tuple[float, float]:
    clean_start = max(0.0, float(start))
    clean_end = min(float(duration), float(end))
    if clean_end - clean_start < 0.2:
        raise MediaEditorError("O intervalo precisa ter pelo menos 0,2 segundo.")
    return clean_start, clean_end


def extract_timeline_frames(
    source: Path,
    destination: Path,
    *,
    sample_fps: float = 2.0,
    width: int = 220,
) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    for stale in destination.glob("timeline_*.jpg"):
        stale.unlink()
    command = [
        ffmpeg_executable(), "-y", "-i", str(source), "-an",
        "-vf", f"fps={max(0.2, float(sample_fps))},scale={int(width)}:-2:flags=lanczos",
        "-q:v", "4", str(destination / "timeline_%06d.jpg"),
    ]
    completed = _run(command)
    frames = sorted(destination.glob("timeline_*.jpg"))
    if completed.returncode != 0 or not frames:
        detail = str(completed.stderr or "").strip().splitlines()
        raise MediaEditorError(
            "Falha ao extrair a timeline."
            + (f" Detalhe: {detail[-1]}" if detail else "")
        )
    return frames


def waveform_peaks(
    source: Path,
    *,
    start: float,
    duration: float,
    points: int = 900,
) -> list[float]:
    command = [
        ffmpeg_executable(), "-hide_banner", "-loglevel", "error",
        "-ss", f"{max(0.0, start):.6f}", "-i", str(source),
        "-t", f"{max(0.1, duration):.6f}", "-vn", "-ac", "1", "-ar", "8000",
        "-f", "s16le", "pipe:1",
    ]
    completed = _run(command, binary=True)
    if completed.returncode != 0 or not completed.stdout:
        return [0.0] * max(1, points)
    samples = array.array("h")
    samples.frombytes(completed.stdout)
    bucket = max(1, len(samples) // max(1, points))
    peaks: list[float] = []
    for index in range(0, len(samples), bucket):
        block = samples[index : index + bucket]
        peaks.append(max((abs(value) for value in block), default=0) / 32768.0)
        if len(peaks) >= points:
            break
    return peaks + [0.0] * max(0, points - len(peaks))


def _extract_frames(
    source: Path,
    destination: Path,
    *,
    start: float,
    duration: float,
    fps: int,
    max_side: int,
) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    scale = (
        f"scale='if(gt(iw,ih),min({int(max_side)},iw),-2)':"
        f"'if(gt(iw,ih),-2,min({int(max_side)},ih))':flags=lanczos"
    )
    command = [
        ffmpeg_executable(), "-y", "-ss", f"{start:.6f}", "-i", str(source),
        "-t", f"{duration:.6f}", "-an", "-vf", f"fps={int(fps)},{scale}",
        str(destination / "frame_%06d.png"),
    ]
    completed = _run(command)
    frames = sorted(destination.glob("frame_*.png"))
    if completed.returncode != 0 or len(frames) < 2:
        detail = str(completed.stderr or "").strip().splitlines()
        raise MediaEditorError(
            "Falha ao extrair os quadros do trecho."
            + (f" Detalhe: {detail[-1]}" if detail else "")
        )
    return frames


def _save_animated_webp(
    frames: list[Path],
    destination: Path,
    *,
    fps: int,
    quality: int,
) -> None:
    from PIL import Image

    images = [Image.open(path).convert("RGB") for path in frames]
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        images[0].save(
            destination,
            "WEBP",
            save_all=True,
            append_images=images[1:],
            duration=max(1, round(1000 / int(fps))),
            loop=1,
            quality=max(1, min(100, int(quality))),
            method=6,
        )
    finally:
        for image in images:
            image.close()


def _export_audio(
    source: Path,
    destination: Path,
    *,
    source_start: float,
    duration: float,
    offset_ms: int,
    volume: float,
    fade_in_ms: int,
    fade_out_ms: int,
) -> None:
    delay_ms = max(0, int(offset_ms))
    trim_start = max(0.0, float(source_start) + max(0, -int(offset_ms)) / 1000.0)
    fade_in = max(0.0, int(fade_in_ms) / 1000.0)
    fade_out = max(0.0, int(fade_out_ms) / 1000.0)
    # Trim in the filter graph instead of using input seeking. Some MP4 edit
    # lists otherwise produce backward timestamps after ``adelay`` and make the
    # MP3 shorter than the selected WebP interval.
    filters = [
        f"atrim=start={trim_start:.6f}:end={trim_start + duration:.6f}",
        "asetpts=PTS-STARTPTS",
        f"volume={max(0.0, float(volume)):.4f}",
    ]
    if delay_ms:
        filters.append(f"adelay={delay_ms}:all=1")
    filters.append("aresample=async=1:first_pts=0")
    filters.extend(
        [
            f"apad=whole_dur={duration:.6f}",
            f"atrim=0:{duration:.6f}",
            "asetpts=N/SR/TB",
        ]
    )
    if fade_in:
        filters.append(f"afade=t=in:st=0:d={min(fade_in, duration):.6f}")
    if fade_out:
        fade_start = max(0.0, duration - fade_out)
        filters.append(f"afade=t=out:st={fade_start:.6f}:d={min(fade_out, duration):.6f}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg_executable(), "-y", "-i", str(source),
        "-vn", "-af", ",".join(filters),
        "-c:a", "libmp3lame", "-b:a", "192k", str(destination),
    ]
    completed = _run(command)
    if completed.returncode != 0 or not destination.is_file():
        detail = str(completed.stderr or "").strip().splitlines()
        raise MediaEditorError(
            "Falha ao exportar o áudio sincronizado."
            + (f" Detalhe: {detail[-1]}" if detail else "")
        )


def export_synchronized_clip(
    video_source: Path,
    destination_dir: Path,
    basename: str,
    *,
    start: float,
    end: float,
    fps: int = 12,
    quality: int = 78,
    max_side: int = 1280,
    audio_source: Path | None = None,
    audio_offset_ms: int = 0,
    audio_volume: float = 1.0,
    audio_fade_in_ms: int = 0,
    audio_fade_out_ms: int = 250,
) -> ExportResult:
    info = probe_media(video_source)
    start, end = validate_interval(start, end, info.duration)
    duration = end - start
    clean_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", basename).strip("_") or "motion"
    webp_path = destination_dir / f"{clean_name}_motion.webp"
    selected_audio = audio_source if audio_source is not None else (video_source if info.has_audio else None)
    audio_path = destination_dir / f"{clean_name}_audio.mp3" if selected_audio else None
    with tempfile.TemporaryDirectory(prefix="entrecenas_media_") as temp:
        frames = _extract_frames(
            video_source, Path(temp), start=start, duration=duration,
            fps=max(1, int(fps)), max_side=max(64, int(max_side)),
        )
        _save_animated_webp(frames, webp_path, fps=max(1, int(fps)), quality=quality)
        if selected_audio is not None and audio_path is not None:
            source_start = start if selected_audio == video_source else 0.0
            _export_audio(
                selected_audio, audio_path, source_start=source_start,
                duration=duration, offset_ms=audio_offset_ms, volume=audio_volume,
                fade_in_ms=audio_fade_in_ms, fade_out_ms=audio_fade_out_ms,
            )
    return ExportResult(webp_path, audio_path, duration, len(frames), max(1, int(fps)))


__all__ = [
    "ExportResult", "MediaEditorError", "MediaInfo", "export_synchronized_clip",
    "extract_timeline_frames", "ffmpeg_executable", "probe_media",
    "validate_interval", "waveform_peaks",
]
