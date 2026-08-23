"""Tests du planificateur : quels fichiers, dans quel ordre, et quels refus."""

from __future__ import annotations

import pytest

from helm_forge.engine import chart_dir, plan, resource_filename
from helm_forge.engine.planner import SPEC_SENTINEL, first_exposed
from helm_forge.errors import HelmForgeError
from helm_forge.models import (
    AddonKind,
    AppMeta,
    ComponentKind,
    ComponentSpec,
    EnvironmentSpec,
    ImageSpec,
    Layout,
    ProjectSpec,
)


def _spec(**kwargs) -> ProjectSpec:
    base = dict(
        app=AppMeta(name="shop", description="Boutique"),
        environments=[EnvironmentSpec(name="dev"), EnvironmentSpec(name="prod")],
        image=ImageSpec(repository="acme/shop"),
        components=[ComponentSpec(name="api", addons=[AddonKind.SERVICE])],
    )
    base.update(kwargs)
    return ProjectSpec(**base)


def test_chemins_du_plan(minimal_spec: ProjectSpec) -> None:
    paths = [f.path for f in plan(minimal_spec)]
    assert paths == [
        "forge.yml",
        "README.md",
        ".gitignore",
        "Makefile",
        "charts/shop/Chart.yaml",
        "charts/shop/values.yaml",
        "charts/shop/values-dev.yaml",
        "charts/shop/values-prod.yaml",
        "charts/shop/.helmignore",
        "charts/shop/README.md",
        "charts/shop/templates/_helpers.tpl",
        "charts/shop/templates/NOTES.txt",
        "charts/shop/templates/deployment-api.yaml",
        "charts/shop/templates/service-api.yaml",
        "charts/shop/templates/tests/test-connection.yaml",
    ]


def test_la_specification_est_le_premier_fichier(minimal_spec: ProjectSpec) -> None:
    """forge.yml n'est pas rendu par Jinja2 mais sérialisé depuis le modèle."""
    first = plan(minimal_spec)[0]
    assert first.path == "forge.yml"
    assert first.template == SPEC_SENTINEL


def test_repertoire_du_chart(minimal_spec: ProjectSpec) -> None:
    assert chart_dir(minimal_spec) == "charts/shop"


def test_un_fichier_de_values_par_environnement() -> None:
    spec = _spec(
        environments=[
            EnvironmentSpec(name="dev"),
            EnvironmentSpec(name="staging"),
            EnvironmentSpec(name="prod"),
        ]
    )
    values = [f.path for f in plan(spec) if "values-" in f.path]
    assert values == [
        "charts/shop/values-dev.yaml",
        "charts/shop/values-staging.yaml",
        "charts/shop/values-prod.yaml",
    ]


def test_nom_de_fichier_toujours_suffixe_par_le_composant() -> None:
    """Règle unique : le suffixe existe même avec un seul composant, pour
    qu'ajouter un second ne renomme rien."""
    component = ComponentSpec(name="api")
    assert resource_filename("deployment", component) == "deployment-api.yaml"


def test_plusieurs_composants_produisent_plusieurs_deployments() -> None:
    spec = _spec(
        components=[
            ComponentSpec(name="api", addons=[AddonKind.SERVICE]),
            ComponentSpec(name="worker", addons=[]),
        ]
    )
    paths = [f.path for f in plan(spec)]
    assert "charts/shop/templates/deployment-api.yaml" in paths
    assert "charts/shop/templates/deployment-worker.yaml" in paths
    # Le worker n'a pas d'addon service : aucun Service ne doit être généré.
    assert "charts/shop/templates/service-worker.yaml" not in paths


def test_makefile_optionnel() -> None:
    spec = _spec(extras={"makefile": False})
    assert "Makefile" not in [f.path for f in plan(spec)]


def test_tests_helm_optionnels() -> None:
    spec = _spec(extras={"helm_tests": False})
    assert not [f.path for f in plan(spec) if "tests/" in f.path]


def test_pas_de_test_de_connexion_sans_service_joignable() -> None:
    """Sans Service classique, un test de connexion n'aurait rien à interroger."""
    spec = _spec(components=[ComponentSpec(name="worker", addons=[])])
    assert first_exposed(spec) is None
    assert not [f.path for f in plan(spec) if "tests/" in f.path]


def test_premier_composant_expose_retenu_pour_le_test() -> None:
    spec = _spec(
        components=[
            ComponentSpec(name="worker", addons=[]),
            ComponentSpec(name="api", addons=[AddonKind.SERVICE]),
        ]
    )
    assert first_exposed(spec).name == "api"


# ---------------------------------------------------------------------------
# Refus explicites de ce qui n'est pas encore implémenté
# ---------------------------------------------------------------------------


def test_umbrella_refuse() -> None:
    with pytest.raises(HelmForgeError) as exc:
        plan(_spec(layout=Layout.UMBRELLA))
    assert "umbrella" in str(exc.value)


def test_type_de_composant_non_implemente_refuse() -> None:
    """Mieux vaut une erreur nette qu'un chart amputé en silence."""
    spec = _spec(
        components=[
            ComponentSpec(name="cache", kind=ComponentKind.STATEFULSET, addons=[])
        ]
    )
    with pytest.raises(HelmForgeError) as exc:
        plan(spec)
    assert "statefulset" in str(exc.value)


def test_addon_non_implemente_refuse() -> None:
    spec = _spec(
        components=[
            ComponentSpec(name="api", addons=[AddonKind.SERVICE, AddonKind.INGRESS])
        ]
    )
    with pytest.raises(HelmForgeError) as exc:
        plan(spec)
    assert "ingress" in str(exc.value)
