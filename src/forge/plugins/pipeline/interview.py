"""Entretien du domaine pipeline.

L'entretien le plus court du projet, et c'est le signe que le domaine est bien
cadre : presque tout se deduit des autres sections. Ce qui reste tient en quatre
questions — quel outil, sur quoi il se declenche, construit-on une image,
deploie-t-on.

Conformement a l'arbitrage R7 (PLAN.md), retourner `None` signifie « il n'y a
rien a generer » et non « l'utilisateur refuse le domaine » : ici, un pipeline
qui ne validerait rien, ne construirait rien et ne deploierait rien.
"""

from __future__ import annotations

from typing import Any

from forge.interview.prompter import Prompter
from forge.plugins.pipeline.enums import Provider
from forge.spec.service import ServiceSpec

#: Libelles des outils de CI, dans l'ordre propose.
PROVIDER_CHOICES: list[tuple[str, str]] = [
    (Provider.GITHUB.value, "GitHub Actions — .github/workflows/ci.yml"),
    (Provider.GITLAB.value, "GitLab CI — .gitlab-ci.yml"),
]


def run(prompter: Prompter, service: ServiceSpec) -> dict[str, Any] | None:
    """Conduit l'entretien et retourne la section `pipeline:` de forge.yml."""
    prompter.note(
        "Le pipeline se deduit des autres domaines : un job de validation par "
        "domaine demande, avec leurs propres commandes. Restent quatre choix."
    )

    provider = prompter.select(
        "Quel outil d'integration continue ?", PROVIDER_CHOICES, Provider.GITHUB.value
    )
    section: dict[str, Any] = {"provider": provider}

    branche = prompter.text("Branche principale", default="main")
    trigger: dict[str, Any] = {}
    if branche != "main":
        trigger["branches"] = [branche]
    if not prompter.confirm("Declencher aussi sur les propositions de fusion ?", default=True):
        trigger["on_pull_request"] = False
    if trigger:
        section["trigger"] = trigger

    build = _ask_build(prompter, service, provider)
    if build is not None:
        section["build"] = build

    deploy = _ask_deploy(prompter, service)
    if deploy is not None:
        section["deploy"] = deploy

    return section


def _ask_build(prompter: Prompter, service: ServiceSpec, provider: str) -> dict[str, Any] | None:
    """Construction d'image. Tous les services ne sont pas conteneurises."""
    if not prompter.confirm("Construire et publier une image de conteneur ?", default=False):
        return None
    defaut = "ghcr.io" if provider == Provider.GITHUB.value else "$CI_REGISTRY"
    build: dict[str, Any] = {}
    registre = prompter.text("Registre d'images", default=defaut)
    if registre != "ghcr.io":
        build["registry"] = registre
    depot = prompter.text("Depot de l'image dans le registre", default=service.name)
    if depot != service.name:
        build["image"] = depot
    prompter.note(
        "Aucun identifiant de registre n'est ecrit : le pipeline emploie le "
        "jeton que l'outil de CI fournit deja."
    )
    return build


def _ask_deploy(prompter: Prompter, service: ServiceSpec) -> dict[str, Any] | None:
    """Deploiement. Se limiter a valider est un choix legitime, et le plus sur."""
    if not prompter.confirm("Deployer depuis le pipeline ?", default=False):
        return None

    choix = [(env.name, f"{env.name}{' (production)' if env.production else ''}") for env in service.environments]
    defaut = [env.name for env in service.environments if not env.production]
    retenus = prompter.checkbox("Quels environnements deployer ?", choix, defaut)
    if not retenus:
        prompter.note("Aucun environnement retenu : le pipeline se limitera a valider.")
        return None

    deploy: dict[str, Any] = {}
    if sorted(retenus) != sorted(env.name for env in service.environments):
        deploy["environments"] = [
            env.name for env in service.environments if env.name in set(retenus)
        ]

    production = next((env.name for env in service.environments if env.production), "")
    if production in retenus:
        garde = prompter.confirm(
            f"Exiger une approbation humaine avant de deployer '{production}' ?",
            default=True,
        )
        if not garde:
            deploy["manual_for_production"] = False
    return deploy
