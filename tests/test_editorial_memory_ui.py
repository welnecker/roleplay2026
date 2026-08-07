from __future__ import annotations

from types import SimpleNamespace

from services import editorial_memory_ui as memory_ui


def test_selector_turn_is_scoped_to_authenticated_user(monkeypatch) -> None:
    package_id = "roleplay2026.casada_frustrada"
    user_a = SimpleNamespace(user_id="user-a")
    user_b = SimpleNamespace(user_id="user-b")
    state_a = SimpleNamespace(facts={"_episodic_memory_turn": "7"})
    state_b = SimpleNamespace(facts={"_episodic_memory_turn": "2"})
    session_state = {
        "authenticated_user": user_b,
        f"editorial:user-a:{package_id}:editorial_state": state_a,
        f"editorial:user-b:{package_id}:editorial_state": state_b,
    }
    monkeypatch.setattr(memory_ui.st, "session_state", session_state)

    assert memory_ui._selector_key(package_id) == (
        f"editorial_memory_requested:user-b:{package_id}:2"
    )


def test_selector_key_changes_with_authenticated_user(monkeypatch) -> None:
    package_id = "roleplay2026.casada_frustrada"
    session_state = {
        "authenticated_user": SimpleNamespace(user_id="user-a"),
        f"editorial:user-a:{package_id}:editorial_state": SimpleNamespace(
            facts={"_episodic_memory_turn": "4"}
        ),
        f"editorial:user-b:{package_id}:editorial_state": SimpleNamespace(
            facts={"_episodic_memory_turn": "9"}
        ),
    }
    monkeypatch.setattr(memory_ui.st, "session_state", session_state)

    assert memory_ui._selector_key(package_id).endswith(":user-a:" + package_id + ":4")

    session_state["authenticated_user"] = SimpleNamespace(user_id="user-b")

    assert memory_ui._selector_key(package_id).endswith(":user-b:" + package_id + ":9")
