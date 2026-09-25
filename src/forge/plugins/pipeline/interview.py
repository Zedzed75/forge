"""Interview for the pipeline domain.

The shortest interview in the project, and that is the sign the domain is well
scoped: almost everything is derived from the other sections. What is left fits
in four questions — which tool, what triggers it, do we build an image, do we
deploy.

Per arbitration R7 (PLAN.md), returning `None` means "there is nothing to
generate" and not "the user declines the domain": here, a pipeline that would
validate nothing, build nothing and deploy nothing.
"""

from __future__ import annotations

from typing import Any

from forge.interview.prompter import Prompter
from forge.plugins.pipeline.enums import Provider
from forge.spec.service import ServiceSpec

#: Labels of the CI tools, in the order offered.
PROVIDER_CHOICES: list[tuple[str, str]] = [
    (Provider.GITHUB.value, "GitHub Actions — .github/workflows/ci.yml"),
    (Provider.GITLAB.value, "GitLab CI — .gitlab-ci.yml"),
]


def run(prompter: Prompter, service: ServiceSpec) -> dict[str, Any] | None:
    """Conduct the interview and return the `pipeline:` section of forge.yml."""
    prompter.note(
        "The pipeline is derived from the other domains: one validation job per "
        "requested domain, with their own commands. Four choices remain."
    )

    provider = prompter.select(
        "Which continuous integration tool?", PROVIDER_CHOICES, Provider.GITHUB.value
    )
    section: dict[str, Any] = {"provider": provider}

    branch = prompter.text("Main branch", default="main")
    trigger: dict[str, Any] = {}
    if branch != "main":
        trigger["branches"] = [branch]
    if not prompter.confirm("Also trigger on pull requests?", default=True):
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
    """Image build. Not every service is containerised."""
    if not prompter.confirm("Build and publish a container image?", default=False):
        return None
    default_registry = "ghcr.io" if provider == Provider.GITHUB.value else "$CI_REGISTRY"
    build: dict[str, Any] = {}
    registry = prompter.text("Image registry", default=default_registry)
    if registry != "ghcr.io":
        build["registry"] = registry
    repository = prompter.text("Image repository in the registry", default=service.name)
    if repository != service.name:
        build["image"] = repository
    prompter.note(
        "No registry credential is written: the pipeline uses the token the CI "
        "tool already provides."
    )
    return build


def _ask_deploy(prompter: Prompter, service: ServiceSpec) -> dict[str, Any] | None:
    """Deployment. Validating only is a legitimate choice, and the safest one."""
    if not prompter.confirm("Deploy from the pipeline?", default=False):
        return None

    choices = [(env.name, f"{env.name}{' (production)' if env.production else ''}") for env in service.environments]
    default_envs = [env.name for env in service.environments if not env.production]
    selected = prompter.checkbox("Which environments should be deployed?", choices, default_envs)
    if not selected:
        prompter.note("No environment retained: the pipeline will only validate.")
        return None

    deploy: dict[str, Any] = {}
    if sorted(selected) != sorted(env.name for env in service.environments):
        deploy["environments"] = [
            env.name for env in service.environments if env.name in set(selected)
        ]

    production = next((env.name for env in service.environments if env.production), "")
    if production in selected:
        gate = prompter.confirm(
            f"Require a human approval before deploying '{production}'?",
            default=True,
        )
        if not gate:
            deploy["manual_for_production"] = False
    return deploy
