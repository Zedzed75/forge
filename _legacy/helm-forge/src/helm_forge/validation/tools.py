"""Détection des outils externes requis par la validation.

helm-forge ne dépend d'aucun outil externe pour *générer* un projet ; il en
dépend uniquement pour le *valider*. La distinction est importante : une
machine sans helm peut parfaitement produire un chart, elle ne peut simplement
pas le vérifier.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass

from ..errors import ToolNotFoundError

#: Instructions d'installation affichées lorsqu'un outil manque.
INSTALL_HINTS: dict[str, str] = {
    "helm": (
        "installez helm depuis https://helm.sh/docs/intro/install/ "
        "(ou : curl -fsSL https://raw.githubusercontent.com/helm/helm/main/"
        "scripts/get-helm-3 | bash)"
    ),
    "kubeconform": (
        "installez kubeconform depuis "
        "https://github.com/yannh/kubeconform/releases"
    ),
}


@dataclass(frozen=True)
class Tool:
    """Un outil externe localisé sur la machine."""

    name: str
    path: str
    version: str


def is_available(name: str) -> bool:
    """Indique si l'outil est présent dans le PATH."""
    return shutil.which(name) is not None


def require(name: str) -> Tool:
    """Localise un outil, ou lève une erreur assortie d'une piste d'installation."""
    path = shutil.which(name)
    if path is None:
        hint = INSTALL_HINTS.get(name, "")
        suffix = f" — {hint}" if hint else ""
        raise ToolNotFoundError(f"outil introuvable dans le PATH : {name}{suffix}")
    return Tool(name=name, path=path, version=_version(name, path))


def _version(name: str, path: str) -> str:
    """Interroge la version de l'outil, sans jamais faire échouer l'appel.

    La version n'est qu'informative : une détection ratée ne doit pas empêcher
    la validation de se dérouler.
    """
    args = {
        "helm": ["version", "--short"],
        "kubeconform": ["-v"],
    }.get(name, ["--version"])
    try:
        result = subprocess.run(
            [path, *args], capture_output=True, text=True, timeout=30, check=False
        )
    except (OSError, subprocess.SubprocessError):  # pragma: no cover
        return "inconnue"
    output = (result.stdout or result.stderr).strip()
    return output.splitlines()[0] if output else "inconnue"
