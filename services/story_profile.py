from __future__ import annotations

import unicodedata
from typing import Any, Mapping

from services.editorial_runtime_types import EditorialScript


_STORY_GENDER_TAGS = {
    "Como homem": "HOMEM",
    "Como mulher": "MULHER",
    "De forma neutra": "NEUTRA",
}
_BODY_ROUTE_TAGS = {
    "Corpo masculino": "CORPO_MASCULINO",
    "Corpo feminino": "CORPO_FEMININO",
    "Corpo intersexo": "CORPO_INTERSEXO",
}


def profile_tags(profile: Mapping[str, Any] | None) -> tuple[str, ...]:
    if not profile:
        return ()
    story_gender = str(
        profile.get("story_gender") or profile.get("gender") or ""
    ).strip()
    body_route = str(profile.get("body_route", "") or "").strip()
    return tuple(
        tag
        for tag in (
            _STORY_GENDER_TAGS.get(story_gender, ""),
            _BODY_ROUTE_TAGS.get(body_route, ""),
        )
        if tag
    )


def _plain(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(
        char for char in normalized if not unicodedata.combining(char)
    ).casefold().strip()


def _gendered_name_values(
    profile: Mapping[str, Any] | None,
) -> tuple[str, str, str]:
    source = profile or {}
    name = str(
        source.get("preferred_name")
        or source.get("name")
        or source.get("user_name")
        or source.get("nome")
        or ""
    ).strip()
    gender = _plain(source.get("story_gender") or source.get("gender"))
    if gender in {"como homem", "homem", "masculino", "male"}:
        return name, f"o {name}".strip(), "ele"
    if gender in {"como mulher", "mulher", "feminino", "female"}:
        return name, f"a {name}".strip(), "ela"
    return name, name, name


def resolve_profile_text(text: str, profile: Mapping[str, Any] | None) -> str:
    """Resolve os marcadores autorais de nome e tratamento do protagonista."""

    name, article_name, pronoun = _gendered_name_values(profile)
    rendered = str(text or "")
    # Do marcador mais específico para o mais simples, mantendo o roteiro fonte intacto.
    return (
        rendered.replace("{{**nome}}", pronoun)
        .replace("{{*nome}}", article_name)
        .replace("{{nome}}", name)
    )


def _selected_variant(variants: Any, tags: tuple[str, ...]) -> str:
    if not isinstance(variants, Mapping):
        return ""
    ordered_tags = tuple(tag for tag in tags if tag.startswith("CORPO_")) + tuple(
        tag for tag in tags if not tag.startswith("CORPO_")
    )
    for tag in ordered_tags:
        value = str(variants.get(tag, "") or "").strip()
        if value:
            return value
    return ""


def _delivery_text(delivery: Mapping[str, Any], profile: Mapping[str, Any]) -> str:
    tags = profile_tags(profile)
    thought = _selected_variant(delivery.get("thought_variants"), tags) or str(
        delivery.get("thought", "") or ""
    ).strip()
    speech = _selected_variant(delivery.get("speech_variants"), tags) or str(
        delivery.get("speech", "") or ""
    ).strip()
    transition = str(delivery.get("transition", "") or "").strip()
    visible: list[str] = []
    if transition:
        visible.append(f"[{transition.upper()}]")
    if thought:
        visible.append(f"[PENSAMENTO]\n{thought}\n[/PENSAMENTO]")
    if speech:
        visible.append(speech)
    return resolve_profile_text("\n\n".join(visible), profile)


def personalize_editorial_script(
    script: EditorialScript,
    profile: Mapping[str, Any],
) -> EditorialScript:
    """Cria uma visão por usuário sem alterar o roteiro compartilhado em cache."""

    raw = dict(script.raw)
    scene = dict(raw.get("scene") or {})
    scene["introduction"] = resolve_profile_text(
        str(scene.get("introduction", "") or ""), profile
    )
    scene["beats"] = [
        {
            **dict(beat),
            "units": [dict(unit) if isinstance(unit, Mapping) else unit for unit in beat.get("units", []) or []],
            "profile_delivery": dict(beat.get("profile_delivery") or {}),
        }
        if isinstance(beat, Mapping)
        else beat
        for beat in scene.get("beats", []) or []
    ]
    scene["endings"] = [
        {
            **dict(ending),
            "visible_delivery": dict(ending.get("visible_delivery") or {}),
        }
        if isinstance(ending, Mapping)
        else ending
        for ending in scene.get("endings", []) or []
    ]
    raw["scene"] = scene
    for beat in scene.get("beats", []) or []:
        if not isinstance(beat, dict):
            continue
        delivery = beat.get("profile_delivery")
        for unit in beat.get("units", []) or []:
            if not isinstance(unit, dict):
                continue
            if unit.get("kind") == "dialogue":
                anchor = (
                    _delivery_text(delivery, profile)
                    if isinstance(delivery, Mapping)
                    else resolve_profile_text(
                        str(unit.get("anchor") or unit.get("text") or ""), profile
                    )
                )
                unit["anchor"] = anchor
                if "text" in unit:
                    unit["text"] = anchor
                unit["instruction"] = resolve_profile_text(
                    str(unit.get("instruction", "") or ""), profile
                )
        if isinstance(delivery, Mapping):
            tags = profile_tags(profile)
            selected_thought = _selected_variant(
                delivery.get("thought_variants"), tags
            ) or str(delivery.get("thought", "") or "").strip()
            selected_speech = _selected_variant(
                delivery.get("speech_variants"), tags
            ) or str(delivery.get("speech", "") or "").strip()
            beat["authored_thought"] = resolve_profile_text(selected_thought, profile)
            beat["exact_speech"] = (
                resolve_profile_text(selected_speech, profile)
                if bool(delivery.get("speech_exact", False))
                else ""
            )
        beat["authored_transition"] = resolve_profile_text(
            str(beat.get("authored_transition", "") or ""), profile
        )
        beat["objective"] = resolve_profile_text(
            str(beat.get("objective", "") or ""), profile
        )
        if "required_movement" in beat:
            beat["required_movement"] = resolve_profile_text(
                str(beat.get("required_movement", "") or ""), profile
            )
    for ending in scene.get("endings", []) or []:
        if not isinstance(ending, dict):
            continue
        delivery = ending.get("visible_delivery")
        if isinstance(delivery, dict):
            delivery["text"] = resolve_profile_text(
                str(delivery.get("text", "") or ""), profile
            )
    return EditorialScript(raw)


def opening_with_required_name(text: str, profile: Mapping[str, Any]) -> str:
    rendered = resolve_profile_text(text, profile)
    name = str(profile.get("preferred_name", "") or "").strip()
    if not name or name.casefold() in rendered.casefold():
        return rendered
    greeting = f"Oi, {name}... que prazer ter você aqui."
    thought_end = rendered.find("[/PENSAMENTO]")
    if thought_end >= 0:
        insert_at = thought_end + len("[/PENSAMENTO]")
        return rendered[:insert_at] + "\n\n" + greeting + " " + rendered[insert_at:].lstrip()
    return f"{greeting} {rendered}".strip()


__all__ = [
    "opening_with_required_name",
    "personalize_editorial_script",
    "profile_tags",
    "resolve_profile_text",
]
