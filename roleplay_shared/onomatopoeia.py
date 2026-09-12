from __future__ import annotations

import shlex
import unicodedata
from dataclasses import asdict, dataclass
from typing import Mapping


def _plain(value: object) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(
        character for character in normalized
        if not unicodedata.combining(character)
    ).casefold().strip()


@dataclass(frozen=True, slots=True)
class OnomatopoeiaEffect:
    kind: str = "smack"
    text: str = "SMACK!"
    x: float = 69.0
    y: float = 48.0
    delay: int = 350
    duration: int = 1200
    dx: int = 32
    dy: int = -10

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def canonical_header(self) -> str:
        x = f"{self.x:g}"
        y = f"{self.y:g}"
        return (
            f"ONOMATOPEIA {self.kind} x={x} y={y} delay={self.delay} "
            f"duracao={self.duration} dx={self.dx} dy={self.dy}"
        )


def parse_onomatopoeia_header(header: str) -> OnomatopoeiaEffect:
    try:
        parts = shlex.split(str(header or "").strip())
    except ValueError as exc:
        raise ValueError(f"Tag [ONOMATOPEIA] inválida: {exc}") from exc
    if not parts or _plain(parts[0]) != "onomatopeia":
        raise ValueError("A tag precisa começar com [ONOMATOPEIA].")
    if len(parts) < 2:
        raise ValueError("[ONOMATOPEIA] exige o tipo do efeito, por exemplo: smack.")
    kind = _plain(parts[1])
    if kind != "smack":
        raise ValueError("Neste primeiro exemplo, a única onomatopeia disponível é smack.")

    values: dict[str, str] = {}
    for token in parts[2:]:
        key, separator, value = token.partition("=")
        key = _plain(key)
        if not separator or not key or not value:
            raise ValueError(f"Parâmetro inválido em [ONOMATOPEIA]: {token!r}.")
        if key in values:
            raise ValueError(f"Parâmetro repetido em [ONOMATOPEIA]: {key}.")
        values[key] = value
    allowed = {"x", "y", "delay", "duracao", "dx", "dy"}
    unknown = sorted(set(values) - allowed)
    if unknown:
        raise ValueError("Parâmetro desconhecido em [ONOMATOPEIA]: " + ", ".join(unknown))

    try:
        effect = OnomatopoeiaEffect(
            kind=kind,
            text="SMACK!",
            x=float(values.get("x", 69)),
            y=float(values.get("y", 48)),
            delay=int(values.get("delay", 350)),
            duration=int(values.get("duracao", 1200)),
            dx=int(values.get("dx", 32)),
            dy=int(values.get("dy", -10)),
        )
    except ValueError as exc:
        raise ValueError("Os parâmetros da [ONOMATOPEIA] precisam ser numéricos.") from exc

    if not 0 <= effect.x <= 100 or not 0 <= effect.y <= 100:
        raise ValueError("x e y da [ONOMATOPEIA] precisam estar entre 0 e 100.")
    if not 0 <= effect.delay <= 5000:
        raise ValueError("delay da [ONOMATOPEIA] precisa estar entre 0 e 5000 ms.")
    if not 300 <= effect.duration <= 5000:
        raise ValueError("duracao da [ONOMATOPEIA] precisa estar entre 300 e 5000 ms.")
    if not -500 <= effect.dx <= 500 or not -500 <= effect.dy <= 500:
        raise ValueError("dx e dy da [ONOMATOPEIA] precisam estar entre -500 e 500 px.")
    return effect


def effect_from_mapping(value: Mapping[str, object]) -> OnomatopoeiaEffect:
    return OnomatopoeiaEffect(
        kind=str(value.get("kind", "smack") or "smack"),
        text=str(value.get("text", "SMACK!") or "SMACK!"),
        x=float(value.get("x", 69) or 69),
        y=float(value.get("y", 48) or 48),
        delay=int(value.get("delay", 350) or 0),
        duration=int(value.get("duration", 1200) or 1200),
        dx=int(value.get("dx", 32) or 0),
        dy=int(value.get("dy", -10) or 0),
    )


__all__ = [
    "OnomatopoeiaEffect",
    "effect_from_mapping",
    "parse_onomatopoeia_header",
]
