"""Enumerations du domaine pipeline."""

from __future__ import annotations

from enum import Enum


class Provider(str, Enum):
    """Outil d'integration continue vise.

    Le choix change le **format du fichier**, jamais ce qu'il contient : les
    memes jobs, derives du meme contexte, s'ecrivent dans les deux dialectes.
    C'est la seule raison pour laquelle deux gabarits cohabitent.
    """

    #: GitHub Actions — `.github/workflows/ci.yml`.
    GITHUB = "github"

    #: GitLab CI — `.gitlab-ci.yml`.
    GITLAB = "gitlab"


class JobKind(str, Enum):
    """Nature d'un job engendre. Fixe son etage et ses dependances."""

    #: Validation d'un domaine : ses propres `Command`, telles qu'il les declare.
    VALIDATE = "validate"

    #: Construction et publication de l'image du service.
    BUILD = "build"

    #: Deploiement d'un environnement, un job par environnement.
    DEPLOY = "deploy"
