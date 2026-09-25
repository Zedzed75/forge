"""Helm domain plugin: implementation of the forge hooks.

This module holds no logic: it wires the plugin contract (`DESIGN.md` §2.2) onto
the modules that do the work — `spec` for the model, `answers` for the projection
towards copier, `validators` for the external commands, `catalog` for the resource
families, `interview` for the interview.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge.interview.prompter import Prompter
from forge.plugins.helm import answers as answers_module
from forge.plugins.helm import validators as validators_module
from forge.plugins.helm.catalog.registry import all_families
from forge.plugins.helm.spec import HelmSpec
from forge.plugins_api.hookspecs import hookimpl
from forge.plugins_api.types import CatalogEntry, Command, DomainInfo, Issue, Projection
from forge.spec.service import ServiceSpec


@hookimpl
def forge_domain() -> DomainInfo:
    return DomainInfo(
        name="helm",
        title="Helm",
        summary="Complete Helm chart: commented values, templates and strict validation",
    )


@hookimpl
def forge_spec_model() -> type[HelmSpec]:
    return HelmSpec


@hookimpl
def forge_template_subdir() -> str:
    return "src/forge/plugins/helm/template"


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
    if getattr(spec, "helm", None) is None:
        return []
    return answers_module.cross_check(spec)


@hookimpl
def forge_projection(spec: Any) -> Projection:
    """What the Helm domain claims to produce.

    The facet names belong to a **vocabulary shared** between domains (cf.
    `forge.validate.consistency.FACET_VOCABULARY`): `ingress_hosts` designates the
    domain names the service is reachable under from the outside, and not the
    machines of an inventory — Ansible declares `inventory_hosts`, which is not the
    same thing. Having them both named `hosts` produced a false positive on every
    two-domain specification: that is the first defect the meeting of two real
    domains revealed.
    """
    projection = answers_module.build(spec)
    hosts = sorted(
        {
            override["ingress_host"]
            for env in projection["environments"]
            for override in env["components"].values()
            if override.get("ingress_host")
        }
    )
    namespaces = sorted({env["namespace"] for env in projection["environments"]})
    return Projection(
        service_name=spec.service.name,
        environments=tuple(env.name for env in spec.service.environments),
        labels=dict(spec.service.labels),
        facets={"ingress_hosts": tuple(hosts), "namespaces": tuple(namespaces)},
    )


@hookimpl
def forge_catalog() -> list[CatalogEntry]:
    """Resource families browsable through `forge catalog helm`."""
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
    """Long description of a family: its role, then its traps.

    The traps are displayed to the user because they explain choices of the
    generated chart that would look arbitrary without them.
    """
    lines = [
        family.details or family.summary,
        "",
        f"Produces: {family.kind} ({family.api_version})",
    ]
    if family.requires:
        lines.append(f"Requires: {', '.join(family.requires)}")
    if family.traps:
        lines += ["", "Points to watch:"]
        lines += [f"  - {trap}" for trap in family.traps]
    return "\n".join(lines)


@hookimpl
def forge_interview(prompter: Prompter, service: ServiceSpec) -> dict[str, Any] | None:
    from forge.plugins.helm import interview

    return interview.run(prompter, service)
