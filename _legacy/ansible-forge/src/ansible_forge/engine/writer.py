"""Écriture des artefacts sur disque et rendu de l'arborescence.

Le planificateur produit des artefacts en mémoire ; ce module est le seul à
toucher au système de fichiers. ``--dry-run`` réutilise :func:`build_tree` sur
exactement la même liste d'artefacts, ce qui garantit que l'aperçu correspond
au résultat réel.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from ansible_forge.engine.artifact import Artifact, sort_artifacts
from ansible_forge.errors import OutputDirError

#: Caractères de dessin de l'arborescence.
_BRANCH = "├── "
_LAST_BRANCH = "└── "
_VERTICAL = "│   "
_SPACE = "    "


def check_output_dir(directory: Path, *, force: bool = False) -> None:
    """Vérifie que le répertoire de sortie est utilisable.

    Refuse d'écrire dans un répertoire non vide sans ``force``, afin de ne
    jamais écraser un projet existant par accident.
    """
    directory = Path(directory)
    if directory.exists() and not directory.is_dir():
        raise OutputDirError(f"Le chemin de sortie existe et n'est pas un répertoire : {directory}")
    if directory.is_dir() and any(directory.iterdir()) and not force:
        raise OutputDirError(
            f"Le répertoire de sortie n'est pas vide : {directory}\n"
            "Utilisez --force pour écraser son contenu, ou choisissez un autre répertoire."
        )


def write_artifacts(artifacts: list[Artifact], directory: Path, *, force: bool = False) -> list[Path]:
    """Écrit les artefacts dans ``directory`` et retourne les chemins écrits.

    Les fichiers sont écrits en UTF-8 avec des fins de ligne LF, y compris sur
    Windows : c'est indispensable pour que la sortie soit identique quel que
    soit le système du poste de génération.
    """
    directory = Path(directory)
    check_output_dir(directory, force=force)

    written: list[Path] = []
    for artifact in sort_artifacts(artifacts):
        target = directory / Path(artifact.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(artifact.content, encoding="utf-8", newline="\n")
        written.append(target)
    return written


def build_tree(paths: list[str], root: str) -> str:
    """Rend une arborescence lisible à partir d'une liste de chemins relatifs."""
    tree = _nest(sorted(set(paths)))
    lines = [f"{root}/"]
    lines.extend(_render(tree, prefix=""))
    return "\n".join(lines)


def _nest(paths: list[str]) -> dict[str, dict]:
    """Transforme une liste de chemins plats en dictionnaire imbriqué."""
    root: dict[str, dict] = {}
    for path in paths:
        node = root
        for part in PurePosixPath(path).parts:
            node = node.setdefault(part, {})
    return root


def _render(node: dict[str, dict], prefix: str) -> list[str]:
    """Rend récursivement un niveau de l'arborescence.

    Les répertoires (nœuds ayant des enfants) sont listés avant les fichiers,
    puis triés par nom : l'affichage est donc stable d'une exécution à l'autre.
    """
    entries = sorted(node.items(), key=lambda item: (not item[1], item[0]))
    lines: list[str] = []
    for index, (name, children) in enumerate(entries):
        is_last = index == len(entries) - 1
        connector = _LAST_BRANCH if is_last else _BRANCH
        suffix = "/" if children else ""
        lines.append(f"{prefix}{connector}{name}{suffix}")
        if children:
            lines.extend(_render(children, prefix + (_SPACE if is_last else _VERTICAL)))
    return lines
