"""Tests d'intégration : les charts générés passent réellement les outils.

Ces tests exigent ``helm`` et ``kubeconform`` dans le PATH. Ils sont sautés
avec un message explicite lorsque ceux-ci sont absents, mais la CI les installe
et les exige : c'est là que se vérifie l'exigence de CLAUDE.md selon laquelle
tout chart généré doit passer lint, template et kubeconform en mode strict.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from helm_forge.engine import render, write
from helm_forge.spec_io import load_spec
from helm_forge.validation import is_available, validate

SPECS_DIR = Path(__file__).parent / "specs"
SPEC_FILES = sorted(SPECS_DIR.glob("*.yml"))

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not (is_available("helm") and is_available("kubeconform")),
        reason="helm et kubeconform sont requis pour les tests d'intégration",
    ),
]


@pytest.mark.parametrize("spec_file", SPEC_FILES, ids=lambda p: p.stem)
def test_projet_genere_passe_toute_la_validation(
    spec_file: Path, tmp_path: Path
) -> None:
    """helm lint, helm template et kubeconform -strict, pour chaque environnement."""
    spec = load_spec(spec_file)
    write(render(spec), tmp_path, force=True)

    report = validate(tmp_path, spec)

    details = "\n\n".join(
        f"--- {check.name} ---\n{check.output}" for check in report.failures
    )
    assert report.ok, f"validation en échec pour {spec_file.stem} :\n{details}"
    # Trois contrôles par environnement : lint, template, kubeconform.
    assert len(report.checks) == 3 * len(spec.environments)


def test_le_chart_se_package(tmp_path: Path) -> None:
    """helm package doit accepter le chart, .helmignore compris."""
    import subprocess

    spec = load_spec(SPECS_DIR / "minimal.yml")
    write(render(spec), tmp_path, force=True)

    result = subprocess.run(
        ["helm", "package", str(tmp_path / "charts" / spec.app.name),
         "--destination", str(tmp_path / "dist")],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    archives = list((tmp_path / "dist").glob("*.tgz"))
    assert len(archives) == 1
