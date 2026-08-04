from __future__ import annotations

from services.editorial_bridge import (
    bridge_active,
    create_bridge_turn,
    release_bridge_state,
)
from services.editorial_compiler import compile_editorial_document
from services.editorial_content import load_source_document
from services.editorial_progression import prepare_editorial_script
from services.editorial_runtime import EditorialScript, EditorialState, EditorialTurn
from services.editorial_turn_finalization import finalize_editorial_turn


def _script() -> EditorialScript:
    return prepare_editorial_script(
        EditorialScript(compile_editorial_document(load_source_document()))
    )


def _turn(target_id: str) -> EditorialTurn:
    return EditorialTurn(
        engagement="engaged",
        target_id=target_id,
        visible_fallback="",
        system_prompt="",
        state=EditorialState(node_id=target_id),
    )


def _memory_writes(script: EditorialScript, beat_id: str) -> tuple[str, ...]:
    beat = script.beats.get(beat_id) or {}
    return tuple(
        str(item).strip()
        for item in beat.get("memory_writes", []) or []
        if str(item).strip()
    )


def _active_memories(state: EditorialState) -> tuple[str, ...]:
    return tuple(
        item.strip()
        for item in str(state.facts.get("_active_memory_ids", "") or "").split(",")
        if item.strip()
    )


def test_estado_de_ponte_sobrevive_serializacao_e_libera_o_mesmo_alvo() -> None:
    script = _script()
    previous = EditorialState(node_id="late_night_004")
    bridge = create_bridge_turn(
        script,
        previous,
        _turn("late_night_005"),
        "Pode falar, Mary.",
    )

    restored = EditorialState.from_dict(bridge.state.to_dict())

    assert bridge_active(restored) is True
    assert restored.node_id == "late_night_004"
    assert restored.pending_next_beat_id == "late_night_005"

    released = release_bridge_state(script, restored)

    assert bridge_active(released) is False
    assert released.pending_next_beat_id == "late_night_005"
    assert released.facts["_runtime_phase"] == "canonical"


def test_fallback_da_ponte_e_neutro_e_nao_revela_linha_futura() -> None:
    script = _script()
    previous = EditorialState(node_id="late_night_004")
    target_id = "late_night_005"
    future = script.beats[target_id]
    future_lines = [
        str(unit.get("anchor") or unit.get("text") or "").strip()
        for unit in future.get("units", []) or []
        if isinstance(unit, dict) and str(unit.get("kind", "")) == "dialogue"
    ]

    bridge = create_bridge_turn(
        script,
        previous,
        _turn(target_id),
        "Claro que quero, mas é perigoso.",
    )

    assert bridge.target_id == "late_night_004"
    assert bridge.visible_fallback
    assert "sem apressar o próximo passo" in bridge.visible_fallback
    for line in future_lines:
        assert line not in bridge.visible_fallback


def test_memoria_futura_nunca_e_gravada_na_ponte_e_entra_uma_vez_na_liberacao() -> None:
    script = _script()
    audited_targets: set[str] = set()

    for origin_id, origin in script.beats.items():
        transitions = origin.get("on_user") or {}
        target_id = str(transitions.get("engaged") or "").strip()
        writes = _memory_writes(script, target_id)
        if not target_id or target_id not in script.beats or not writes:
            continue

        previous = EditorialState(node_id=origin_id)
        bridge = create_bridge_turn(script, previous, _turn(target_id), "sim, continua")
        if bridge.target_id != origin_id or not bridge_active(bridge.state):
            continue

        bridge_finalized = finalize_editorial_turn(script, bridge)
        bridge_active_ids = _active_memories(bridge_finalized.state)
        assert bridge_finalized.state.facts["_pending_memory_writes"] == ""
        assert all(memory_id not in bridge_active_ids for memory_id in writes)

        released = release_bridge_state(script, bridge_finalized.state)
        canonical_state = EditorialState.from_dict(released.to_dict())
        canonical_state.node_id = target_id
        canonical = finalize_editorial_turn(
            script,
            EditorialTurn(
                engagement="engaged",
                target_id=target_id,
                visible_fallback="",
                system_prompt="",
                state=canonical_state,
            ),
        )
        active_ids = _active_memories(canonical.state)
        for memory_id in writes:
            assert active_ids.count(memory_id) == 1
        audited_targets.add(target_id)

    assert audited_targets, "Nenhum beat com memória foi alcançado pela auditoria de ponte."
