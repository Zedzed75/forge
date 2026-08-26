"""Commandes de validation du projet Terraform genere.

Premier domaine sans generateur legacy : il n'existe aucun instantane de parite
pour dire si la sortie est juste. Ce sont ces quatre commandes qui tiennent ce
role, et elles verifient des choses differentes :

1. `terraform fmt -check` — la mise en forme canonique. Ne demande ni reseau ni
   `init`, et attrape le defaut que les gabarits produisent le plus facilement :
   un `=` mal aligne. C'est aussi un controle de determinisme, puisque la forme
   canonique est unique.
2. `terraform init -backend=false` — les providers se resolvent. Sans elle,
   `validate` refuse de s'executer. `-backend=false` evite de joindre le
   stockage d'etat : on valide du code, on ne touche a aucune infrastructure.
3. `terraform validate` — la configuration tient debout : types, references,
   arguments obligatoires, blocs inconnus. C'est le validateur central.
4. `tflint` — ce que `validate` laisse passer : version de provider non bornee,
   variable declaree et jamais employee, nom de ressource non conforme.

Les trois premieres tournent **par racine d'environnement** : chaque racine est
une configuration Terraform independante, et rien ne garantit que la validite de
l'une entraine celle de l'autre. `tflint` parcourt l'arborescence en une fois.

Aucune de ces commandes ne joint le cluster ni ne lit un etat : `forge validate`
verifie du code, jamais une infrastructure.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from forge.plugins.terraform import tree
from forge.plugins_api.types import Command

#: Delai maximal accorde a une commande, en secondes. `init` telecharge des
#: providers au premier passage : le delai est plus large que celui des autres
#: domaines.
TIMEOUT = 600

#: Message d'installation commun aux deux outils.
INSTALL_HINT = (
    "installez terraform (https://developer.hashicorp.com/terraform/install) et "
    "tflint (https://github.com/terraform-linters/tflint). Sous Windows, le pont "
    "WSL les cherche dans /opt/forge-tools/bin ; un lien symbolique suffit."
)

#: Variable d'environnement designant un cache local de providers. Sans elle,
#: `terraform init` retelecharge chaque provider pour **chaque** racine
#: d'environnement : trois environnements, trois fois le meme telechargement.
CACHE_ENV_VAR = "FORGE_TF_PLUGIN_CACHE"


def _environnement() -> tuple[tuple[str, str], ...]:
    """Variables d'environnement passees a terraform et tflint.

    `TF_IN_AUTOMATION` retire des messages qui invitent a lancer d'autres
    commandes — sans objet ici. `CHECKPOINT_DISABLE` supprime l'appel a
    HashiCorp qui verifie s'il existe une version plus recente : c'est le seul
    acces reseau que ces commandes font sans y etre obligees.
    """
    variables: dict[str, str] = {
        "NO_COLOR": "1",
        "TF_IN_AUTOMATION": "1",
        "CHECKPOINT_DISABLE": "1",
    }
    cache = os.environ.get(CACHE_ENV_VAR, "")
    # Terraform echoue si le repertoire de cache n'existe pas : mieux vaut s'en
    # passer que faire echouer la validation pour un chemin mal renseigne.
    if cache and Path(cache).is_dir():
        variables["TF_PLUGIN_CACHE_DIR"] = cache
    return tuple(sorted(variables.items()))


def commands(spec: Any, outdir: Path) -> list[Command]:
    """Commandes validant le projet genere, dans l'ordre d'execution."""
    env_commun = _environnement()
    liste: list[Command] = [
        Command(
            label="terraform fmt",
            tool="terraform",
            argv=("fmt", "-check", "-recursive", "-diff", "-no-color"),
            cwd=outdir,
            timeout=TIMEOUT,
            env=env_commun,
            install_hint=INSTALL_HINT,
            requires_linux=True,
        )
    ]

    for env in spec.service.environments:
        racine = outdir / tree.environment_dir(env.name)
        liste.append(
            Command(
                label=f"terraform init ({env.name})",
                tool="terraform",
                argv=("init", "-backend=false", "-input=false", "-no-color"),
                cwd=racine,
                timeout=TIMEOUT,
                env=env_commun,
                install_hint=INSTALL_HINT,
                requires_linux=True,
            )
        )
        liste.append(
            Command(
                label=f"terraform validate ({env.name})",
                tool="terraform",
                argv=("validate", "-no-color"),
                cwd=racine,
                timeout=TIMEOUT,
                env=env_commun,
                install_hint=INSTALL_HINT,
                requires_linux=True,
            )
        )

    liste.append(
        Command(
            label="tflint",
            tool="tflint",
            argv=("--recursive", "--no-color"),
            cwd=outdir,
            timeout=TIMEOUT,
            env=env_commun,
            install_hint=INSTALL_HINT,
            requires_linux=True,
        )
    )
    return liste
