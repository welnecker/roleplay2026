from __future__ import annotations

import array
import io
import os
import re
import json
import os
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
    frame_count: int


@dataclass(frozen=True, slots=True)
class ExportResult:
    webp_path: Path
    audio_path: Path | None
    duration: float
    frame_count: int
    fps: int


@dataclass(frozen=True, slots=True)
class AudioSegment:
    """Trecho não destrutivo de uma gravação colocado na timeline."""

    name: str
    source_start: float
    source_end: float
    timeline_start: float

    @property
    def duration(self) -> float:
        return max(0.0, self.source_end - self.source_start)

    @property
    def timeline_end(self) -> float:
        return self.timeline_start + self.duration


_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_VIDEO_SIZE_RE = re.compile(r"Video:.*?(\d{2,5})x(\d{2,5})")
_VIDEO_RATE_RE = re.compile(r"Video:.*?(\d+(?:\.\d+)?)\s*(?:fps|tbr)")


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
    size_match = _VIDEO_SIZE_RE.search(diagnostic)
    rate_match = _VIDEO_RATE_RE.search(diagnostic)
    width = int(size_match.group(1)) if size_match else 0
    height = int(size_match.group(2)) if size_match else 0
    fps = float(rate_match.group(1)) if rate_match else 0.0
    return MediaInfo(
        duration=duration,
        width=width,
        height=height,
        fps=fps,
        has_audio="Audio:" in diagnostic,
        frame_count=max(1, round(duration * fps)) if fps else 1,
    )


def frame_time(frame_index: int, fps: float) -> float:
    if fps <= 0:
        raise MediaEditorError("O vídeo não informou uma taxa de quadros válida.")
    return max(0, int(frame_index)) / float(fps)


def extract_precision_frames(
    source: Path,
    destination: Path,
    *,
    max_width: int = 960,
) -> list[Path]:
    """Decode every source frame into a lightweight, frame-accurate preview."""
    destination.mkdir(parents=True, exist_ok=True)
    for stale in destination.glob("precision_*.jpg"):
        stale.unlink()
    scale = f"scale='min({max(160, int(max_width))},iw)':-2:flags=lanczos"
    command = [
        ffmpeg_executable(),
        "-y",
        "-i",
        str(source),
        "-an",
        "-vsync",
        "0",
        "-vf",
        scale,
        "-q:v",
        "4",
        str(destination / "precision_%08d.jpg"),
    ]
    completed = _run(command)
    frames = sorted(destination.glob("precision_*.jpg"))
    if completed.returncode != 0 or not frames:
        detail = str(completed.stderr or "").strip().splitlines()
        raise MediaEditorError(
            "Falha ao indexar os quadros do vídeo."
            + (f" Detalhe: {detail[-1]}" if detail else "")
        )
    return frames


