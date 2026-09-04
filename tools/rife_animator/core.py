from __future__ import annotations

import math
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from PIL import Image, ImageOps


DEFAULT_FFMPEG = Path(
    r"C:\Users\welne\miniconda3\envs\wangp\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
)
SUPPORTED_IMAGES = {".jpg", ".jpeg", ".png", ".webp"}
Progress = Callable[[str], None]


class AnimatorError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RenderSettings:
    duration_seconds: float = 12.0
    cycle_seconds: float = 2.0
    fps: int = 24
    mode: str = "loop"
    crf: int = 19

    def validate(self) -> None:
        if self.duration_seconds < 1:
            raise AnimatorError("A duração final deve ter ao menos 1 segundo.")
        if self.cycle_seconds <= 0 or self.cycle_seconds > self.duration_seconds:
            raise AnimatorError("A duração do ciclo deve ser positiva e não superar o vídeo.")
        if self.fps not in {24, 25, 30, 48, 60}:
            raise AnimatorError("FPS inválido.")
        if self.mode not in {"loop", "pingpong"}:
            raise AnimatorError("Modo de ciclo inválido.")
        if not 14 <= self.crf <= 30:
            raise AnimatorError("CRF deve ficar entre 14 e 30.")


def validate_images(paths: Sequence[Path]) -> list[Path]:
    images = [Path(path) for path in paths]
    if not 2 <= len(images) <= 12:
        raise AnimatorError("Selecione entre 2 e 12 imagens.")
    missing = [str(path) for path in images if not path.is_file()]
    if missing:
        raise AnimatorError(f"Imagem não encontrada: {missing[0]}")
    invalid = [path.name for path in images if path.suffix.lower() not in SUPPORTED_IMAGES]
    if invalid:
        raise AnimatorError(f"Formato não suportado: {invalid[0]}")
    return images


def cycle_sequence(paths: Sequence[Path], mode: str) -> list[Path]:
    images = validate_images(paths)
    if mode == "loop":
        return [*images, images[0]]
    if mode == "pingpong":
        return [*images, *images[-2::-1]]
    raise AnimatorError("Modo de ciclo inválido.")


def _even(value: int) -> int:
    return value if value % 2 == 0 else value - 1


def prepare_keyframes(paths: Sequence[Path], mode: str, destination: Path) -> list[Path]:
    sequence = cycle_sequence(paths, mode)
    destination.mkdir(parents=True, exist_ok=True)
    with Image.open(sequence[0]) as reference:
        target_size = (_even(reference.width), _even(reference.height))
    if min(target_size) <= 0:
        raise AnimatorError("As dimensões das imagens são inválidas.")

    written: list[Path] = []
    for index, source in enumerate(sequence):
        with Image.open(source) as image:
            frame = ImageOps.exif_transpose(image).convert("RGB")
            if frame.size != target_size:
                frame = ImageOps.fit(frame, target_size, method=Image.Resampling.LANCZOS)
            output = destination / f"{index:08d}.png"
            frame.save(output, "PNG", optimize=False)
            written.append(output)
    return written


def _run(command: list[str], *, progress: Progress, cwd: Path | None = None) -> None:
    progress("Executando: " + " ".join(f'"{part}"' if " " in part else part for part in command))
    completed = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
        cwd=str(cwd) if cwd else None,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if completed.returncode:
        detail = (completed.stdout or "").strip()[-3000:]
        raise AnimatorError(detail or f"Processo terminou com código {completed.returncode}.")


def _require_file(path: Path, label: str) -> Path:
    resolved = Path(path).expanduser()
    if not resolved.is_file():
        raise AnimatorError(f"{label} não encontrado: {resolved}")
    return resolved


def render_with_vulkan(
    images: Sequence[Path],
    *,
    rife_executable: Path,
    ffmpeg: Path,
    output: Path,
    settings: RenderSettings,
    model: str = "rife-v4.6",
    progress: Progress = lambda _message: None,
) -> Path:
    settings.validate()
    validate_images(images)
    rife = _require_file(rife_executable, "RIFE Vulkan")
    encoder = _require_file(ffmpeg, "FFmpeg")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="entrecenas-rife-") as raw_temp:
        temp = Path(raw_temp)
        inputs = temp / "keyframes"
        interpolated = temp / "interpolated"
        progress("Preparando imagens...")
        prepared = prepare_keyframes(images, settings.mode, inputs)
        interpolated.mkdir()
        target_frames = max(len(prepared), round(settings.cycle_seconds * settings.fps) + 1)
        progress("Interpolando o ciclo com RIFE...")
        _run(
            [
                str(rife), "-i", str(inputs), "-o", str(interpolated),
                "-n", str(target_frames), "-m", model,
            ],
            progress=progress,
        )
        progress("Montando o MP4 final...")
        _run(
            [
                str(encoder), "-y", "-stream_loop", "-1",
                "-framerate", str(settings.fps), "-i", str(interpolated / "%08d.png"),
                "-t", f"{settings.duration_seconds:.3f}", "-an",
                "-c:v", "libx264", "-preset", "medium", "-crf", str(settings.crf),
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output),
            ],
            progress=progress,
        )
    progress(f"Concluído: {output}")
    return output


def render_with_practical_rife(
    images: Sequence[Path],
    *,
    python_executable: Path,
    practical_rife_dir: Path,
    model_dir: Path,
    ffmpeg: Path,
    output: Path,
    settings: RenderSettings,
    progress: Progress = lambda _message: None,
) -> Path:
    settings.validate()
    validate_images(images)
    python = _require_file(python_executable, "Python do Practical-RIFE")
    script = _require_file(Path(practical_rife_dir) / "inference_video.py", "inference_video.py")
    _require_file(ffmpeg, "FFmpeg")
    if not Path(model_dir).is_dir():
        raise AnimatorError(f"Modelo RIFE não encontrado: {model_dir}")

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="entrecenas-practical-rife-") as raw_temp:
        temp = Path(raw_temp)
        inputs = temp / "keyframes"
        cycle_video = temp / "cycle.mp4"
        prepared = prepare_keyframes(images, settings.mode, inputs)
        intervals = max(1, len(prepared) - 1)
        source_fps = intervals / settings.cycle_seconds
        multiplier = max(2, math.ceil(settings.fps / source_fps))
        generated_frames = intervals * multiplier + 1
        generated_seconds = generated_frames / settings.fps
        speed_ratio = settings.cycle_seconds / generated_seconds
        progress("Interpolando o ciclo com Practical-RIFE...")
        _run(
            [
                str(python), str(script), "--img", str(inputs),
                "--output", str(cycle_video), "--model", str(model_dir),
                "--multi", str(multiplier), "--fps", str(settings.fps),
            ],
            progress=progress,
            cwd=Path(practical_rife_dir),
        )
        progress("Ajustando ciclo e montando o MP4 final...")
        _run(
            [
                str(ffmpeg), "-y", "-stream_loop", "-1", "-i", str(cycle_video),
                "-t", f"{settings.duration_seconds:.3f}", "-an",
                "-vf", f"setpts={speed_ratio:.8f}*PTS",
                "-r", str(settings.fps), "-c:v", "libx264", "-preset", "medium",
                "-crf", str(settings.crf), "-pix_fmt", "yuv420p",
                "-movflags", "+faststart", str(output),
            ],
            progress=progress,
        )
    progress(f"Concluído: {output}")
    return output
