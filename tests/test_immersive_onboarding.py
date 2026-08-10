from __future__ import annotations

from services.immersive_onboarding import (
    PRIVACY_NOTICE,
    _analyze_once,
    build_immersive_context,
    clear_immersive_profile,
    persistent_profile_payload,
    photo_acknowledgement,
    profile_key,
    recover_persistent_profile,
    restore_profile_for_run,
)


def test_privacy_notice_is_explicit() -> None:
    assert "arquivos das fotos não serão salvos nem armazenados" in PRIVACY_NOTICE
    assert "descrição extraída será guardada como memória" in PRIVACY_NOTICE
    assert "não passa para uma nova execução paga" in PRIVACY_NOTICE
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


class _Upload:
    def getvalue(self) -> bytes:
        return b"same-private-file"


def test_same_uploaded_file_is_analyzed_only_once(monkeypatch) -> None:
    calls: list[str] = []

    def fake_analyze(*args, **kwargs) -> str:
        calls.append(str(kwargs["kind"]))
        return "descrição"

    monkeypatch.setattr("services.immersive_onboarding._analyze", fake_analyze)
    profile: dict[str, object] = {"gender": "Homem"}

    first, first_error = _analyze_once(
        profile, _Upload(), kind="appearance", api_key="key", model="model"
    )
    second, second_error = _analyze_once(
        profile, _Upload(), kind="appearance", api_key="key", model="model"
    )

    assert first == "descrição"
    assert first_error == ""
    assert second == ""
    assert second_error == ""
    assert calls == ["appearance"]


def test_acknowledgement_praises_and_explains_immersion() -> None:
    general = photo_acknowledgement("Camilly")
    intimate = photo_acknowledgement("Camilly", intimate=True)

    assert "gostei do que vi" in general.lower()
    assert "Camilly" in general
    assert "mais pessoal e imersiva" in general
    assert "gostei muito do que vi" in intimate.lower()
    assert "mais íntima e imersiva" in intimate


def test_description_is_persisted_without_photo_bytes_and_recovered() -> None:
    payload = persistent_profile_payload(
        {
            "completed": True,
            "preferred_name": "Jânio",
            "gender": "Homem",
            "appearance": "cabelos curtos e barba",
            "intimate": "descrição íntima",
            "appearance_attempt_digest": "hash-que-nao-pode-persistir",
        }
    )
    assert payload == {
        "preferred_name": "Jânio",
        "gender": "Homem",
        "appearance": "cabelos curtos e barba",
        "intimate": "descrição íntima",
    }

    recovered = recover_persistent_profile(
        [{"role": "assistant", "immersive_profile": payload}]
    )
    assert recovered is not None
    assert recovered["completed"] is True
    assert recovered["appearance"] == "cabelos curtos e barba"


def test_active_run_does_not_show_onboarding_again() -> None:
    state: dict[str, object] = {}
    restore_profile_for_run(
        state,
        user_id="user-1",
        package_id="story-1",
        messages=[{"role": "assistant", "content": "história em andamento"}],
    )
    profile = state[profile_key("user-1", "story-1")]
    assert isinstance(profile, dict)
    assert profile["completed"] is True