def extract_frame_at_index(
    source: Path,
    destination: Path,
    frame_index: int,
) -> Path:
    """Extract one original-resolution source frame by its zero-based index."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    select = f"select=eq(n\\,{max(0, int(frame_index))})"
    command = [
        ffmpeg_executable(),
        "-y",
        "-i",
        str(source),
        "-an",
        "-vf",
        select,
        "-vsync",
        "0",
        "-frames:v",
        "1",
        str(destination),
    ]
    completed = _run(command)
    if completed.returncode != 0 or not destination.is_file():
        detail = str(completed.stderr or "").strip().splitlines()
        raise MediaEditorError(
            "Falha ao extrair o frame selecionado."
            + (f" Detalhe: {detail[-1]}" if detail else "")
        )
    return destination


def image_dib_bytes(source: Path) -> bytes:
    """Return Windows CF_DIB bytes (a BMP without its 14-byte file header)."""
    from PIL import Image

    with Image.open(source) as image:
        converted = image.convert("RGB")
        buffer = io.BytesIO()
        converted.save(buffer, "BMP")
    return buffer.getvalue()[14:]


def copy_image_to_clipboard(source: Path) -> None:
    if os.name != "nt":
        raise MediaEditorError(
            "A cópia de imagem está disponível no aplicativo Windows."
        )
    import ctypes

    data = image_dib_bytes(source)
    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32
    kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p
    handle = kernel32.GlobalAlloc(0x0002, len(data))  # GMEM_MOVEABLE
    if not handle:
        raise MediaEditorError("O Windows não reservou memória para a imagem.")
    pointer = kernel32.GlobalLock(handle)
    ctypes.memmove(pointer, data, len(data))
    kernel32.GlobalUnlock(handle)
    if not user32.OpenClipboard(None):
        kernel32.GlobalFree(handle)
        raise MediaEditorError(
            "A área de transferência está sendo usada por outro programa."
        )
    try:
        user32.EmptyClipboard()
        if not user32.SetClipboardData(8, handle):  # CF_DIB
            kernel32.GlobalFree(handle)
            raise MediaEditorError("Não foi possível copiar o frame.")
        handle = None  # ownership transferred to Windows
    finally:
        user32.CloseClipboard()


def validate_interval(start: float, end: float, duration: float) -> tuple[float, float]:
    clean_start = max(0.0, float(start))
    clean_end = min(float(duration), float(end))
    if clean_end - clean_start < 0.2:
        raise MediaEditorError("O intervalo precisa ter pelo menos 0,2 segundo.")
    return clean_start, clean_end


def create_audio_segment(
    duration: float,
    *,
    name: str = "audio_01",
    timeline_start: float = 0.0,
) -> AudioSegment:
    if float(duration) < 0.2:
        raise MediaEditorError("O áudio precisa ter pelo menos 0,2 segundo.")
    return AudioSegment(
        name=str(name or "audio_01"),
        source_start=0.0,
        source_end=float(duration),
        timeline_start=max(0.0, float(timeline_start)),
    )


def split_audio_segment(
    segment: AudioSegment,
    timeline_time: float,
    *,
    minimum_duration: float = 0.1,
) -> tuple[AudioSegment, AudioSegment]:
    local_time = float(timeline_time) - segment.timeline_start
    source_cut = segment.source_start + local_time
    minimum = max(0.05, float(minimum_duration))
    if (
        source_cut - segment.source_start < minimum
        or segment.source_end - source_cut < minimum
    ):
        raise MediaEditorError(
            "Posicione o cursor dentro do bloco, deixando espaço dos dois lados."
        )
    left = AudioSegment(
        name=segment.name,
        source_start=segment.source_start,
        source_end=source_cut,
        timeline_start=segment.timeline_start,
    )
    right = AudioSegment(
        name=segment.name,
        source_start=source_cut,
        source_end=segment.source_end,
        timeline_start=float(timeline_time),
    )
    return left, right


def trim_audio_segment(
    segment: AudioSegment,
    *,
    source_start: float | None = None,
    source_end: float | None = None,
    minimum_duration: float = 0.1,
) -> AudioSegment:
    clean_start = segment.source_start if source_start is None else float(source_start)
    clean_end = segment.source_end if source_end is None else float(source_end)
    if clean_start < 0 or clean_end - clean_start < max(0.05, minimum_duration):
        raise MediaEditorError("O trecho de áudio ficou curto ou inválido.")
    return AudioSegment(
        name=segment.name,
        source_start=clean_start,
        source_end=clean_end,
        timeline_start=segment.timeline_start,
    )


def move_audio_segment(segment: AudioSegment, timeline_start: float) -> AudioSegment:
    return AudioSegment(
        name=segment.name,
        source_start=segment.source_start,
        source_end=segment.source_end,
        timeline_start=max(0.0, float(timeline_start)),
    )


def rename_audio_segments(
    segments: list[AudioSegment],
    basename: str,
) -> list[AudioSegment]:
    clean = re.sub(r"[^a-zA-Z0-9_-]+", "_", basename).strip("_") or "audio"
    return [
        AudioSegment(
            name=f"{clean}_{index:02d}",
            source_start=segment.source_start,
            source_end=segment.source_end,
            timeline_start=segment.timeline_start,
        )
        for index, segment in enumerate(segments, start=1)
    ]


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
        ffmpeg_executable(),
        "-y",
        "-i",
        str(source),
        "-an",
        "-vf",
        f"fps={max(0.2, float(sample_fps))},scale={int(width)}:-2:flags=lanczos",
        "-q:v",
        "4",
        str(destination / "timeline_%06d.jpg"),
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
        ffmpeg_executable(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{max(0.0, start):.6f}",
        "-i",
        str(source),
        "-t",
        f"{max(0.1, duration):.6f}",
        "-vn",
        "-ac",
        "1",
        "-ar",
        "8000",
        "-f",
        "s16le",
        "pipe:1",
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
        ffmpeg_executable(),
        "-y",
        "-ss",
        f"{start:.6f}",
        "-i",
        str(source),
        "-t",
        f"{duration:.6f}",
        "-an",
        "-vf",
        f"fps={int(fps)},{scale}",
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
        filters.append(
            f"afade=t=out:st={fade_start:.6f}:d={min(fade_out, duration):.6f}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    codec = (
        ["-c:a", "pcm_s16le"]
        if destination.suffix.lower() == ".wav"
        else [
            "-c:a",
            "libmp3lame",
            "-b:a",
            "192k",
        ]
    )

    # O modo acoplado pode reabrir o áudio já pré-salvo de uma linha e
    # exportar o novo corte para o mesmo audio_id. O FFmpeg não aceita
    # entrada e saída no mesmo arquivo. Nessa situação, convertemos para
    # um temporário irmão e só substituímos o original após sucesso.
    try:
        same_file = source.resolve() == destination.resolve()
    except OSError:
        same_file = False
    output_path = (
        destination.with_name(
            f".{destination.stem}.entrecenas_tmp{destination.suffix}"
        )
        if same_file
        else destination
    )
    if output_path != destination and output_path.exists():
        output_path.unlink()

    command = [
        ffmpeg_executable(),
        "-y",
        "-i",
        str(source),
        "-vn",
        "-af",
        ",".join(filters),
        *codec,
        str(output_path),
    ]
    completed = _run(command)
    if completed.returncode != 0 or not output_path.is_file():
        if output_path != destination:
            output_path.unlink(missing_ok=True)
        detail = str(completed.stderr or "").strip().splitlines()
        diagnostic = " | ".join(detail[-4:]) if detail else ""
        raise MediaEditorError(
            "Falha ao exportar o áudio sincronizado."
            + (f" Detalhe: {diagnostic}" if diagnostic else "")
        )

    if output_path != destination:
        output_path.replace(destination)


def export_audio_clip(
    source: Path,
    destination: Path,
    *,
    start: float,
    end: float,
    offset_ms: int = 0,
    volume: float = 1.0,
    fade_in_ms: int = 0,
    fade_out_ms: int = 250,
) -> Path:
    info = probe_media(source)
    start, end = validate_interval(start, end, info.duration)
    if destination.suffix.lower() not in {".mp3", ".wav"}:
        raise MediaEditorError("Escolha MP3 ou WAV para exportar o áudio.")
    _export_audio(
        source,
        destination,
        source_start=start,
        duration=end - start,
        offset_ms=offset_ms,
        volume=volume,
        fade_in_ms=fade_in_ms,
        fade_out_ms=fade_out_ms,
    )
    return destination


def export_audio_segments(
    source: Path,
    destination_dir: Path,
    segments: list[AudioSegment],
    *,
    extension: str = ".mp3",
    volume: float = 1.0,
    fade_in_ms: int = 0,
    fade_out_ms: int = 120,
) -> list[Path]:
    if not segments:
        raise MediaEditorError("Não existem blocos de áudio para exportar.")
    suffix = extension.lower()
    if suffix not in {".mp3", ".wav"}:
        raise MediaEditorError("Escolha MP3 ou WAV para exportar os blocos.")
    destination_dir.mkdir(parents=True, exist_ok=True)
    results: list[Path] = []
    for segment in segments:
        clean_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", segment.name).strip("_")
        destination = destination_dir / f"{clean_name or 'audio'}{suffix}"
        export_audio_clip(
            source,
            destination,
            start=segment.source_start,
            end=segment.source_end,
            volume=volume,
            fade_in_ms=fade_in_ms,
            fade_out_ms=min(fade_out_ms, round(segment.duration * 500)),
        )
        results.append(destination)
    return results


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
    selected_audio = (
        audio_source
        if audio_source is not None
        else (video_source if info.has_audio else None)
    )
    audio_path = destination_dir / f"{clean_name}_audio.mp3" if selected_audio else None
    with tempfile.TemporaryDirectory(prefix="entrecenas_media_") as temp:
        frames = _extract_frames(
            video_source,
            Path(temp),
            start=start,
            duration=duration,
            fps=max(1, int(fps)),
            max_side=max(64, int(max_side)),
        )
        _save_animated_webp(frames, webp_path, fps=max(1, int(fps)), quality=quality)
        if selected_audio is not None and audio_path is not None:
            source_start = start if selected_audio == video_source else 0.0
            _export_audio(
                selected_audio,
                audio_path,
                source_start=source_start,
                duration=duration,
                offset_ms=audio_offset_ms,
                volume=audio_volume,
                fade_in_ms=audio_fade_in_ms,
                fade_out_ms=audio_fade_out_ms,
            )
    return ExportResult(webp_path, audio_path, duration, len(frames), max(1, int(fps)))


def export_synchronized_segment(
    video_source: Path,
    audio_source: Path,
    segment: AudioSegment,
    destination_dir: Path,
    basename: str,
    *,
    fps: int = 10,
    quality: int = 65,
    max_side: int = 960,
    audio_volume: float = 1.0,
    audio_fade_in_ms: int = 0,
    audio_fade_out_ms: int = 120,
) -> ExportResult:
    video_info = probe_media(video_source)
    start, end = validate_interval(
        segment.timeline_start,
        segment.timeline_end,
        video_info.duration,
    )
    if abs((end - start) - segment.duration) > 0.05:
        raise MediaEditorError(
            "O bloco ultrapassa a duração do vídeo. Mova ou apare o áudio primeiro."
        )
    clean_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", basename).strip("_") or "motion"
    webp_path = destination_dir / f"{clean_name}_motion.webp"
    audio_path = destination_dir / f"{clean_name}_audio.mp3"
    with tempfile.TemporaryDirectory(prefix="entrecenas_segment_") as temp:
        frames = _extract_frames(
            video_source,
            Path(temp),
            start=start,
            duration=segment.duration,
            fps=max(1, int(fps)),
            max_side=max(64, int(max_side)),
        )
        _save_animated_webp(
            frames,
            webp_path,
            fps=max(1, int(fps)),
            quality=quality,
        )
        _export_audio(
            audio_source,
            audio_path,
            source_start=segment.source_start,
            duration=segment.duration,
            offset_ms=0,
            volume=audio_volume,
            fade_in_ms=audio_fade_in_ms,
            fade_out_ms=audio_fade_out_ms,
        )
    return ExportResult(
        webp_path,
        audio_path,
        segment.duration,
        len(frames),
        max(1, int(fps)),
    )



def media_editor_settings_path() -> Path:
    """Arquivo persistente e local com preferências não sensíveis do editor."""

    appdata = str(os.getenv("APPDATA", "") or "").strip()
    base = Path(appdata) if appdata else Path.home() / ".entrecenas"
    if appdata:
        return base / "EntreCenas" / "media_editor_settings.json"
    return base / "media_editor_settings.json"


def load_media_editor_settings(path: Path | None = None) -> dict[str, str]:
    target = Path(path) if path is not None else media_editor_settings_path()
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    result: dict[str, str] = {}
    for key in ("last_open_dir", "last_export_dir"):
        value = str(payload.get(key, "") or "").strip()
        if value:
            result[key] = value
    return result


def save_media_editor_settings(
    settings: dict[str, str],
    path: Path | None = None,
) -> None:
    target = Path(path) if path is not None else media_editor_settings_path()
    payload = {
        key: str(settings.get(key, "") or "").strip()
        for key in ("last_open_dir", "last_export_dir")
        if str(settings.get(key, "") or "").strip()
    }
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(target)
    except OSError:
        return

__all__ = [
    "AudioSegment",
    "ExportResult",
    "MediaEditorError",
    "MediaInfo",
    "copy_image_to_clipboard",
    "create_audio_segment",
    "export_audio_clip",
    "export_audio_segments",
    "export_synchronized_clip",
    "export_synchronized_segment",
    "extract_frame_at_index",
    "extract_precision_frames",
    "extract_timeline_frames",
    "ffmpeg_executable",
    "frame_time",
    "image_dib_bytes",
    "load_media_editor_settings",
    "media_editor_settings_path",
    "move_audio_segment",
    "probe_media",
    "rename_audio_segments",
    "save_media_editor_settings",
    "split_audio_segment",
    "trim_audio_segment",
    "validate_interval",
    "waveform_peaks",
]
