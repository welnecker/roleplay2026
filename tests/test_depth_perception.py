from services.editorial_depth_perception import assess_depth_perception


def test_resposta_profunda_centraliza_beat_e_reage_ao_usuario() -> None:
    report = assess_depth_perception(
        "Talvez eu tenha me assustado mais que você, mas fala sério: tem certeza que não machucou?",
        beat_terms=("certeza", "machucou"),
        user_terms=("assustado",),
        emotional_terms=("fala sério",),
        max_sentences=2,
    )

    assert report.perceived_depth == "deep"
    assert report.score >= 8
    assert report.beat_centrality
    assert report.user_specificity
    assert report.emotional_embodiment
    assert not report.bureaucratic_delivery


def test_fala_burocratica_e_classificada_como_rasa() -> None:
    report = assess_depth_perception(
        "Certo. Tem certeza que não machucou?",
        beat_terms=("certeza", "machucou"),
        user_terms=("assustado",),
        emotional_terms=("fala sério", "preocup"),
        max_sentences=2,
    )

    assert report.perceived_depth == "shallow"
    assert report.bureaucratic_delivery
    assert not report.user_specificity
    assert not report.emotional_embodiment


def test_intensidade_nao_justifica_verborragia() -> None:
    response = (
        "Eu fiquei preocupada. Você pareceu distante. Isso me lembrou outras coisas. "
        "Eu pensei no que poderia acontecer. Eu não queria exagerar. "
        "Mas agora preciso saber: você se machucou?"
    )
    report = assess_depth_perception(
        response,
        beat_terms=("machucou",),
        emotional_terms=("preocupada",),
        max_sentences=3,
    )

    assert not report.concise_completion
    assert "orçamento de frases" in " ".join(report.reasons)


def test_pensamento_interno_em_primeira_pessoa_e_aceito() -> None:
    report = assess_depth_perception(
        "<thought>Por que eu me assustei tanto com isso?</thought> Tem certeza que não machucou?",
        beat_terms=("certeza", "machucou"),
        emotional_terms=("assustei",),
        max_sentences=2,
    )

    assert report.first_person_thought
    assert not report.third_person_thought_violation


def test_pensamento_em_terceira_pessoa_e_rejeitado() -> None:
    report = assess_depth_perception(
        "<thought>Mary sente que está mais preocupada do que deveria.</thought> Tem certeza que não machucou?",
        beat_terms=("certeza", "machucou"),
        emotional_terms=("preocupada",),
        max_sentences=2,
    )

    assert report.third_person_thought_violation
    assert "terceira pessoa" in " ".join(report.reasons)


def test_ausencia_de_bloco_de_pensamento_nao_e_penalizada() -> None:
    report = assess_depth_perception(
        "Você pode rir de mim depois. Primeiro me diz: tem certeza que não machucou?",
        beat_terms=("certeza", "machucou"),
        user_terms=("rir",),
        emotional_terms=("primeiro me diz",),
        max_sentences=2,
    )

    assert report.first_person_thought
    assert not report.third_person_thought_violation
    assert report.perceived_depth == "deep"


def test_resposta_que_tem_emocao_mas_perde_o_beat_nao_parece_profunda() -> None:
    report = assess_depth_perception(
        "Eu odeio admitir, mas você me deixou nervosa de um jeito que eu não esperava.",
        beat_terms=("certeza", "machucou"),
        emotional_terms=("nervosa",),
        max_sentences=2,
    )

    assert not report.beat_centrality
    assert report.perceived_depth != "deep"


def test_resposta_curta_pode_ser_profunda() -> None:
    report = assess_depth_perception(
        "Não brinca com isso agora. Você se machucou?",
        beat_terms=("machucou",),
        emotional_terms=("não brinca",),
        max_sentences=2,
    )

    assert report.concise_completion
    assert report.emotional_embodiment
    assert report.perceived_depth == "deep"
