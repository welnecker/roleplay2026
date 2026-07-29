from roleplay.models import Movement, StoryDefinition


CASADA_FRUSTRADA = StoryDefinition(
    story_id="casada_frustrada",
    title="Casada frustrada",
    sequence=(
        ("supermarket_encounter", "injury_check"),
        ("supermarket_encounter", "recognize_plaza"),
    ),
    movements=(
        Movement(
            order=10,
            route="supermarket_encounter",
            beat="injury_check",
            kind="fala",
            content="Eita, caralho... desculpa!",
        ),
        Movement(
            order=20,
            route="supermarket_encounter",
            beat="injury_check",
            kind="fala",
            content="Tem certeza que está tudo bem? Não machucou?",
        ),
        Movement(
            order=30,
            route="supermarket_encounter",
            beat="recognize_plaza",
            kind="fala",
            content="Espera... eu conheço você de algum lugar?",
        ),
    ),
)
