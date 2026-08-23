"""Vérifie que le projet de démonstration reste synchronisé avec sa spécification.

Sans ce test, `examples/plateforme-web/` dériverait silencieusement dès la
première modification d'un template : la démonstration livrée ne correspondrait
plus à ce que l'outil produit réellement.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ansible_forge.catalog.registry import role_names
from ansible_forge.engine.planner import plan
from ansible_forge.spec_io import load_spec
from tests.ansible_tools import get_runner, skip_reason

EXAMPLES = Path(__file__).parent.parent / "examples"
SPEC = EXAMPLES / "forge.yml"
PROJECT = EXAMPLES / "plateforme-web"

REGENERATE = (
    "Régénérez-le avec : "
    "ansible-forge generate --spec examples/forge.yml --output examples/plateforme-web --force"
)


@pytest.fixture(scope="module")
def generated() -> dict[str, str]:
    """Sortie attendue pour la spécification de démonstration."""
    return {artifact.posix_path: artifact.content for artifact in plan(load_spec(SPEC))}


def test_la_specification_de_demonstration_existe():
    assert SPEC.is_file(), f"{SPEC} est absent."


def test_le_projet_de_demonstration_existe():
    assert PROJECT.is_dir(), f"{PROJECT} est absent. {REGENERATE}"


def test_aucun_fichier_manquant_ni_en_trop(generated: dict[str, str]):
    on_disk = {
        path.relative_to(PROJECT).as_posix() for path in PROJECT.rglob("*") if path.is_file()
    }
    assert on_disk == set(generated), (
        f"Le projet de démonstration ne contient pas les mêmes fichiers que sa spec. {REGENERATE}"
    )


def test_le_contenu_est_a_jour(generated: dict[str, str]):
    for relative, expected in sorted(generated.items()):
        actual = (PROJECT / relative).read_text(encoding="utf-8")
        assert actual == expected, f"« {relative} » est obsolète. {REGENERATE}"


def test_la_demonstration_couvre_tout_le_catalogue():
    """La démonstration doit rester représentative de l'ensemble des rôles."""
    assert load_spec(SPEC).ordered_used_roles() == role_names()


@pytest.mark.skipif(get_runner() is None, reason=skip_reason())
@pytest.mark.parametrize("environment", ["dev", "staging", "prod"])
def test_la_demonstration_passe_le_syntax_check(environment: str):
    """La démonstration livrée doit être exécutable telle quelle."""
    result = get_runner().run(
        "ansible-playbook",
        ["-i", f"inventories/{environment}", "playbooks/site.yml", "--syntax-check"],
        PROJECT,
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"


@pytest.mark.skipif(get_runner() is None, reason=skip_reason())
def test_la_demonstration_passe_ansible_lint():
    result = get_runner().run("ansible-lint", ["--offline", "--nocolor"], PROJECT)
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
