from pathlib import Path

import yaml

from services.editorial_depth_perception import assess_depth_perception


_FIXTURE = Path(__file__).parent / "fixtures" / "depth_perception_cases.yaml"


def test_corpus_de_percepcao_de_profundidade() -> None:
    raw = yaml.safe_load(_FIXTURE.read_text(encoding="utf-8"))
    cases = raw.get("cases") or []

    assert len(cases) >= 8
    for case in cases:
        report = assess_depth_perception(
            case["response"],
            beat_terms=case.get("beat_terms", ()),
            user_terms=case.get("user_terms", ()),
            emotional_terms=case.get("emotional_terms", ()),
            max_sentences=case.get("max_sentences", 3),
        )
        assert report.perceived_depth == case["expected"], (
            case["case_id"],
            report,
        )


def test_falha_estrutural_nao_pode_ser_compensada_por_prosa_bonita() -> None:
    sem_beat = assess_depth_perception(
        "Eu odeio o quanto isso mexeu comigo; talvez eu esteja mais vulnerável do que queria admitir.",
        beat_terms=("telefone", "número"),
        emotional_terms=("vulnerável",),
        max_sentences=2,
    )
    terceira_pessoa = assess_depth_perception(
        "<thought>Mary percebe que está pronta para confiar.</thought> Posso te passar meu número.",
        beat_terms=("número",),
        emotional_terms=("confiar",),
        max_sentences=2,
    )

    assert sem_beat.perceived_depth == "shallow"
    assert sem_beat.score <= 4
    assert terceira_pessoa.perceived_depth == "shallow"
    assert terceira_pessoa.score <= 4


def test_profundidade_exige_convergencia_de_sinais() -> None:
    fria = assess_depth_perception(
        "Você disse que foi só um susto. Tem certeza que não machucou?",
        beat_terms=("certeza", "machucou"),
        user_terms=("susto",),
        emotional_terms=("preocup",),
        max_sentences=2,
    )
    profunda = assess_depth_perception(
        "Você pode rir de mim depois; primeiro me diz: tem certeza que não machucou?",
        beat_terms=("certeza", "machucou"),
        user_terms=("rir",),
        emotional_terms=("primeiro me diz",),
        max_sentences=2,
    )

    assert fria.perceived_depth == "adequate"
    assert profunda.perceived_depth == "deep"
    assert profunda.score > fria.score
