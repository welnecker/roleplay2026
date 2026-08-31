from __future__ import annotations

from services.immersive_onboarding import (
    PHOTO_ONBOARDING_ENABLED,
    identity_completion_state,
)


def test_photo_onboarding_is_disabled_by_default() -> None:
    assert PHOTO_ONBOARDING_ENABLED is False
    assert identity_completion_state() == {"stage": 3, "completed": True}


def test_photo_flow_can_be_reenabled_without_rebuilding_it() -> None:
    assert identity_completion_state(photos_enabled=True) == {
        "stage": 1,
        "completed": False,
    }
