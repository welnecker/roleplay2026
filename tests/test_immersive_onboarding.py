from __future__ import annotations

from services.immersive_onboarding import (
    PRIVACY_NOTICE,
    build_immersive_context,
    clear_immersive_profile,
    profile_key,
)


def test_privacy_notice_is_explicit() -> None:
    assert "não serão salvas nem armazenadas" in PRIVACY_NOTICE
    assert "não estarão disponíveis quando retornar" in PRIVACY_NOTICE
    assert "opcionais" in PRIVACY_NOTICE


def test_profile_is_session_scoped_and_removable() -> None:
    key = profile_key("user-1", "story-1")
    state = {key: {"completed": True}, "unrelated": 1}
    clear_immersive_profile(state, user_id="user-1", package_id="story-1")
    assert key not in state
    assert state["unrelated"] == 1


def test_private_context_requires_completed_profile() -> None:
    assert build_immersive_context({"preferred_name": "Alex"}) == ""
    context = build_immersive_context(
        {
            "completed": True,
            "preferred_name": "Alex",
            "gender": "Homem",
            "appearance": "cabelo curto",
            "intimate": "descrição privada",
        }
    )
    assert "Alex" in context
    assert "cabelo curto" in context
    assert "descrição privada" in context
