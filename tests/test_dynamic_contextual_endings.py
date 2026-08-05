from __future__ import annotations

from services.editorial_compiler import compile_editorial_document
from services.editorial_content import load_source_document
from services.editorial_contextual_destination import (
    current_interaction_context,
    parse_contextual_destination,
)
from services.editorial_progression import prepare_editorial_script
from services.editorial_runtime_impl import PilotScript, PilotState


def _script() -> PilotScript:
    document = load_source_document()
    return prepare_editorial_script(PilotScript(compile_editorial_document(document)))


def test_recusa_veemente_pode_entrar_no_patio_dinamico() -> None:
    script = _script()
    context = current_interaction_context(
        script,
        PilotState(node_id="encontro_acidental_003"),
    )

    destination = parse_contextual_destination(
        '{"route":"terminal_yard","signal":"explicit_or_vehement_rejection_of_continuation","reason":"o usuário ordenou que Mary se afastasse","confidence":0.99}',
        context,
    )

    assert destination.route == "terminal_yard"
    assert context.terminal_yard_target == "yard_dynamic_rupture_001"
    assert "explicit_or_vehement_rejection_of_continuation" in context.terminal_violations


def test_violencia_gratuita_pode_encerrar_imediatamente() -> None:
    script = _script()
    context = current_interaction_context(
        script,
        PilotState(node_id="encontro_acidental_002"),
    )

    destination = parse_contextual_destination(
        '{"route":"immediate_ending","signal":"gratuitous_violence_or_credible_threat","reason":"ameaça concreta e gratuita","confidence":0.99}',
        context,
    )

    assert destination.route == "immediate_ending"
    assert context.immediate_ending_target == "end_hostile"


def test_motel_nao_herda_limites_sexuais_do_primeiro_contato() -> None:
    script = _script()
    context = current_interaction_context(
        script,
        PilotState(node_id="motel_arrival_003"),
    )

    assert context.relationship_stage != "strangers"
    assert "sexual_harassment_in_incompatible_context" not in context.terminal_violations
    assert "explicit_sexual_proposition_before_mutual_intimacy" not in context.terminal_violations


def test_patio_dinamico_existe_e_nao_retorna_ao_fluxo_principal() -> None:
    script = _script()

    first = script.beats["yard_dynamic_rupture_001"]
    second = script.beats["yard_dynamic_rupture_002"]

    assert first["on_user"]["engaged"] == "yard_dynamic_rupture_002"
    assert second["on_user"]["engaged"] == "end_dynamic_rupture"
    assert script.endings["end_dynamic_rupture"]["ending_code"] == "contextual_interaction_broken"
