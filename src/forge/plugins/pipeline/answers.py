"""Projection of the specification and of the context into the `domain` dict.

The only `forge_answers` of the project that declares the `context` parameter:
that is what distinguishes this domain from the others, and it is all that
distinguishes it. The context only speaks the vocabulary of the contract —
`DomainInfo`, `Command`, `Projection` — so that no domain name has to be known
here.
"""

from __future__ import annotations

from typing import Any

from forge.plugins.pipeline import jobs as jobs_module
from forge.plugins.pipeline import tree
from forge.plugins_api.types import GenerationContext, Issue

#: Name of the domain, used so that it excludes itself where it must.
DOMAIN_NAME = "pipeline"


def build(spec: Any, context: GenerationContext | None = None) -> dict[str, Any]:
    """Build the `domain` dict passed to copier for the pipeline domain."""
    generation = context or GenerationContext()
    pipeline = spec.pipeline
    service = spec.service

    declared = tuple(env.name for env in service.environments)
    production = next((env.name for env in service.environments if env.production), "")
    deployed = pipeline.deployed_environments(declared)

    validations = jobs_module.validate_jobs(generation, pipeline.provider.value)
    build_step = (
        jobs_module.build_job(pipeline.build, service.name, pipeline.provider.value)
        if pipeline.build is not None
        else None
    )
    if build_step is not None:
        build_step.needs = [job.key for job in validations]

    prerequisites = [job.key for job in validations]
    if build_step is not None:
        prerequisites.append(build_step.key)
    deployments = jobs_module.deploy_jobs(
        generation,
        deployed,
        production,
        pipeline.provider.value,
        manual_for_production=(
            pipeline.deploy.manual_for_production if pipeline.deploy else True
        ),
        sequential=pipeline.deploy.sequential if pipeline.deploy else True,
        needs=prerequisites,
    )

    all_jobs = validations + ([build_step] if build_step else []) + deployments
    unknown = sorted({tool for job in all_jobs for tool in job.unknown_tools})

    return {
        # -- identity of the pipeline ------------------------------------------
        "provider": pipeline.provider.value,
        "is_github": pipeline.is_github,
        "is_gitlab": pipeline.is_gitlab,
        "runner": pipeline.runner,
        "workflow_path": tree.workflow_path(spec),
        "workflow_name": service.name,
        "provider_slots": tree.provider_slots(spec),
        # -- triggering ---------------------------------------------------------
        "trigger": {
            "branches": list(pipeline.trigger.branches),
            "on_pull_request": pipeline.trigger.on_pull_request,
            "on_tag": pipeline.trigger.on_tag,
        },
        "default_branch": pipeline.trigger.branches[0],
        # -- jobs ----------------------------------------------------------------
        "validate_jobs": [job.as_dict() for job in validations],
        "build_job": build_step.as_dict() if build_step else None,
        "deploy_jobs": [job.as_dict() for job in deployments],
        "jobs": [job.as_dict() for job in all_jobs],
        # -- what the pipeline knows about the other domains ----------------------
        "domains": [
            {
                "name": summary.name,
                "title": summary.info.title,
                "summary": summary.info.summary,
                "outdir": summary.info.outdir,
                "validator_count": len(summary.validators),
                "deploys": [name for name, _ in summary.deployments],
            }
            for summary in generation.domains
        ],
        "undeployed": jobs_module.undeployed(generation, deployed, DOMAIN_NAME),
        "unknown_tools": unknown,
        "tools": list(generation.tools()),
        # -- environments --------------------------------------------------------
        "env_names": list(declared),
        "deploy_environments": list(deployed),
        "production": production,
        # -- documentation ----------------------------------------------------------
        "expected_paths": tree.expected_paths(spec),
    }


# ---------------------------------------------------------------------------
# Cross-checks
# ---------------------------------------------------------------------------


def cross_check(spec: Any) -> list[Issue]:
    """Checks `PipelineSpec` cannot do: it does not see `service:`."""
    pipeline = getattr(spec, "pipeline", None)
    if pipeline is None:
        return []

    issues: list[Issue] = []
    issues.extend(_check_deploy_environments(spec, pipeline))
    issues.extend(_check_production_guard(spec, pipeline))
    issues.extend(_check_registry_credentials(pipeline))
    return issues


def _check_deploy_environments(spec: Any, pipeline: Any) -> list[Issue]:
    """Refuse a deployment environment absent from `service.environments`."""
    if pipeline.deploy is None:
        return []
    known = {env.name for env in spec.service.environments}
    declared = ", ".join(env.name for env in spec.service.environments)
    return [
        Issue(
            level="error",
            message=(
                f"pipeline.deploy.environments quotes '{name}', absent from "
                f"service.environments (declared: {declared})."
            ),
            hint=(
                f"Add an environment '{name}' to service.environments, or remove "
                f"'{name}' from pipeline.deploy.environments."
            ),
            domains=(DOMAIN_NAME,),
        )
        for name in sorted(set(pipeline.deploy.environments) - known)
    ]


def _check_production_guard(spec: Any, pipeline: Any) -> list[Issue]:
    """Report a production deployed with no human guard at all.

    It is not an error — a disposable service may want exactly that — but it is a
    decision, and a decision that must not be taken by default.
    """
    if pipeline.deploy is None or pipeline.deploy.manual_for_production:
        return []
    declared = tuple(env.name for env in spec.service.environments)
    production = next((env.name for env in spec.service.environments if env.production), "")
    if not production or production not in pipeline.deployed_environments(declared):
        return []
    return [
        Issue(
            level="warning",
            message=(
                f"pipeline.deploy deploys the production environment "
                f"'{production}' with no human approval: every push accepted on "
                "the default branch will go to production."
            ),
            hint="Switch pipeline.deploy.manual_for_production back to true.",
            domains=(DOMAIN_NAME,),
        )
    ]


def _check_registry_credentials(pipeline: Any) -> list[Issue]:
    """Report an image publication to a registry the token does not open.

    The token GitHub supplies out of the box only opens `ghcr.io`; the GitLab one
    only opens the registry of the project. Publishing elsewhere requires a secret
    forge can neither guess nor write.
    """
    build = pipeline.build
    if build is None or not build.push:
        return []
    expected = "ghcr.io" if pipeline.is_github else "$CI_REGISTRY"
    if build.registry == expected:
        return []
    return [
        Issue(
            level="warning",
            message=(
                f"pipeline.build publishes to '{build.registry}', which the token "
                f"{pipeline.provider.value} supplies out of the box does not open "
                f"(it only opens '{expected}')."
            ),
            hint=(
                "Declare a registry access secret in the CI settings and complete "
                "the login step of the generated pipeline; forge never writes a "
                "credential."
            ),
            domains=(DOMAIN_NAME,),
        )
    ]
