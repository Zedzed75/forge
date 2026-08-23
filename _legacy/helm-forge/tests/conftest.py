"""Fixtures partagées par la suite de tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from helm_forge.models import (
    AddonKind,
    AppMeta,
    ComponentKind,
    ComponentSpec,
    EnvironmentSpec,
    ImageSpec,
    ProjectSpec,
)


#: Répertoires des spécifications de référence et de leur rendu attendu.
SPECS_DIR = Path(__file__).parent / "specs"
GOLDEN_DIR = Path(__file__).parent / "golden"


def pytest_addoption(parser: pytest.Parser) -> None:
    """Ajoute l'option de régénération des fichiers de référence."""
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help=(
            "réécrit les fichiers de référence de tests/golden/ à partir des "
            "spécifications de tests/specs/. À n'utiliser que lorsque le "
            "changement de rendu est intentionnel, et à relire dans le diff."
        ),
    )


@pytest.fixture
def update_golden(request: pytest.FixtureRequest) -> bool:
    """Vrai lorsque la suite est lancée avec --update-golden."""
    return bool(request.config.getoption("--update-golden"))


@pytest.fixture
def minimal_spec() -> ProjectSpec:
    """Spécification la plus simple possible : une API, deux environnements.

    Les addons sont énumérés explicitement plutôt que laissés par défaut : ce
    jeu doit rester aligné sur ce que le générateur sait produire.
    """
    return ProjectSpec(
        app=AppMeta(name="shop", description="Boutique en ligne"),
        environments=[EnvironmentSpec(name="dev"), EnvironmentSpec(name="prod")],
        image=ImageSpec(registry="ghcr.io", repository="acme/shop"),
        components=[ComponentSpec(name="api", addons=[AddonKind.SERVICE])],
    )


@pytest.fixture
def full_spec() -> ProjectSpec:
    """Spécification exerçant tous les types de composants et d'addons."""
    return ProjectSpec(
        app=AppMeta(
            name="shop",
            description="Boutique en ligne",
            chart_version="1.2.3",
            app_version="2026.8.1",
            maintainer_name="Equipe plateforme",
            maintainer_email="platform@example.com",
        ),
        environments=[
            EnvironmentSpec(name="dev"),
            EnvironmentSpec(name="staging"),
            EnvironmentSpec(name="prod"),
        ],
        image=ImageSpec(registry="ghcr.io", repository="acme/shop"),
        components=[
            ComponentSpec(
                name="api",
                kind=ComponentKind.DEPLOYMENT,
                addons=[
                    AddonKind.SERVICE,
                    AddonKind.INGRESS,
                    AddonKind.CONFIGMAP,
                    AddonKind.SECRET,
                    AddonKind.HPA,
                    AddonKind.PDB,
                    AddonKind.SERVICEACCOUNT,
                ],
            ),
            ComponentSpec(
                name="worker",
                kind=ComponentKind.DEPLOYMENT,
                addons=[AddonKind.CONFIGMAP],
                command=["/app/worker"],
            ),
            ComponentSpec(
                name="cache",
                kind=ComponentKind.STATEFULSET,
                addons=[AddonKind.SERVICE],
            ),
            ComponentSpec(
                name="cleanup",
                kind=ComponentKind.CRONJOB,
                addons=[AddonKind.CONFIGMAP],
            ),
        ],
    )
