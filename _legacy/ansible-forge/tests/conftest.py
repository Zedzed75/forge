"""Fixtures partagées par la suite de tests."""

from __future__ import annotations

from typing import Any

import pytest

from ansible_forge.models.spec import ProjectSpec


def build_spec(**overrides: Any) -> ProjectSpec:
    """Construit une spec valide minimale, surchargeable champ par champ."""
    data: dict[str, Any] = {
        "project_name": "demo-infra",
        "description": "Projet de demonstration",
        "author": "Equipe Infra",
        "groups": [
            {
                "name": "webservers",
                "description": "Serveurs web frontaux",
                "roles": ["common", "nginx"],
            },
        ],
        "environments": [
            {
                "name": "dev",
                "hosts": {
                    "webservers": [
                        {"name": "web-dev-01", "ansible_host": "192.168.56.11"},
                    ],
                },
            },
        ],
    }
    data.update(overrides)
    return ProjectSpec.model_validate(data)


def pytest_addoption(parser: pytest.Parser) -> None:
    """Ajoute l'option de régénération des références golden."""
    parser.addoption(
        "--regen-golden",
        action="store_true",
        default=False,
        help="Réécrit les références de tests/golden/ au lieu de les comparer.",
    )


@pytest.fixture
def spec() -> ProjectSpec:
    """Spec valide minimale, réutilisable dans les tests."""
    return build_spec()
