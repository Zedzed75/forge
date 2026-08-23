"""Tests de non-régression par fichiers de référence.

Chaque spécification de ``tests/specs/`` est rendue puis comparée fichier par
fichier au contenu attendu, stocké dans ``tests/golden/<spec>/``. Toute
modification du rendu apparaît donc en clair dans le diff du dépôt, ce qui
force à décider si elle est voulue.

Régénérer les références après un changement volontaire :

    pytest tests/test_golden.py --update-golden

puis relire le diff avant de valider.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from helm_forge.engine import render
from helm_forge.spec_io import load_spec

SPECS_DIR = Path(__file__).parent / "specs"
GOLDEN_DIR = Path(__file__).parent / "golden"

#: Spécifications de référence, triées pour un ordre de test stable.
SPEC_FILES = sorted(SPECS_DIR.glob("*.yml"))


def test_des_specifications_de_reference_existent() -> None:
    """Garde-fou : un glob vide ferait passer la suite sans rien vérifier."""
    assert SPEC_FILES, "aucune spécification dans tests/specs/"


@pytest.mark.parametrize("spec_file", SPEC_FILES, ids=lambda p: p.stem)
def test_rendu_conforme_a_la_reference(spec_file: Path, update_golden: bool) -> None:
    spec = load_spec(spec_file)
    rendered = render(spec)
    reference = GOLDEN_DIR / spec_file.stem

    if update_golden:
        _rewrite(reference, rendered.files)
        pytest.skip(f"références régénérées pour {spec_file.stem}")

    assert reference.is_dir(), (
        f"références absentes pour {spec_file.stem} ; "
        "lancez pytest --update-golden pour les créer"
    )

    expected_paths = sorted(
        str(p.relative_to(reference)).replace("\\", "/")
        for p in reference.rglob("*")
        if p.is_file()
    )
    assert sorted(rendered.paths) == expected_paths, (
        "la liste des fichiers générés a changé"
    )

    for relative in rendered.paths:
        expected = (reference / relative).read_text(encoding="utf-8")
        assert rendered[relative] == expected, f"contenu différent : {relative}"


def _rewrite(reference: Path, files: dict[str, str]) -> None:
    """Réécrit intégralement un répertoire de référence.

    Les fichiers obsolètes sont supprimés : sans cela, un fichier qui cesse
    d'être généré resterait indéfiniment dans les références.
    """
    if reference.exists():
        for path in sorted(reference.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            else:
                path.rmdir()
    for relative, content in files.items():
        destination = reference / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8", newline="\n")
