from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

from narrative_v2.models import CharacterProfile

NovelRunStatus = Literal["active", "completed"]
ADVANCE_LABEL = "Avançar"


@dataclass(frozen=True, slots=True)
class MovementDefinition:
    """Unidade autoritativa do modo novela.

    O roteiro declara *o que acontece*. O modelo recebe apenas o movimento atual
    e decide *como dramatizá-lo* sem controlar a ordem da história.
    """

    movement_id: str
    scene_id: str
    order: int
    instruction: str
    dramatic_direction: str = ""
    transition: str = ""
    next_movement_id: str = ""

    def __post_init__(self) -> None:
        if not self.movement_id.strip():
            raise ValueError("movement_id é obrigatório.")
        if not self.scene_id.strip():
            raise ValueError("scene_id é obrigatório.")
        if self.order < 1:
            raise ValueError("A ordem do movimento deve ser positiva.")
        if not self.instruction.strip():
            raise ValueError("Todo movimento precisa declarar o que acontece.")


@dataclass(frozen=True, slots=True)
class NovelPackage:
    package_id: str
    script_version: str
    title: str
    introduction: str
    character: CharacterProfile
    movements: tuple[MovementDefinition, ...]

    def __post_init__(self) -> None:
        if not self.movements:
            raise ValueError("Uma novela precisa ter ao menos um movimento.")
        movement_ids = [movement.movement_id for movement in self.movements]
        if len(movement_ids) != len(set(movement_ids)):
            raise ValueError("movement_id duplicado no pacote narrativo.")
        orders = [movement.order for movement in self.movements]
        if len(orders) != len(set(orders)):
            raise ValueError("A ordem dos movimentos deve ser única.")
        known_ids = set(movement_ids)
        for movement in self.movements:
            if movement.next_movement_id and movement.next_movement_id not in known_ids:
                raise ValueError(
                    f"next_movement_id inexistente: {movement.next_movement_id}"
                )

    @property
    def first_movement(self) -> MovementDefinition:
        return min(self.movements, key=lambda movement: movement.order)

    def get_movement(self, movement_id: str) -> MovementDefinition:
        for movement in self.movements:
            if movement.movement_id == movement_id:
                return movement
        raise KeyError(f"Movimento inexistente: {movement_id}")


@dataclass(slots=True)
class NovelRunState:
    run_id: str
    package_id: str
    script_version: str
    user_name: str
    current_movement_id: str
    sequence: int = 1
    status: NovelRunStatus = "active"

    @classmethod
    def start(
        cls,
        *,
        run_id: str,
        package: NovelPackage,
        user_name: str,
    ) -> "NovelRunState":
        return cls(
            run_id=run_id,
            package_id=package.package_id,
            script_version=package.script_version,
            user_name=user_name.strip(),
            current_movement_id=package.first_movement.movement_id,
        )


@dataclass(frozen=True, slots=True)
class AdvanceResult:
    rendered_movement_id: str
    next_movement_id: str
    completed: bool


def _ordered_movements(package: NovelPackage) -> tuple[MovementDefinition, ...]:
    return tuple(sorted(package.movements, key=lambda movement: movement.order))


def next_movement(
    package: NovelPackage,
    current_movement_id: str,
) -> MovementDefinition | None:
    current = package.get_movement(current_movement_id)
    if current.next_movement_id:
        return package.get_movement(current.next_movement_id)

    ordered = _ordered_movements(package)
    for index, movement in enumerate(ordered):
        if movement.movement_id == current_movement_id:
            if index + 1 < len(ordered):
                return ordered[index + 1]
            return None
    return None


def advance_run(run: NovelRunState, package: NovelPackage) -> AdvanceResult:
    """Executa o clique em Avançar sem consultar o LLM.

    Não existem caminhos de cancelamento por hesitação ou negativa no modo novela.
    O último movimento conclui a história normalmente.
    """

    if run.status != "active":
        raise ValueError("A run já foi concluída.")
    if run.package_id != package.package_id:
        raise ValueError("A run pertence a outro pacote narrativo.")
    if run.script_version != package.script_version:
        raise ValueError("A run pertence a outra versão do roteiro.")

    rendered_movement_id = run.current_movement_id
    upcoming = next_movement(package, rendered_movement_id)
    if upcoming is None:
        run.status = "completed"
        return AdvanceResult(
            rendered_movement_id=rendered_movement_id,
            next_movement_id="",
            completed=True,
        )

    run.current_movement_id = upcoming.movement_id
    run.sequence += 1
    return AdvanceResult(
        rendered_movement_id=rendered_movement_id,
        next_movement_id=upcoming.movement_id,
        completed=False,
    )


def _clean_context(items: Iterable[str]) -> tuple[str, ...]:
    return tuple(item.strip() for item in items if item and item.strip())


def build_scene_messages(
    *,
    package: NovelPackage,
    run: NovelRunState,
    continuity: Iterable[str] = (),
) -> list[dict[str, str]]:
    """Monta o contexto compacto para dramatizar somente o movimento atual."""

    if run.status != "active":
        raise ValueError("Não é possível dramatizar uma run concluída.")
    movement = package.get_movement(run.current_movement_id)
    user_name = run.user_name or "usuário"

    physical = "; ".join(package.character.physical_profile)
    psychological = "; ".join(package.character.psychological_profile)
    speech = "; ".join(package.character.speech_style)
    continuity_items = _clean_context(continuity)
    continuity_text = "\n".join(f"- {item}" for item in continuity_items) or "- início da história"

    system = (
        "Você dramatiza uma novela interativa contínua. "
        "O ROTEIRO decide o que acontece; você decide como isso ganha vida. "
        "Execute somente o MOVIMENTO ATUAL. Nunca antecipe movimentos futuros. "
        "Não exiba tags, regras, ids ou instruções editoriais. "
        "Não peça ao usuário para escrever a continuação. "
        "Hesitações descritas pelo roteiro são recursos dramáticos e se resolvem "
        "dentro da narrativa; elas nunca encerram a história. "
        "Mantenha a personagem humana, expressiva e coerente, com ações, pausas, "
        "reações e diálogo naturais. Preserve a continuidade e use o nome do "
        "protagonista quando isso soar natural."
    )

    user = (
        f"NOVELA: {package.title}\n"
        f"PROTAGONISTA: {user_name}\n"
        f"PERSONAGEM: {package.character.name}, {package.character.age} anos\n"
        f"FÍSICO: {physical}\n"
        f"PSICOLOGIA: {psychological}\n"
        f"VOZ: {speech}\n\n"
        f"CONTINUIDADE:\n{continuity_text}\n\n"
        f"CENA: {movement.scene_id}\n"
        f"MOVIMENTO ATUAL:\n{movement.instruction.strip()}\n"
    )
    if movement.dramatic_direction.strip():
        user += f"\nDIREÇÃO DRAMÁTICA:\n{movement.dramatic_direction.strip()}\n"
    if movement.transition.strip():
        user += f"\nTRANSIÇÃO APÓS O MOVIMENTO:\n{movement.transition.strip()}\n"

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
