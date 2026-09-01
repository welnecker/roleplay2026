from __future__ import annotations

import json
from contextlib import nullcontext
from types import SimpleNamespace

from flet_api import story_end_card
from flet_api.runs import FletRunService
from roleplay.models import StoryState
from services import editorial_content, novel_frame_patch
from services.runtime_persistence import RuntimePersistenceContext


def _document() -> dict[str, object]:
    previous = {
        "beat_id": "capitulo1_024",
        "order": 24,
        "required_movement": novel_frame_patch._FRAME_PREFIX
        + json.dumps(
            {
                "frame_id": "capitulo1_024",
                "description": "Último quadro narrativo",
                "entries": [{"kind": "fala", "actor": "mary", "instruction": "Fim"}],
                "is_ending": False,
            }
        ),
        "next_beat_id": "",
        "allowed_transitions": {},
    }
    return {
        "character": {"character_id": "mary", "name": "Mary"},
        "blocks": [{"block_id": "novel_v2_frames", "beats": [previous]}],
    }


def test_story_end_text_becomes_own_terminal_frame_with_image() -> None:
    document = _document()
    row = {
        "line_id": "capitulo1_fim_historia",
        "instruction": "[FIM_HISTORIA] Gostou dessa aventura, {{nome}}? Tchauzinho...",
        "image_id": "mary99.webp",
        "status": "active",
        "order": 1170,
    }

    result = story_end_card._append_terminal_card(
        document,
        row=row,
        body="Gostou dessa aventura, {{nome}}? Tchauzinho...",
    )

    beats = result["blocks"][0]["beats"]
    assert beats[0]["next_beat_id"] == "capitulo1_fim_historia"
    assert beats[0]["allowed_transitions"] == {"engaged": "capitulo1_fim_historia"}
    terminal = beats[-1]
    payload = json.loads(
        terminal["required_movement"][len(novel_frame_patch._FRAME_PREFIX) :]
    )
    assert terminal["beat_id"] == "capitulo1_fim_historia"
    assert payload["is_ending"] is True
    assert payload["terminal_kind"] == "story_end"
    assert payload["deterministic"] is True
    assert payload["image_id"] == "mary99.webp"
    assert payload["entries"][0]["image_id"] == "mary99.webp"
    assert payload["entries"][0]["delivery"] == "exata"
    assert payload["entries"][0]["instruction"].startswith("Gostou dessa aventura")


def test_terminal_content_substitutes_name_without_model_rewrite() -> None:
    frame = {
        "frame_id": "capitulo1_fim_historia",
        "entries": [
            {
                "actor": "mary",
                "visible_name": "Mary",
                "instruction": "Gostou dessa aventura, {{nome}}? Aposto que sim. Tchauzinho...",
            }
        ],
    }

    content = story_end_card._terminal_content(frame, protagonist="Janio")

    assert "[QUADRO capitulo1_fim_historia]" in content
    assert "[FALA mary|Mary]" in content
    assert "Gostou dessa aventura, Janio? Aposto que sim. Tchauzinho..." in content
    assert "{{nome}}" not in content


def test_installed_terminal_generate_bypasses_original_model_path(monkeypatch) -> None:
    cls = FletRunService
    saved_generate = cls._generate
    saved_installed = story_end_card._INSTALLED
    saved_mark = editorial_content._mark_explicit_story_end
    model_calls: list[str] = []

    def model_path(self, **kwargs):
        model_calls.append("called")
        raise AssertionError("O caminho do modelo não pode ser usado no [FIM_HISTORIA].")

    try:
        cls._generate = model_path  # type: ignore[method-assign]
        story_end_card._INSTALLED = False
        story_end_card.install()

        payload = {
            "frame_id": "capitulo1_fim_historia",
            "description": "",
            "entries": [
                {
                    "kind": "fala",
                    "actor": "mary",
                    "visible_name": "Mary",
                    "instruction": "Até a próxima, {{nome}}!",
                    "line_id": "capitulo1_fim_historia",
                    "delivery": "exata",
                    "image_id": "mary99.webp",
                }
            ],
            "image_id": "mary99.webp",
            "is_ending": True,
            "terminal_kind": "story_end",
            "deterministic": True,
        }
        movement = SimpleNamespace(
            instruction=novel_frame_patch._FRAME_PREFIX + json.dumps(payload),
            block_id="novel_v2_frames",
            is_ending=True,
        )
        monkeypatch.setattr(story_end_card, "movement_from_script", lambda script, target_id: movement)

        persisted: list[str] = []

        def persist(*args, **kwargs):
            persisted.append(str(kwargs["assistant_text"]))
            return kwargs["context"]

        monkeypatch.setattr(story_end_card, "persist_assistant_message", persist)
        monkeypatch.setattr(story_end_card, "persistent_profile_payload", lambda profile: {})
        monkeypatch.setattr(story_end_card, "recover_persistent_profile", lambda messages: None)

        run = SimpleNamespace(
            run_id="run_1",
            user_id="user_1",
            package_id="story_1",
            current_block_id="novel_v2_frames",
            current_beat_id="capitulo1_024",
            state_version=1,
        )
        context = RuntimePersistenceContext(
            package_id="story_1",
            package_version="200",
            run=run,
        )
        service = object.__new__(FletRunService)
        service.repository = SimpleNamespace()
        service.secrets = {}
        service._finish_loaded_run = lambda **kwargs: kwargs["context"]  # type: ignore[method-assign]
        service._lock = lambda *args, **kwargs: nullcontext()  # type: ignore[method-assign]

        state = StoryState(step_index=24, consumed_orders=list(range(1, 25)), finished=False)
        messages: list[dict[str, object]] = []
        package = SimpleNamespace(manifest=SimpleNamespace(package_id="story_1"))
        user = SimpleNamespace(user_id="user_1", display_name="Janio")

        _context, result_state, result_messages = cls._generate(  # type: ignore[misc]
            service,
            package=package,
            script=object(),
            user=user,
            context=context,
            state=state,
            messages=messages,
            profile={"preferred_name": "Janio"},
            target_id="capitulo1_fim_historia",
        )

        assert model_calls == []
        assert len(persisted) == 1
        assert "Até a próxima, Janio!" in persisted[0]
        assert result_state.finished is True
        assert result_messages[-1]["story_end_card"] is True
    finally:
        cls._generate = saved_generate
        story_end_card._INSTALLED = saved_installed
        editorial_content._mark_explicit_story_end = saved_mark
