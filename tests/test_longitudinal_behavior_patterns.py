from __future__ import annotations

from services.editorial_longitudinal_patterns import (
    render_behavior_patterns,
    update_behavior_patterns,
)
from services.editorial_runtime_impl import PilotState


def _document() -> dict:
    return {
        "behavior_patterns": {
            "history_size": 6,
            "max_visible_patterns": 2,
            "signals": {
                "respectful": {
                    "engagements": ["engaged"],
                    "context_patterns": [r"\\brespeito\\b"],
                    "match": "any",
                },
                "evasive": {"engagements": ["minimal", "dismissive"]},
                "warm": {"engagements": ["engaged"]},
                "cold": {"engagements": ["minimal", "dismissive"]},
            },
            "patterns": {
                "sustained_respect": {
                    "label": "Respeito sustentado",
                    "kind": "signal_count",
                    "signal": "respectful",
                    "window": 4,
                    "min_observations": 3,
                    "min_count": 3,
                    "interpretation": "Lia percebe respeito consistente.",
                },
                "recurring_evasion": {
                    "label": "Evasão recorrente",
                    "kind": "signal_count",
                    "signal": "evasive",
                    "window": 4,
                    "min_observations": 3,
                    "min_count": 3,
                    "interpretation": "Lia percebe evasão repetida.",
                },
                "hot_and_cold": {
                    "label": "Quente e frio",
                    "kind": "alternation",
                    "positive": ["warm", "engaged"],
                    "negative": ["cold", "minimal", "dismissive"],
                    "window": 4,
                    "min_observations": 4,
                    "min_switches": 3,
                    "interpretation": "Lia percebe alternância recorrente.",
                },
            },
        }
    }


def _turn(state: PilotState, engagement: str, text: str) -> list:
    state.node_id = f"beat_{len(state.recent_engagement)}"
    state.recent_engagement.append(engagement)
    _, patterns = update_behavior_patterns(_document(), state, text, engagement)
    return patterns


def test_um_turno_isolado_nao_vira_padrao() -> None:
    state = PilotState()

    patterns = _turn(state, "engaged", "Eu respeito seu tempo.")

    assert patterns == []


def test_respeito_repetido_ativa_padrao_longitudinal() -> None:
    state = PilotState()
    _turn(state, "engaged", "Eu respeito seu tempo.")
    _turn(state, "engaged", "Pode ser no seu ritmo.")
    patterns = _turn(state, "engaged", "Respeito seus limites.")

    assert [item.pattern_id for item in patterns] == ["sustained_respect"]
    assert "respeito consistente" in patterns[0].interpretation


def test_evasao_recorrente_exige_varios_turnos() -> None:
    state = PilotState()
    _turn(state, "minimal", "ok")
    _turn(state, "dismissive", "continua")
    patterns = _turn(state, "minimal", "sim")

    assert "recurring_evasion" in [item.pattern_id for item in patterns]


def test_alternancia_quente_fria_e_detectada() -> None:
    state = PilotState()
    _turn(state, "engaged", "Quero te conhecer.")
    _turn(state, "minimal", "ok")
    _turn(state, "engaged", "Gosto de você.")
    patterns = _turn(state, "dismissive", "continua")

    assert "hot_and_cold" in [item.pattern_id for item in patterns]


def test_mesmo_turno_nao_e_registrado_duas_vezes() -> None:
    state = PilotState(node_id="beat", recent_engagement=["engaged"])
    update_behavior_patterns(_document(), state, "Respeito você.", "engaged")
    update_behavior_patterns(_document(), state, "Respeito você.", "engaged")

    import json

    history = json.loads(state.facts["_behavior_pattern_history_json"])
    assert len(history) == 1


def test_renderizacao_nao_expoe_ids_ou_contagens() -> None:
    state = PilotState()
    _turn(state, "engaged", "Respeito você.")
    _turn(state, "engaged", "Respeito seu tempo.")
    patterns = _turn(state, "engaged", "Respeito seus limites.")

    prompt = render_behavior_patterns(patterns)

    assert "Respeito sustentado" in prompt
    assert "sustained_respect" not in prompt
    assert "contagens" in prompt
