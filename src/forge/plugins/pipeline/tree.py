"""Chemins que le domaine pipeline ecrit.

Le seul domaine du projet dont la sortie est la **racine du depot** : un fichier
de CI n'existe que la ou son outil le lit, et ni GitHub ni GitLab ne le
cherchent ailleurs. `DomainInfo.outdir` vaut donc `.`, ce que le coeur sait
traiter depuis la phase 8 (`pipeline.foreign_paths`).

Consequence a ne pas oublier : ce domaine partage sa racine avec les fichiers de
niveau depot que forge ecrit lui-meme (`README.md`, `forge.yml`,
`.gitattributes`). Il ne doit donc **jamais** produire un fichier portant l'un de
ces noms — un test le verifie.
"""

from __future__ import annotations

from typing import Any, Final

#: Emplacement impose par GitHub Actions.
GITHUB_WORKFLOW: Final[str] = ".github/workflows/ci.yml"

#: Emplacement impose par GitLab CI.
GITLAB_CONFIG: Final[str] = ".gitlab-ci.yml"

#: Fichiers de niveau depot ecrits par forge lui-meme, avec lesquels ce domaine
#: partage sa racine.
REPO_LEVEL_FILES: Final[frozenset[str]] = frozenset(
    {"README.md", "forge.yml", ".gitattributes"}
)


def workflow_path(spec: Any) -> str:
    """Chemin du fichier de pipeline, relatif a la racine du depot."""
    return GITHUB_WORKFLOW if spec.pipeline.is_github else GITLAB_CONFIG


def expected_paths(spec: Any) -> list[str]:
    """Tous les chemins ecrits par le domaine, tries."""
    return sorted([workflow_path(spec), ".copier-answers.yml"])


def provider_slots(spec: Any) -> dict[str, list[dict[str, str]]]:
    """Emplacements de fichier par outil de CI : `[{...}]` pour l'un, `[]` pour l'autre.

    Meme motif que les deux autres domaines (arbitrage R4) : le chemin du
    gabarit porte une balise `yield`, et copier decide d'ecrire ou non — y
    compris le repertoire `.github/`, qui n'a pas a exister chez GitLab.
    """
    retenu = spec.pipeline.provider.value
    return {
        nom: ([{"name": nom}] if nom == retenu else [])
        for nom in ("github", "gitlab")
    }
