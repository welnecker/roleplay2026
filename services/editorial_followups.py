from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from services.editorial_runtime_types import EditorialScript, EditorialState


_ACTIVE_SCRIPT: ContextVar[EditorialScript | None] = ContextVar(
    "active_editorial_followup_script",
    default=None,
)


def _runtime_policy(script: EditorialScript) -> dict[str, Any]:
    direct = script.raw.get("runtime_policy") or {}
    if isinstance(direct, dict) and direct:
        return direct
    legacy = script.raw.get("organic_slack") or {}
    return legacy if isinstance(legacy, dict) else {}


def _humanize_scene_location(value: str) -> str:
    words = [part for part in value.strip().split("_") if part]
    return " ".join(words).capitalize() if words else ""


def _transition_metadata(item: dict[str, Any]) -> tuple[str, str]:
    transition = item.get("transition") if isinstance(item.get("transition"), dict) else {}
    time_label = str(transition.get("time", "") or "").strip() or "Algum tempo depois"
    location_label = str(transition.get("location", "") or "").strip()
    if not location_label:
        location_label = _humanize_scene_location(str(item.get("scene_location", "") or ""))
    return time_label, location_label


def render_editorial_followup_text(followup: dict[str, Any]) -> str:
    text = str(followup.get("text", "") or "").strip()
    heading = " — ".join(
        part
        for part in (
            str(followup.get("transition_time", "") or "").strip(),
            str(followup.get("transition_location", "") or "").strip(),
        )
        if part
    )
    return f"[{heading.upper()}]\n\n{text}" if heading else text


def _declared_state_updates(script: EditorialScript, target_id: str) -> dict[str, str]:
    state_updates = _runtime_policy(script).get("state_updates") or {}
    if not isinstance(state_updates, dict):
        return {}
    rules = state_updates.get("automatic_followups") or []
    if not isinstance(rules, list):
        raise ValueError("state_updates.automatic_followups deve ser uma lista.")

    updates: dict[str, str] = {}
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        exact = str(rule.get("target_id", "") or "").strip()
        prefix = str(rule.get("target_prefix", "") or "").strip()
        matches = (exact and target_id == exact) or (prefix and target_id.startswith(prefix))
        if not matches:
            continue
        facts = rule.get("facts") or {}
        if not isinstance(facts, dict):
            raise ValueError("state_updates facts deve ser um mapa.")
        updates.update({str(key): str(value) for key, value in facts.items()})
    return updates


def prepare_editorial_followups(script: EditorialScript) -> EditorialScript:
    registered: dict[str, tuple[dict[str, Any], ...]] = {}
    for block in script.raw.get("blocks", []):
        if not isinstance(block, dict):
            continue
        for beat in block.get("beats", []):
            if not isinstance(beat, dict):
                continue
            beat_id = str(beat.get("beat_id", ""))
            followups: list[dict[str, Any]] = []
            for item in beat.get("automatic_followups", []) or []:
                if not isinstance(item, dict):
                    continue
                target_id = str(item.get("target_id", "")).strip()
                raw_text = str(item.get("text", "")).strip()
                if not target_id or not raw_text:
                    raise ValueError(f"Ponte automática inválida no beat {beat_id!r}.")
                time_label, location_label = _transition_metadata(item)
                followup: dict[str, Any] = {
                    "target_id": target_id,
                    "text": raw_text,
                    "scene_location": str(item.get("scene_location", "")).strip(),
                    "transition_time": time_label,
                    "transition_location": location_label,
                    "state_updates": _declared_state_updates(script, target_id),
                }
                followup["text"] = render_editorial_followup_text(followup)
                followups.append(followup)
            if followups:
                registered[beat_id] = tuple(followups)

    script.editorial_followups = registered
    _ACTIVE_SCRIPT.set(script)
    return script


def editorial_followups_after(target_id: str) -> tuple[dict[str, Any], ...]:
    script = _ACTIVE_SCRIPT.get()
    if script is None:
        return ()
    registered = getattr(script, "editorial_followups", {})
    if not isinstance(registered, dict):
        return ()
    return registered.get(str(target_id), ())


def state_after_editorial_followup(
    state: EditorialState,
    followup: dict[str, Any],
) -> EditorialState:
    updated = EditorialState.from_dict(state.to_dict())
    updated.node_id = str(followup["target_id"])
    updated.pending_next_beat_id = ""
    updated.interstitial_turns = 0
    updated.facts["_organic_interstitial"] = "false"
    location = str(followup.get("scene_location", ""))
    if location:
        updated.facts["_scene_location"] = location

    state_updates = followup.get("state_updates") or {}
    if not isinstance(state_updates, dict):
        raise ValueError("state_updates da ponte automática deve ser um mapa.")
    updated.facts.update({str(key): str(value) for key, value in state_updates.items()})
    return updated


__all__ = [
    "editorial_followups_after",
    "prepare_editorial_followups",
    "render_editorial_followup_text",
    "state_after_editorial_followup",
]
