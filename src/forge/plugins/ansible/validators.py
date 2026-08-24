"""Commandes de validation du projet Ansible genere.

Portage de la partie « quoi lancer » de `ansible_forge.verify` (MIGRATION.md §3) :
l'execution, le delai, la detection d'outil manquant et le rapport appartiennent
au coeur (`forge.validate.runner`). Ici, uniquement la liste des commandes.

CLAUDE.md exige que tout projet genere passe `ansible-playbook --syntax-check`
et `ansible-lint`. Ni l'un ni l'autre n'est une dependance de forge : la
generation n'en a pas besoin, seule la verification les reclame — d'ou
`requires_linux`, qui autorise le repli WSL sous Windows (ansible-core ne
supporte pas Windows comme noeud de controle).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from forge.plugins_api.types import Command

#: Delai maximal accorde a une commande, en secondes.
TIMEOUT = 600

#: Variable d'environnement designant les collections Galaxy installees.
#: Sans elles, `--syntax-check` echoue sur les modules cites par les roles
#: (`community.general.timezone`…) : ce n'est pas un defaut du projet genere,
#: c'est un prerequis d'execution, que `requirements.yml` documente.
COLLECTIONS_ENV_VAR = "FORGE_ANSIBLE_COLLECTIONS"

#: Emplacement par defaut, repris de la convention du harnais legacy.
COLLECTIONS_DEFAUT = "/opt/forge-collections"


def environnement() -> tuple[tuple[str, str], ...]:
    """Variables d'environnement passees aux deux outils.

    La couleur est desactivee pour que le rapport reste lisible et comparable ;
    le chemin des collections est transmis s'il est configure.
    """
    variables = {"ANSIBLE_FORCE_COLOR": "0"}
    collections = os.environ.get(COLLECTIONS_ENV_VAR, COLLECTIONS_DEFAUT)
    if collections:
        variables["ANSIBLE_COLLECTIONS_PATH"] = collections
    return tuple(sorted(variables.items()))

#: Message d'installation commun aux deux outils.
INSTALL_HINT = (
    "pipx install ansible-core ansible-lint (ou "
    "python -m pip install ansible-core ansible-lint). Sous Windows, "
    "installez-les dans une distribution WSL : ansible-core ne supporte pas "
    "Windows comme noeud de controle."
)


def commands(spec: Any, outdir: Path) -> list[Command]:
    """Commandes validant le projet genere, dans l'ordre d'execution.

    Une verification de syntaxe par environnement — un inventaire incomplet ne
    se voit que sur l'environnement concerne — puis un passage d'ansible-lint
    sur l'ensemble du projet.
    """
    liste: list[Command] = []
    for env in spec.service.environments:
        liste.append(
            Command(
                label=f"syntax-check ({env.name})",
                tool="ansible-playbook",
                argv=(
                    "-i",
                    f"inventories/{env.name}",
                    "playbooks/site.yml",
                    "--syntax-check",
                ),
                cwd=outdir,
                timeout=TIMEOUT,
                env=environnement(),
                install_hint=INSTALL_HINT,
                requires_linux=True,
            )
        )
    liste.append(
        Command(
            label="ansible-lint",
            tool="ansible-lint",
            argv=("--offline", "--nocolor"),
            cwd=outdir,
            timeout=TIMEOUT,
            env=environnement(),
            install_hint=INSTALL_HINT,
            requires_linux=True,
        )
    )
    return liste
