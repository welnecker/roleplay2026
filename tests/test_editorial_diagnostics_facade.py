from pathlib import Path

from services import editorial_diagnostics, pilot_diagnostics


def test_api_editorial_e_fachada_legada_compartilham_implementacao() -> None:
    assert (
        editorial_diagnostics.EditorialGuardedResponse
        is pilot_diagnostics.GuardedResponse
    )
    assert (
        editorial_diagnostics.build_editorial_turn_diagnostics
        is pilot_diagnostics.build_turn_diagnostics
    )
    assert (
        editorial_diagnostics.finalize_editorial_model_response
        is pilot_diagnostics.finalize_model_response
    )


def test_implementacao_concreta_tem_nome_editorial() -> None:
    implementation = Path("services/editorial_diagnostics_impl.py")
    legacy = Path("services/pilot_diagnostics.py").read_text(encoding="utf-8")
    public = Path("services/editorial_diagnostics.py").read_text(encoding="utf-8")

    assert implementation.is_file()
    assert "def finalize_model_response" not in legacy
    assert "def build_turn_diagnostics" not in legacy
    assert "services.editorial_diagnostics_impl" in legacy
    assert "services.editorial_diagnostics_impl" in public


def test_api_publica_nao_depende_da_fachada_pilot() -> None:
    public = Path("services/editorial_diagnostics.py").read_text(encoding="utf-8")

    assert "services.pilot_diagnostics" not in public
