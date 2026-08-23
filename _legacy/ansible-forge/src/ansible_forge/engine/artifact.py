"""Représentation en mémoire d'un fichier à écrire.

Le planificateur produit des :class:`Artifact` sans jamais toucher au disque.
C'est ce qui permet à ``--dry-run``, aux tests golden et à l'écriture réelle de
partager exactement le même code de génération.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True)
class Artifact:
    """Un fichier du projet généré.

    Attributs :
        path: chemin relatif à la racine du projet, toujours en séparateurs
            POSIX pour que la sortie soit identique sur Windows et sur Linux.
        content: contenu textuel complet, fins de ligne LF.
    """

    path: PurePosixPath
    content: str

    def __post_init__(self) -> None:
        if self.path.is_absolute():
            raise ValueError(f"Le chemin d'un artefact doit être relatif : {self.path}")

    @property
    def posix_path(self) -> str:
        """Chemin sous forme de chaîne POSIX, utilisé pour le tri et l'affichage."""
        return self.path.as_posix()


def sort_artifacts(artifacts: list[Artifact]) -> list[Artifact]:
    """Trie les artefacts par chemin : garantit un ordre de génération stable."""
    return sorted(artifacts, key=lambda artifact: artifact.posix_path)
