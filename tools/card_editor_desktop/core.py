from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class CardEditorError(ValueError):
    pass


@dataclass(slots=True)
class CardDraft:
    title: str = ""
    subtitle: str = ""
    description: str = ""
    genres: str = ""
    chapter_label: str = ""
    cover: str = ""
    profile_name: str = ""
    profile_identity: str = ""
    profile_personality: str = ""
    profile_intention: str = ""
    price_brl: str = "9,90"
    replay_policy: str = "new_purchase"


def load_manifest(path: Path) -> dict[str, Any]:
    target = Path(path)
    if not target.is_file():
        raise CardEditorError("Manifesto não encontrado.")
    try:
        payload = yaml.safe_load(target.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise CardEditorError(f"Não foi possível ler o manifesto: {exc}") from exc
    if not isinstance(payload, dict):
        raise CardEditorError("manifest.yaml inválido.")
    if not str(payload.get("package_id", "") or "").strip():
        raise CardEditorError("manifest.yaml sem package_id.")
    return payload


def _price_to_label(price_cents: int) -> str:
    value = max(0, int(price_cents)) / 100
    return f"{value:.2f}".replace(".", ",")


def manifest_to_draft(payload: dict[str, Any]) -> CardDraft:
    card = dict(payload.get("card") or {})
    profile = dict(card.get("character_profile") or {})
    commerce = dict(payload.get("commerce") or {})
    genres = card.get("genres") or []
    if isinstance(genres, str):
        genres_text = genres
    else:
        genres_text = ", ".join(str(item) for item in genres if str(item).strip())
    return CardDraft(
        title=str(card.get("title", "") or ""),
        subtitle=str(card.get("subtitle", "") or ""),
        description=str(card.get("description", "") or ""),
        genres=genres_text,
        chapter_label=str(card.get("chapter_label", "") or ""),
        cover=str(card.get("cover", "") or ""),
        profile_name=str(profile.get("name", "") or ""),
        profile_identity=str(profile.get("identity", "") or ""),
        profile_personality=str(profile.get("personality", "") or ""),
        profile_intention=str(profile.get("intention", "") or ""),
        price_brl=_price_to_label(int(commerce.get("price_cents", 0) or 0)),
        replay_policy=str(commerce.get("replay_policy", "new_purchase") or "new_purchase"),
    )


def parse_price_brl(value: str) -> int:
    clean = str(value or "").strip().replace("R$", "").replace(" ", "")
    if not clean:
        return 0
    if "," in clean:
        clean = clean.replace(".", "").replace(",", ".")
    try:
        amount = float(clean)
    except ValueError as exc:
        raise CardEditorError("Preço inválido. Exemplo: 9,90") from exc
    cents = round(amount * 100)
    if cents < 0:
        raise CardEditorError("O preço não pode ser negativo.")
    return cents


def _genres(value: str) -> list[str]:
    items = [
        item.strip()
        for chunk in str(value or "").replace("\n", ",").split(",")
        for item in [chunk]
        if item.strip()
    ]
    return items


def apply_card_draft(
    payload: dict[str, Any],
    draft: CardDraft,
) -> dict[str, Any]:
    if not draft.title.strip():
        raise CardEditorError("O título do card é obrigatório.")

    updated = deepcopy(payload)
    card = dict(updated.get("card") or {})
    profile = dict(card.get("character_profile") or {})
    commerce = dict(updated.get("commerce") or {})

    card["title"] = draft.title.strip()
    card["subtitle"] = draft.subtitle.strip()
    card["description"] = draft.description.strip()
    card["genres"] = _genres(draft.genres)
    card["chapter_label"] = draft.chapter_label.strip()
    card["cover"] = draft.cover.strip()
    profile["name"] = draft.profile_name.strip()
    profile["identity"] = draft.profile_identity.strip()
    profile["personality"] = draft.profile_personality.strip()
    profile["intention"] = draft.profile_intention.strip()
    card["character_profile"] = profile

    # O card comercial permanece pago. A abertura gratuita ocorre até [PAGAMENTO].
    commerce["access"] = "paid"
    commerce["price_cents"] = parse_price_brl(draft.price_brl)
    commerce["currency"] = str(commerce.get("currency", "BRL") or "BRL")
    commerce["replay_policy"] = (
        "reuse_access" if draft.replay_policy == "reuse_access" else "new_purchase"
    )

    updated["card"] = card
    updated["commerce"] = commerce
    return updated


def save_manifest(path: Path, payload: dict[str, Any]) -> None:
    target = Path(path)
    try:
        target.write_text(
            yaml.safe_dump(
                payload,
                allow_unicode=True,
                sort_keys=False,
                default_flow_style=False,
            ),
            encoding="utf-8",
        )
    except OSError as exc:
        raise CardEditorError(f"Não foi possível salvar o manifesto: {exc}") from exc


def relative_cover_path(manifest_path: Path, cover_path: Path) -> str:
    manifest_dir = Path(manifest_path).resolve().parent
    cover = Path(cover_path).resolve()
    try:
        return cover.relative_to(manifest_dir).as_posix()
    except ValueError:
        return str(cover)
