from __future__ import annotations

import argparse
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from PIL import Image


DEFAULT_QUALITY = 98
DEFAULT_MAX_BYTES = 500 * 1024


def optimize_scene_images(
    scene_dir: Path,
    *,
    quality: int = DEFAULT_QUALITY,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> list[Path]:
    """Cria WebPs de alta qualidade e preserva os arquivos-fonte."""

    root = Path(scene_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"Diretório de cenas não encontrado: {root}")

    generated: list[Path] = []
    sources = sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.casefold() in {".png", ".jpg", ".jpeg"}
    )
    for source in sources:
        target = source.with_suffix(".webp")
        with NamedTemporaryFile(
            dir=target.parent,
            prefix=f".{target.stem}-",
            suffix=".webp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
        try:
            with Image.open(source) as image:
                source_size = image.size
                converted = image.convert("RGBA" if "A" in image.getbands() else "RGB")
                converted.save(
                    temporary_path,
                    "WEBP",
                    quality=quality,
                    method=6,
                    lossless=False,
                    exact=True,
                )
            with Image.open(temporary_path) as optimized:
                if optimized.size != source_size:
                    raise RuntimeError(f"Dimensões alteradas em {target}")
                optimized.verify()
            if temporary_path.stat().st_size > max_bytes:
                raise RuntimeError(
                    f"Imagem otimizada excede {max_bytes // 1024} KB: "
                    f"{target} ({temporary_path.stat().st_size // 1024} KB)"
                )
            os.replace(temporary_path, target)
        finally:
            temporary_path.unlink(missing_ok=True)
        generated.append(target)
    return generated


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Converte imagens de cenas para WebP sem apagar os originais."
    )
    parser.add_argument("scene_dir", type=Path)
    parser.add_argument("--quality", type=int, default=DEFAULT_QUALITY)
    parser.add_argument("--max-kb", type=int, default=DEFAULT_MAX_BYTES // 1024)
    args = parser.parse_args()

    generated = optimize_scene_images(
        args.scene_dir,
        quality=args.quality,
        max_bytes=args.max_kb * 1024,
    )
    total = sum(path.stat().st_size for path in generated)
    print(
        f"{len(generated)} imagens WebP geradas; "
        f"total={total / 1024 / 1024:.1f} MB"
    )


if __name__ == "__main__":
    main()
