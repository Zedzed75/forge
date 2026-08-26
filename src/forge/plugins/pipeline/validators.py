"""Commandes de validation du pipeline genere.

Un validateur par outil de CI, et ils ne se valent pas — le dire est plus utile
que de faire semblant :

* **GitHub** — `actionlint` connait le schema des workflows, les expressions
  `${{ }}`, les actions et leurs entrees. Il trouve une cle mal placee, une
  reference a un job inexistant, une expression qui ne compile pas.
* **GitLab** — il n'existe pas d'equivalent hors ligne. Le seul linter fiable
  est celui du serveur (`/ci/lint`), qui exige une URL, un jeton et le projet
  deja cree : rien de tout cela n'a sa place dans `forge validate`. On se rabat
  donc sur `yamllint`, qui verifie la forme du document et rien de sa semantique.

Cette dissymetrie est **assumee et documentee** : le README du domaine la
mentionne, pour que « validation verte » ne veuille pas dire deux choses
differentes selon l'outil.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge.plugins.pipeline import tree
from forge.plugins_api.types import Command

#: Delai maximal accorde a une commande, en secondes.
TIMEOUT = 120

#: Message d'installation commun.
INSTALL_HINT = (
    "installez actionlint (https://github.com/rhysd/actionlint) pour GitHub, ou "
    "yamllint (pip install yamllint) pour GitLab. Sous Windows, le pont WSL les "
    "cherche dans /opt/forge-tools/bin et /opt/forge-venv/bin."
)

#: Regles yamllint appliquees au fichier GitLab. La longueur de ligne est
#: desactivee : une commande de deploiement complete depasse toute limite
#: raisonnable, et la couper serait la rendre moins lisible, pas plus.
YAMLLINT_RULES = (
    "{extends: default, rules: {line-length: disable, comments-indentation: disable, "
    "document-start: disable, truthy: {check-keys: false}}}"
)


def commands(spec: Any, outdir: Path) -> list[Command]:
    """Commande validant le fichier de pipeline genere."""
    chemin = tree.workflow_path(spec)
    if spec.pipeline.is_github:
        return [
            Command(
                label="actionlint",
                tool="actionlint",
                argv=("-no-color", "-oneline", chemin),
                cwd=outdir,
                timeout=TIMEOUT,
                env=(("NO_COLOR", "1"),),
                install_hint=INSTALL_HINT,
                requires_linux=True,
            )
        ]
    return [
        Command(
            label="yamllint",
            tool="yamllint",
            argv=("--format", "parsable", "-d", YAMLLINT_RULES, chemin),
            cwd=outdir,
            timeout=TIMEOUT,
            env=(("NO_COLOR", "1"),),
            install_hint=INSTALL_HINT,
            requires_linux=True,
        )
    ]
