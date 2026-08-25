"""Fabrique l'instantane de parite du generateur Helm legacy.

A lancer **une seule fois**, avant le portage, tant que `_legacy/` existe :

    PYTHONPATH=_legacy/helm-forge/src .venv/Scripts/python.exe \
        tests/parity/snapshot_helm.py

`helm-forge` n'a pas de CLI : le rendu passe par `helm_forge.engine.render(spec)`,
qui retourne les fichiers en memoire. Ce script les ecrit sous
`tests/parity/helm/<nom>/`, comme son equivalent Ansible.

Les references de `_legacy/helm-forge/tests/golden/` disent la meme chose, mais
elles sont **declarees** ; celles-ci sont **mesurees** au moment du portage. Le
script verifie d'ailleurs que les deux coincident, et le dit si ce n'est pas le
cas : cela signifierait que la suite legacy n'etait pas verte.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

#: Racine du depot forge.
REPO_ROOT = Path(__file__).resolve().parents[2]

#: Depot legacy, source des specifications et du moteur de rendu.
LEGACY = REPO_ROOT / "_legacy" / "helm-forge"

#: Destination de l'instantane.
PARITY = REPO_ROOT / "tests" / "parity" / "helm"


def specifications() -> list[Path]:
    """Specs a rejouer, triees pour un instantane reproductible."""
    return sorted((LEGACY / "tests" / "specs").glob("*.yml"))


def generer(spec_path: Path, cible: Path) -> list[str]:
    """Rend `spec_path` avec le moteur legacy et ecrit le resultat dans `cible`."""
    from helm_forge.engine import render
    from helm_forge.spec_io import load_spec

    if cible.exists():
        shutil.rmtree(cible)
    rendu = render(load_spec(spec_path))
    for relatif in rendu.paths:
        destination = cible / relatif
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            rendu.files[relatif].replace("\r\n", "\n"), encoding="utf-8", newline="\n"
        )
    return sorted(rendu.paths)


def comparer_aux_golden_legacy(nom: str, produits: list[str]) -> str:
    """Compare l'instantane aux references declarees par la suite legacy."""
    reference = LEGACY / "tests" / "golden" / nom
    if not reference.is_dir():
        return "aucune reference legacy"
    attendus = sorted(
        chemin.relative_to(reference).as_posix()
        for chemin in reference.rglob("*")
        if chemin.is_file()
    )
    if attendus == produits:
        return "identique aux golden legacy"
    manquants = sorted(set(attendus) - set(produits))
    en_trop = sorted(set(produits) - set(attendus))
    return f"ECART : manquants {manquants}, en trop {en_trop}"


def main() -> int:
    if not LEGACY.is_dir():
        print(f"depot legacy absent : {LEGACY}", file=sys.stderr)
        return 1

    PARITY.mkdir(parents=True, exist_ok=True)
    total = 0
    for spec_path in specifications():
        produits = generer(spec_path, PARITY / spec_path.stem)
        total += len(produits)
        print(
            f"{spec_path.stem:10s} {len(produits):3d} fichiers "
            f"— {comparer_aux_golden_legacy(spec_path.stem, produits)}"
        )
    print(f"instantane complet : {total} fichiers sous {PARITY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
