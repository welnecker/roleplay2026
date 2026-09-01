from datetime import timedelta

from flet_api.sessions import SessionStore


def test_signed_session_survives_new_store_instance_with_same_key() -> None:
    first = SessionStore(signing_key=b"x" * 32)
    token, created = first.create(user_id="user_1")

    second = SessionStore(signing_key=b"x" * 32)
    restored = second.resolve(token)

    assert restored is not None
    assert restored.user_id == "user_1"
    assert restored.expires_at == created.expires_at


def test_signed_session_rejects_tampering_and_other_key() -> None:
    store = SessionStore(signing_key=b"x" * 32)
    token, _session = store.create(user_id="user_1")

    assert store.resolve(token + "x") is None
    assert SessionStore(signing_key=b"y" * 32).resolve(token) is None


def test_logout_revokes_token_in_current_process() -> None:
    store = SessionStore(signing_key=b"x" * 32)
    token, _session = store.create(user_id="user_1")

    assert store.resolve(token) is not None
    store.revoke(token)
    assert store.resolve(token) is None


def test_non_positive_ttl_is_rejected() -> None:
    try:
        SessionStore(ttl=timedelta(seconds=0), signing_key=b"x" * 32)
    except ValueError as exc:
        assert "positiva" in str(exc)
    else:
        raise AssertionError("TTL zero deveria ser rejeitado")
