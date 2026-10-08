"""Terraform domain plugin: implementation of the forge hooks.

Like the two other plugins, this module holds no logic: it wires the contract
(`DESIGN.md` §2.2) onto the modules that do the work.

It is the first domain of the project that comes from no legacy tool. What it
demonstrates — or does not — is that the plugin contract is enough to add a domain
without touching the core. One single line of the core changes: the
`BUILTIN_PLUGINS` entry.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge.interview.prompter import Prompter
from forge.plugins.terraform import answers as answers_module
from forge.plugins.terraform import validators as validators_module
from forge.plugins.terraform.catalog.registry import all_families
from forge.plugins.terraform.spec import TerraformSpec
from forge.plugins_api.hookspecs import hookimpl
from forge.plugins_api.types import CatalogEntry, Command, DomainInfo, Issue, Projection
from forge.spec.service import ServiceSpec


@hookimpl
def forge_domain() -> DomainInfo:
    return DomainInfo(
        name="terraform",
        title="Terraform",
        summary="Infrastructure foundation: namespace, budget, deployment identity",
        # The base layer goes first: it is what creates the partition the other
        # domains put something into.
        deploy_order=10,
    )


@hookimpl
def forge_spec_model() -> type[TerraformSpec]:
    return TerraformSpec


@hookimpl
def forge_template_subdir() -> str:
    return "src/forge/plugins/terraform/template"


@hookimpl
def forge_answers(spec: Any) -> dict[str, Any]:
    return answers_module.build(spec)


@hookimpl
def forge_validators(spec: Any, outdir: Path) -> list[Command]:
    return validators_module.commands(spec, outdir)


@hookimpl
def forge_deploy(spec: Any, outdir: Path, environment: str) -> list[Command]:
    """How this domain deploys itself. The core never runs it."""
    return validators_module.deploy_commands(spec, outdir, environment)


@hookimpl
def forge_check_spec(spec: Any) -> list[Issue]:
    """Checks the sub-model cannot do: it does not see `service:`."""
    if getattr(spec, "terraform", None) is None:
        return []
    return answers_module.cross_check(spec)


@hookimpl
def forge_projection(spec: Any) -> Projection:
    """What the Terraform domain claims to produce.

    One single facet, and that is deliberate: `namespaces`, from the **shared
    vocabulary** (`forge.validate.consistency.FACET_VOCABULARY`). It is exactly
    the one the Helm domain declares, and where the two domains have to agree:
    Terraform creates the partition, Helm deploys into it. A disagreement means
    the chart targets a namespace nobody creates.

    Phase 5 had established the mechanism without having a real disagreement to
    show — Ansible and Helm share no facet of that kind. This plugin gives it its
    first real case.
    """
    projection = answers_module.build(spec)
    namespaces = sorted({env["namespace"] for env in projection["environments"]})
    return Projection(
        service_name=spec.service.name,
        environments=tuple(env.name for env in spec.service.environments),
        labels=dict(spec.service.labels),
        facets={"namespaces": tuple(namespaces)},
    )


@hookimpl
def forge_catalog() -> list[CatalogEntry]:
    """Resource families browsable through `forge catalog terraform`."""
    return [
        CatalogEntry(
            name=family.name,
            summary=family.summary,
            details=_details(family),
            options=family.option_descriptions(),
        )
        for family in all_families()
    ]


def _details(family: Any) -> str:
    """Long description of a family: its role, what it places, its traps."""
    lines = [
        family.details or family.summary,
        "",
        f"Places: {', '.join(family.resources)}",
        f"Providers: {', '.join(family.providers)}",
    ]
    if family.outputs:
        lines.append(f"Outputs: {', '.join(sorted(family.outputs))}")
    if family.traps:
        lines += ["", "Points to watch:"]
        lines += [f"  - {trap}" for trap in family.traps]
    return "\n".join(lines)


@hookimpl
def forge_interview(prompter: Prompter, service: ServiceSpec) -> dict[str, Any] | None:
    from forge.plugins.terraform import interview

    return interview.run(prompter, service)
