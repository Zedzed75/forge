"""Commandes de validation du chart Helm genere.

Portage de la partie « quoi lancer » de `helm_forge.validation.runner`
(MIGRATION.md §4) : l'execution, le delai, la detection d'outil manquant, le
chainage de stdin et le rapport appartiennent au coeur
(`forge.validate.runner`). Ici, uniquement la liste des commandes.

Trois verifications par environnement, dans cet ordre :

1. `helm lint` — coherence du chart et de ses values ;
2. `helm template` — le chart se rend reellement ;
3. `kubeconform -strict` — les manifestes rendus sont conformes aux schemas de
   l'API Kubernetes de la version visee.

La troisieme lit le **rendu** de la deuxieme : c'est le `stdin_from` du contrat
`Command`. Si `helm template` echoue, le coeur saute `kubeconform` plutot que de
le lancer sur une entree vide — il n'aurait rien a valider.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from forge.plugins_api.types import Command

#: Delai maximal accorde a une commande, en secondes.
TIMEOUT = 300

#: Message d'installation commun aux deux outils.
INSTALL_HINT = (
    "installez helm (https://helm.sh/docs/intro/install/) et kubeconform "
    "(https://github.com/yannh/kubeconform). Sous Windows, le pont WSL les "
    "cherche dans /opt/forge-tools/bin ; un lien symbolique suffit."
)

#: Variable d'environnement designant un cache de schemas kubeconform local.
#: `kubeconform` telecharge sinon les schemas a chaque execution : en CI sans
#: acces reseau, ou sur un poste hors ligne, la validation echouerait pour une
#: raison sans rapport avec le chart.
SCHEMAS_ENV_VAR = "FORGE_KUBECONFORM_SCHEMAS"


def _values(chart: str, env_name: str) -> tuple[str, ...]:
    """Options `--values`, dans l'ordre de priorite de Helm.

    Les valeurs communes d'abord, la surcharge d'environnement ensuite : Helm
    applique les fichiers de gauche a droite, le dernier gagne.
    """
    return (
        "--values",
        f"{chart}/values.yaml",
        "--values",
        f"{chart}/values-{env_name}.yaml",
    )


def _environnement() -> tuple[tuple[str, str], ...]:
    """Variables d'environnement passees aux outils."""
    variables: dict[str, str] = {"NO_COLOR": "1"}
    schemas = os.environ.get(SCHEMAS_ENV_VAR, "")
    if schemas:
        variables["KUBECONFORM_SCHEMA_LOCATION"] = schemas
    return tuple(sorted(variables.items()))


def _namespaces(spec: Any) -> dict[str, str]:
    """Namespace derive de chaque environnement, indexe par nom.

    La derivation appartient a `derive.py` ; on la relit ici plutot que de la
    refaire, pour que `helm template` s'execute dans le namespace que le chart
    annonce lui-meme. Calcule une seule fois, pas une fois par environnement.
    """
    from forge.plugins.helm import answers

    return {
        env.get("name"): env.get("namespace") or spec.service.name
        for env in answers.build(spec).get("environments", [])
    }


def commands(spec: Any, outdir: Path) -> list[Command]:
    """Commandes validant le chart genere, dans l'ordre d'execution."""
    helm = spec.helm
    chart = f"charts/{spec.service.name}"
    version = getattr(helm.kubernetes, "full_version", None) or f"{helm.kubernetes.version}.0"
    env_commun = _environnement()
    namespaces = _namespaces(spec)

    liste: list[Command] = []
    for env in spec.service.environments:
        valeurs = _values(chart, env.name)
        rendu = f"helm template ({env.name})"
        liste.append(
            Command(
                label=f"helm lint ({env.name})",
                tool="helm",
                argv=("lint", chart, *valeurs),
                cwd=outdir,
                timeout=TIMEOUT,
                env=env_commun,
                install_hint=INSTALL_HINT,
                requires_linux=True,
            )
        )
        liste.append(
            Command(
                label=rendu,
                tool="helm",
                argv=(
                    "template",
                    spec.service.name,
                    chart,
                    "--namespace",
                    namespaces.get(env.name, spec.service.name),
                    *valeurs,
                ),
                cwd=outdir,
                timeout=TIMEOUT,
                env=env_commun,
                install_hint=INSTALL_HINT,
                requires_linux=True,
            )
        )
        liste.append(
            Command(
                label=f"kubeconform -strict ({env.name})",
                tool="kubeconform",
                argv=(
                    "-strict",
                    "-summary",
                    "-kubernetes-version",
                    version,
                    "-schema-location",
                    "default",
                    "-",
                ),
                cwd=outdir,
                timeout=TIMEOUT,
                env=env_commun,
                stdin_from=rendu,
                install_hint=INSTALL_HINT,
                requires_linux=True,
            )
        )
    return liste


#: Delai laisse a `helm upgrade --wait` avant de considerer le deploiement en
#: echec. Helm attend que chaque ressource soit prete ; sans borne, un pipeline
#: reste bloque sur un pod qui ne demarrera jamais.
DEPLOY_TIMEOUT = "10m"


def deploy_commands(spec: Any, outdir: Path, environment: str) -> list[Command]:
    """Commandes deployant le chart dans `environment` (hook `forge_deploy`).

    Le coeur ne les execute jamais : elles sont ecrites dans un pipeline.

    `--atomic` implique `--wait` et **defait** la release si le deploiement
    echoue : sans lui, un `upgrade` rate laisse la release dans un etat
    intermediaire, et le deploiement suivant echoue pour une raison sans rapport.
    """
    helm = spec.helm
    chart = f"charts/{spec.service.name}"
    namespace = _namespaces(spec).get(environment, spec.service.name)
    argv = [
        "upgrade",
        "--install",
        spec.service.name,
        chart,
        "--namespace",
        namespace,
    ]
    if helm.create_namespace:
        argv.append("--create-namespace")
    argv += [
        *_values(chart, environment),
        "--atomic",
        "--timeout",
        DEPLOY_TIMEOUT,
    ]
    return [
        Command(
            label=f"helm upgrade --install ({environment})",
            tool="helm",
            argv=tuple(argv),
            cwd=outdir,
            timeout=TIMEOUT,
            env=_environnement(),
            install_hint=INSTALL_HINT,
            requires_linux=True,
        )
    ]
