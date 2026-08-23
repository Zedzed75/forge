"""Écriture sur disque d'un ensemble de fichiers rendus.

Seul module du moteur autorisé à toucher au système de fichiers. Il n'invente
aucun contenu : il écrit exactement ce que le rendu a produit.
"""

from __future__ import annotations

from pathlib import Path

from ..errors import TargetExistsError
from .renderer import FileSet

#: Fichiers et répertoires ignorés lorsqu'on juge si une cible est « vide ».
_IGNORED_ENTRIES = frozenset({".git", ".gitkeep", ".DS_Store"})


def write(files: FileSet, target: Path, force: bool = False) -> list[Path]:
    """Écrit un ensemble de fichiers dans le répertoire cible.

    Refuse d'écrire dans un répertoire non vide sans ``force`` : une génération
    réécrit tous les fichiers du projet et effacerait des modifications
    manuelles sans prévenir.

    Renvoie la liste des chemins écrits, dans l'ordre de génération.
    """
    if not force and _is_occupied(target):
        raise TargetExistsError(
            f"le répertoire {target} existe et n'est pas vide ; utilisez "
            "--force pour écraser son contenu"
        )

    written: list[Path] = []
    for relative, content in files.files.items():
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        # newline="\n" est explicite : les fichiers générés sont en LF sur
        # toutes les plateformes, sinon les fichiers de référence divergent.
        destination.write_text(content, encoding="utf-8", newline="\n")
        written.append(destination)
    return written


def _is_occupied(target: Path) -> bool:
    """Indique si la cible existe et contient autre chose que des broutilles."""
    if not target.exists():
        return False
    if not target.is_dir():
        return True
    return any(entry.name not in _IGNORED_ENTRIES for entry in target.iterdir())
