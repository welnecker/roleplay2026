from __future__ import annotations

from dataclasses import dataclass

from packages.models import InstalledStoryPackage


class RuntimeRoutingError(ValueError):
    """Raised when a package runtime has no registered player."""


@dataclass(frozen=True, slots=True)
class RuntimeRoute:
    kind: str
    page: str


_RUNTIME_ROUTES: dict[str, RuntimeRoute] = {
    "editorial": RuntimeRoute(
        kind="editorial",
        page="pages/2_Historia_Editorial.py",
    ),
    "simple": RuntimeRoute(
        kind="simple",
        page="app.py",
    ),
}


def runtime_route_for(package: InstalledStoryPackage) -> RuntimeRoute:
    """Resolve navigation from the package contract, never from its identity."""

    kind = package.manifest.runtime.kind
    route = _RUNTIME_ROUTES.get(kind)
    if route is None:
        raise RuntimeRoutingError(
            f"Nenhum player registrado para runtime.kind={kind!r}"
        )
    return route


def player_page_for(package: InstalledStoryPackage) -> str:
    return runtime_route_for(package).page
