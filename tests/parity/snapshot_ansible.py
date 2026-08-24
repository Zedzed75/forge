"""Fabrique l'instantane de parite du generateur Ansible legacy.

A lancer **une seule fois**, avant le portage, tant que `_legacy/` existe :

    PYTHONPATH=_legacy/ansible-forge/src .venv/Scripts/python.exe \
        tests/parity/snapshot_ansible.py

Il rejoue le generateur d'origine sur chacune de ses specifications de test et
fige la sortie sous `tests/parity/ansible/<nom>/`. Cet instantane est la
reference de la phase 3 : le plugin porte doit produire le meme contenu, aux
ecarts volontaires pres, tous inscrits dans `MIGRATION.md` §7.

`_legacy/` est supprime en phase 6 ; l'instantane, lui, reste versionne.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

#: Racine du depot forge.
REPO_ROOT = Path(__file__).resolve().parents[2]

#: Depot legacy, source des specifications et du generateur.
LEGACY = REPO_ROOT / "_legacy" / "ansible-forge"

#: Destination de l'instantane.
PARITY = REPO_ROOT / "tests" / "parity" / "ansible"


def specifications() -> list[Path]:
    """Specs a rejouer : les 5 specs de test, plus l'exemple livre."""
    cas = sorted((LEGACY / "tests" / "specs").glob("*.yml"))
    exemple = LEGACY / "examples" / "forge.yml"
    if exemple.is_file():
        cas.append(exemple)
    return cas


def nom_du_cas(spec: Path) -> str:
    """Nom de repertoire de l'instantane, unique et stable."""
    return "exemple" if spec.parent.name == "examples" else spec.stem


def generer(spec: Path, cible: Path) -> None:
    """Lance le generateur legacy sur `spec` vers `cible`."""
    from typer.testing import CliRunner

    from ansible_forge.cli import app

    if cible.exists():
        shutil.rmtree(cible)
    resultat = CliRunner().invoke(
        app, ["generate", "--spec", str(spec), "--output", str(cible), "--force"]
    )
    if resultat.exit_code != 0:
        raise SystemExit(
            f"echec du generateur legacy sur {spec.name} "
            f"(code {resultat.exit_code}) :\n{resultat.output}"
        )


def normaliser(racine: Path) -> None:
    """Force les fins de ligne LF, pour que la comparaison porte sur le contenu."""
    for chemin in sorted(racine.rglob("*")):
        if not chemin.is_file():
            continue
        try:
            texte = chemin.read_bytes().decode("utf-8")
        except UnicodeDecodeError:  # pragma: no cover - aucun binaire attendu
            continue
        chemin.write_text(
            texte.replace("\r\n", "\n"), encoding="utf-8", newline="\n"
        )


def main() -> int:
    if not LEGACY.is_dir():
        print(f"depot legacy absent : {LEGACY}", file=sys.stderr)
        return 1

    PARITY.mkdir(parents=True, exist_ok=True)
    total = 0
    for spec in specifications():
        cible = PARITY / nom_du_cas(spec)
        generer(spec, cible)
        normaliser(cible)
        fichiers = sum(1 for p in cible.rglob("*") if p.is_file())
        total += fichiers
        print(f"{nom_du_cas(spec):12s} {fichiers:4d} fichiers")
    print(f"instantane complet : {total} fichiers sous {PARITY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
