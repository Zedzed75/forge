"""Tests de non-régression sur la sortie générée (golden files).

Pour chaque spécification de ``tests/specs/``, la sortie complète est comparée
fichier par fichier à la référence stockée dans ``tests/golden/<spec>/``.

Régénérer les références après une modification volontaire :

    pytest --regen-golden

Relisez toujours le ``git diff`` des références avant de le valider : c'est la
seule protection contre une modification involontaire du rendu.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ansible_forge.engine.planner import plan
from ansible_forge.spec_io import load_spec

SPEC_DIR = Path(__file__).parent / "specs"
GOLDEN_DIR = Path(__file__).parent / "golden"

SPEC_FILES = sorted(SPEC_DIR.glob("*.yml"))


def _read_golden(directory: Path) -> dict[str, str]:
    """Charge une référence complète, indexée par chemin relatif POSIX."""
    return {
        path.relative_to(directory).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def _write_golden(directory: Path, generated: dict[str, str]) -> None:
    """Réécrit intégralement une référence."""
    if directory.exists():
        for path in sorted(directory.rglob("*"), reverse=True):
            path.unlink() if path.is_file() else path.rmdir()
    for relative, content in sorted(generated.items()):
        target = directory / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")


@pytest.mark.parametrize("spec_path", SPEC_FILES, ids=lambda path: path.stem)
def test_sortie_conforme_a_la_reference(spec_path: Path, request: pytest.FixtureRequest):
    spec = load_spec(spec_path)
    generated = {artifact.posix_path: artifact.content for artifact in plan(spec)}
    golden_dir = GOLDEN_DIR / spec_path.stem

    if request.config.getoption("--regen-golden"):
        _write_golden(golden_dir, generated)
        pytest.skip(f"Référence régénérée : {golden_dir}")

    if not golden_dir.exists():
        pytest.fail(
            f"Référence absente pour « {spec_path.stem} ». "
            "Générez-la avec : pytest --regen-golden"
        )

    expected = _read_golden(golden_dir)

    missing = sorted(set(expected) - set(generated))
    extra = sorted(set(generated) - set(expected))
    assert not missing, f"Fichiers attendus mais non générés : {missing}"
    assert not extra, f"Fichiers générés mais absents de la référence : {extra}"

    for relative in sorted(expected):
        assert generated[relative] == expected[relative], (
            f"Le contenu de « {relative} » diffère de la référence. "
            "Si le changement est voulu : pytest --regen-golden"
        )


@pytest.mark.parametrize("spec_path", SPEC_FILES, ids=lambda path: path.stem)
def test_generation_reproductible(spec_path: Path):
    """Deux générations successives de la même spec doivent être identiques."""
    spec = load_spec(spec_path)
    first = {artifact.posix_path: artifact.content for artifact in plan(spec)}
    second = {artifact.posix_path: artifact.content for artifact in plan(load_spec(spec_path))}
    assert first == second


@pytest.mark.parametrize("spec_path", SPEC_FILES, ids=lambda path: path.stem)
def test_tout_fichier_yaml_genere_commence_par_un_marqueur_de_document(spec_path: Path):
    """La règle yamllint « document-start » s'applique aussi aux fichiers annexes.

    Le projet généré embarque sa propre configuration de lint : il doit la
    respecter lui-même, sinon ansible-lint échoue chez l'utilisateur. Ce
    contrôle est fait ici plutôt que par ansible-lint seul, car la liste des
    fichiers qu'ansible-lint inspecte varie d'une version d'ansible-core à
    l'autre.
    """
    for artifact in plan(load_spec(spec_path)):
        if not artifact.posix_path.endswith((".yml", ".yaml")):
            continue
        first = artifact.content.splitlines()[0]
        assert first == "---", (
            f"« {artifact.posix_path} » commence par {first!r} au lieu de '---'."
        )


def test_les_specs_d_exemple_existent():
    """Sans spec d'exemple, les tests golden passeraient à vide."""
    assert SPEC_FILES, "Aucune spécification dans tests/specs/."
