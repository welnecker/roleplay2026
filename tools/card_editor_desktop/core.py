from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import re
import shutil
from typing import Any

import yaml


class CardEditorError(ValueError):
    pass


@dataclass(slots=True)
class NewCardSpec:
    package_id: str
    version: str = "1.0.0"
    author_id: str = "welnecker"
    author_name: str = "Welnecker"


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



_PACKAGE_ID_RE = re.compile(r"^[a-z0-9._-]+$")


def validate_package_id(value: str) -> str:
    clean = str(value or "").strip().lower()
    if len(clean) < 3 or not _PACKAGE_ID_RE.fullmatch(clean):
        raise CardEditorError(
            "package_id inválido. Use letras minúsculas, números, ponto, hífen ou _."
        )
    return clean


def package_folder_name(package_id: str) -> str:
    clean = validate_package_id(package_id)
    tail = clean.rsplit(".", maxsplit=1)[-1]
    return tail or clean.replace(".", "_")


def new_manifest(spec: NewCardSpec) -> dict[str, Any]:
    package_id = validate_package_id(spec.package_id)
    version = str(spec.version or "").strip()
    if not version:
        raise CardEditorError("A versão do card é obrigatória.")
    author_name = str(spec.author_name or "").strip()
    if not author_name:
        raise CardEditorError("O nome do autor é obrigatório.")
    return {
        "format_version": 2,
        "package_id": package_id,
        "version": version,
        "author": {
            "id": str(spec.author_id or "").strip() or "welnecker",
            "name": author_name,
        },
        "entrypoint": "story.yaml",
        "runtime": {
            "kind": "editorial",
            "editorial": {"source": "content/editorial.yaml"},
        },
        "card": {
            "title": "Novo card",
            "subtitle": "",
            "description": "",
            "genres": [],
            "chapter_label": "História completa",
            "cover": "",
            "character_profile": {
                "name": "",
                "identity": "",
                "personality": "",
                "intention": "",
            },
        },
        "cast_customization": {
            "enabled": False,
            "members": [],
        },
        "commerce": {
            "access": "paid",
            "price_cents": 990,
            "currency": "BRL",
            "replay_policy": "new_purchase",
        },
    }


def _starter_story_yaml(package_id: str, title: str) -> str:
    story_id = package_folder_name(package_id)
    safe_title = str(title or story_id).strip() or story_id
    payload = {
        "story_id": story_id,
        "title": safe_title,
        "entry_route": "abertura",
        "routes": [
            {
                "id": "abertura",
                "beats": [
                    {
                        "id": "abertura_001",
                        "movements": [
                            {
                                "order": 1,
                                "content": (
                                    "A história será conduzida pelo roteiro editorial "
                                    "publicado para este card."
                                ),
                            }
                        ],
                    }
                ],
            }
        ],
    }
    return yaml.safe_dump(
        payload,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )


def _starter_editorial_yaml(package_id: str, version: str, title: str) -> str:
    payload = {
        "format_version": 3,
        "package_id": validate_package_id(package_id),
        "script_version": str(version or "1.0.0"),
        "title": str(title or "Novo card"),
        "introduction": (
            "Conteúdo editorial inicial. Substitua pelo roteiro publicado "
            "antes de disponibilizar este card em produção."
        ),
        "blocks": [
            {
                "block_id": "abertura_fallback",
                "order": 1,
                "title": "Abertura provisória",
                "entry_beat_id": "abertura_001",
                "beats": [
                    {
                        "beat_id": "abertura_001",
                        "order": 1,
                        "required_movement": "Abertura provisória do card.",
                        "canonical_line": "Esta história está sendo preparada.",
                        "allowed_transitions": {
                            "engaged": "abertura_fim",
                            "minimal": "abertura_fim",
                            "dismissive": "abertura_fim",
                            "nonsense": "abertura_fim",
                            "mocking": "abertura_fim",
                            "hostile": "abertura_fim",
                        },
                    },
                    {
                        "beat_id": "abertura_fim",
                        "order": 2,
                        "type": "ending",
                        "canonical_line": "Em breve.",
                        "ending": {
                            "run_status": "completed",
                            "ending_code": "placeholder_complete",
                        },
                    },
                ],
            }
        ],
        "memories": [],
    }
    return yaml.safe_dump(
        payload,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )


def create_card_package(parent_dir: Path, spec: NewCardSpec) -> tuple[Path, dict[str, Any]]:
    payload = new_manifest(spec)
    package_dir = Path(parent_dir) / package_folder_name(payload["package_id"])
    if package_dir.exists() and any(package_dir.iterdir()):
        raise CardEditorError(
            f"A pasta do card já existe e não está vazia: {package_dir}"
        )

    try:
        (package_dir / "assets" / "capas").mkdir(parents=True, exist_ok=True)
        (package_dir / "content").mkdir(parents=True, exist_ok=True)
        manifest_path = package_dir / "manifest.yaml"
        save_manifest(manifest_path, payload)
        (package_dir / "story.yaml").write_text(
            _starter_story_yaml(payload["package_id"], payload["card"]["title"]),
            encoding="utf-8",
        )
        (package_dir / "content" / "editorial.yaml").write_text(
            _starter_editorial_yaml(
                payload["package_id"],
                payload["version"],
                payload["card"]["title"],
            ),
            encoding="utf-8",
        )
    except OSError as exc:
        raise CardEditorError(f"Não foi possível criar a estrutura do card: {exc}") from exc
    return manifest_path, payload


def import_cover_into_package(manifest_path: Path, source_path: Path) -> str:
    manifest = Path(manifest_path).resolve()
    source = Path(source_path).resolve()
    if not source.is_file():
        raise CardEditorError("Arquivo de capa não encontrado.")
    suffix = source.suffix.lower()
    if suffix not in {".webp", ".png", ".jpg", ".jpeg"}:
        raise CardEditorError("A capa deve ser WEBP, PNG, JPG ou JPEG.")
    target_dir = manifest.parent / "assets" / "capas"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"capa{suffix}"
    try:
        if source != target.resolve():
            shutil.copy2(source, target)
    except OSError as exc:
        raise CardEditorError(f"Não foi possível copiar a capa: {exc}") from exc
    return target.relative_to(manifest.parent).as_posix()


def sync_starter_files(manifest_path: Path, payload: dict[str, Any]) -> None:
    root = Path(manifest_path).resolve().parent
    story_path = root / "story.yaml"
    editorial_path = root / "content" / "editorial.yaml"
    try:
        if story_path.is_file():
            story = yaml.safe_load(story_path.read_text(encoding="utf-8"))
            if isinstance(story, dict):
                story["title"] = str(payload.get("card", {}).get("title", "") or "")
                story_path.write_text(
                    yaml.safe_dump(story, allow_unicode=True, sort_keys=False),
                    encoding="utf-8",
                )
        if editorial_path.is_file():
            editorial = yaml.safe_load(editorial_path.read_text(encoding="utf-8"))
            if (
                isinstance(editorial, dict)
                and editorial.get("blocks")
                and str(editorial.get("introduction", "")).startswith("Conteúdo editorial inicial.")
            ):
                editorial["title"] = str(payload.get("card", {}).get("title", "") or "")
                editorial["script_version"] = str(payload.get("version", "") or "1.0.0")
                editorial_path.write_text(
                    yaml.safe_dump(editorial, allow_unicode=True, sort_keys=False),
                    encoding="utf-8",
                )
    except (OSError, yaml.YAMLError):
        # O manifesto é a fonte do configurador. Arquivos editoriais já customizados
        # nunca devem impedir a edição do card nem ser sobrescritos agressivamente.
        return
