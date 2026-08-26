"""Projection de la specification et du contexte vers le dict `domain`.

Le seul `forge_answers` du projet qui declare le parametre `context` : c'est ce
qui distingue ce domaine des autres, et c'est tout ce qui l'en distingue. Le
contexte ne parle que le vocabulaire du contrat — `DomainInfo`, `Command`,
`Projection` — de sorte qu'aucun nom de domaine n'a a etre connu ici.
"""

from __future__ import annotations

from typing import Any

from forge.plugins.pipeline import jobs as jobs_module
from forge.plugins.pipeline import tree
from forge.plugins_api.types import GenerationContext, Issue

#: Nom du domaine, employe pour qu'il s'exclue lui-meme la ou il le doit.
DOMAIN_NAME = "pipeline"


def build(spec: Any, context: GenerationContext | None = None) -> dict[str, Any]:
    """Construit le dict `domain` passe a copier pour le domaine pipeline."""
    contexte = context or GenerationContext()
    pipeline = spec.pipeline
    service = spec.service

    declares = tuple(env.name for env in service.environments)
    production = next((env.name for env in service.environments if env.production), "")
    deployes = pipeline.deployed_environments(declares)

    validations = jobs_module.validate_jobs(contexte, pipeline.provider.value)
    construction = (
        jobs_module.build_job(pipeline.build, service.name, pipeline.provider.value)
        if pipeline.build is not None
        else None
    )
    if construction is not None:
        construction.needs = [job.key for job in validations]

    prealables = [job.key for job in validations]
    if construction is not None:
        prealables.append(construction.key)
    deploiements = jobs_module.deploy_jobs(
        contexte,
        deployes,
        production,
        pipeline.provider.value,
        manual_for_production=(
            pipeline.deploy.manual_for_production if pipeline.deploy else True
        ),
        sequential=pipeline.deploy.sequential if pipeline.deploy else True,
        needs=prealables,
    )

    tous = validations + ([construction] if construction else []) + deploiements
    inconnus = sorted({outil for job in tous for outil in job.unknown_tools})

    return {
        # -- identite du pipeline ----------------------------------------------
        "provider": pipeline.provider.value,
        "is_github": pipeline.is_github,
        "is_gitlab": pipeline.is_gitlab,
        "runner": pipeline.runner,
        "workflow_path": tree.workflow_path(spec),
        "workflow_name": service.name,
        "provider_slots": tree.provider_slots(spec),
        # -- declenchement ------------------------------------------------------
        "trigger": {
            "branches": list(pipeline.trigger.branches),
            "on_pull_request": pipeline.trigger.on_pull_request,
            "on_tag": pipeline.trigger.on_tag,
        },
        "default_branch": pipeline.trigger.branches[0],
        # -- jobs ----------------------------------------------------------------
        "validate_jobs": [job.as_dict() for job in validations],
        "build_job": construction.as_dict() if construction else None,
        "deploy_jobs": [job.as_dict() for job in deploiements],
        "jobs": [job.as_dict() for job in tous],
        # -- ce que le pipeline sait des autres domaines --------------------------
        "domains": [
            {
                "name": sommaire.name,
                "title": sommaire.info.title,
                "summary": sommaire.info.summary,
                "outdir": sommaire.info.outdir,
                "validator_count": len(sommaire.validators),
                "deploys": [nom for nom, _ in sommaire.deployments],
            }
            for sommaire in contexte.domains
        ],
        "undeployed": jobs_module.undeployed(contexte, deployes, DOMAIN_NAME),
        "unknown_tools": inconnus,
        "tools": list(contexte.tools()),
        # -- environnements --------------------------------------------------------
        "env_names": list(declares),
        "deploy_environments": list(deployes),
        "production": production,
        # -- documentation ----------------------------------------------------------
        "expected_paths": tree.expected_paths(spec),
    }


# ---------------------------------------------------------------------------
# Controles croises
# ---------------------------------------------------------------------------


def cross_check(spec: Any) -> list[Issue]:
    """Controles que `PipelineSpec` ne peut pas faire : elle ne voit pas `service:`."""
    pipeline = getattr(spec, "pipeline", None)
    if pipeline is None:
        return []

    issues: list[Issue] = []
    issues.extend(_check_deploy_environments(spec, pipeline))
    issues.extend(_check_production_guard(spec, pipeline))
    issues.extend(_check_registry_credentials(pipeline))
    return issues


def _check_deploy_environments(spec: Any, pipeline: Any) -> list[Issue]:
    """Refuse un environnement de deploiement absent de `service.environments`."""
    if pipeline.deploy is None:
        return []
    connus = {env.name for env in spec.service.environments}
    declares = ", ".join(env.name for env in spec.service.environments)
    return [
        Issue(
            level="error",
            message=(
                f"pipeline.deploy.environments cite '{nom}', absent de "
                f"service.environments (declares : {declares})."
            ),
            hint=(
                f"Ajoutez un environnement '{nom}' a service.environments, ou "
                f"retirez '{nom}' de pipeline.deploy.environments."
            ),
            domains=(DOMAIN_NAME,),
        )
        for nom in sorted(set(pipeline.deploy.environments) - connus)
    ]


def _check_production_guard(spec: Any, pipeline: Any) -> list[Issue]:
    """Signale une production deployee sans aucune garde humaine.

    Ce n'est pas une erreur — un service jetable peut vouloir exactement cela —
    mais c'est une decision, et une decision qui ne doit pas se prendre par
    defaut.
    """
    if pipeline.deploy is None or pipeline.deploy.manual_for_production:
        return []
    declares = tuple(env.name for env in spec.service.environments)
    production = next((env.name for env in spec.service.environments if env.production), "")
    if not production or production not in pipeline.deployed_environments(declares):
        return []
    return [
        Issue(
            level="warning",
            message=(
                f"pipeline.deploy deploie l'environnement de production "
                f"'{production}' sans approbation humaine : tout push accepte "
                "sur la branche par defaut partira en production."
            ),
            hint="Repassez pipeline.deploy.manual_for_production a true.",
            domains=(DOMAIN_NAME,),
        )
    ]


def _check_registry_credentials(pipeline: Any) -> list[Issue]:
    """Signale une publication d'image vers un registre que le jeton n'ouvre pas.

    Le jeton fourni d'office par GitHub n'ouvre que `ghcr.io` ; celui de GitLab
    n'ouvre que le registre du projet. Publier ailleurs demande un secret que
    forge ne peut ni deviner ni ecrire.
    """
    build = pipeline.build
    if build is None or not build.push:
        return []
    attendu = "ghcr.io" if pipeline.is_github else "$CI_REGISTRY"
    if build.registry == attendu:
        return []
    return [
        Issue(
            level="warning",
            message=(
                f"pipeline.build publie vers '{build.registry}', que le jeton "
                f"fourni d'office par {pipeline.provider.value} n'ouvre pas "
                f"(il n'ouvre que '{attendu}')."
            ),
            hint=(
                "Declarez un secret d'acces au registre dans les reglages de la "
                "CI et completez l'etape de connexion du pipeline genere ; forge "
                "n'ecrit jamais d'identifiant."
            ),
            domains=(DOMAIN_NAME,),
        )
    ]
