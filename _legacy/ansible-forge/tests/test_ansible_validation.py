"""Validation des projets générés par les vrais outils Ansible.

Ces tests génèrent chaque spécification d'exemple puis lui appliquent
``ansible-playbook --syntax-check`` et ``ansible-lint``. Ils sont ignorés si
aucun des deux outils n'est disponible (voir :mod:`tests.ansible_tools`).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ansible_forge.engine.planner import plan
from ansible_forge.engine.writer import write_artifacts
from ansible_forge.spec_io import load_spec
from tests.ansible_tools import get_runner, skip_reason
from tests.test_golden import SPEC_FILES

pytestmark = pytest.mark.skipif(get_runner() is None, reason=skip_reason())


@pytest.fixture(scope="module")
def runner():
    return get_runner()


def _generate(spec_path: Path, target: Path) -> Path:
    """Génère le projet décrit par ``spec_path`` dans ``target``."""
    project = target / spec_path.stem
    write_artifacts(plan(load_spec(spec_path)), project)
    return project


def _fail(label: str, result) -> str:
    """Met en forme la sortie d'un outil en échec."""
    return (
        f"{label} a échoué (code {result.returncode})\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )


@pytest.mark.parametrize("spec_path", SPEC_FILES, ids=lambda path: path.stem)
def test_syntax_check(spec_path: Path, tmp_path: Path, runner):
    """Tous les playbooks générés doivent passer --syntax-check."""
    project = _generate(spec_path, tmp_path)
    spec = load_spec(spec_path)
    inventory = f"inventories/{spec.environments[0].name}"

    for playbook in ("playbooks/site.yml", "playbooks/ping.yml"):
        result = runner.run(
            "ansible-playbook", ["-i", inventory, playbook, "--syntax-check"], project
        )
        assert result.returncode == 0, _fail(f"syntax-check {playbook}", result)


@pytest.mark.parametrize("spec_path", SPEC_FILES, ids=lambda path: path.stem)
def test_ansible_lint(spec_path: Path, tmp_path: Path, runner):
    """Le projet généré doit passer ansible-lint avec le profil configuré."""
    project = _generate(spec_path, tmp_path)
    result = runner.run("ansible-lint", ["--offline", "--nocolor"], project)
    assert result.returncode == 0, _fail("ansible-lint", result)


@pytest.mark.parametrize("spec_path", SPEC_FILES, ids=lambda path: path.stem)
def test_inventaire_lisible(spec_path: Path, tmp_path: Path, runner):
    """Chaque inventaire généré doit être analysable par ansible-inventory."""
    project = _generate(spec_path, tmp_path)
    spec = load_spec(spec_path)
    for env in spec.environments:
        result = runner.run(
            "ansible-playbook",
            ["-i", f"inventories/{env.name}", "playbooks/site.yml", "--syntax-check"],
            project,
        )
        assert result.returncode == 0, _fail(f"inventaire {env.name}", result)
