from __future__ import annotations

from platform_core.models import AccessStatus, ProgressStatus, StoryCard


def load_demo_catalog() -> list[StoryCard]:
    return [
        StoryCard(
            package_id="roleplay2026.degustacao",
            title="Primeiro Encontro",
            subtitle="Uma história curta para conhecer a plataforma.",
            description="Uma experiência de degustação com progressão guiada por roteiro e beats.",
            genres=("Drama", "Romance"),
            access_status=AccessStatus.FREE,
            progress_status=ProgressStatus.NOT_STARTED,
            chapter_label="1 capítulo",
            is_tasting=True,
        ),
        StoryCard(
            package_id="roleplay2026.mary_casada",
            title="Mary Casada",
            subtitle="Rotina, desejo e escolhas que mudam tudo.",
            description="Uma história independente, com personagens e progressão próprios.",
            genres=("Drama", "Adulto"),
            access_status=AccessStatus.LOCKED,
            progress_status=ProgressStatus.NOT_STARTED,
            price_label="R$ 19,90",
            chapter_label="8 capítulos",
        ),
        StoryCard(
            package_id="roleplay2026.a_herdeira",
            title="A Herdeira",
            subtitle="Privilégio, controle e uma vida fora do roteiro.",
            description="Outro universo narrativo, sem compartilhar personagens ou memória.",
            genres=("Romance", "Suspense"),
            access_status=AccessStatus.LOCKED,
            progress_status=ProgressStatus.NOT_STARTED,
            price_label="R$ 24,90",
            chapter_label="10 capítulos",
        ),
    ]
