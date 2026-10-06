"""Monitoring domain plugin: implementation of the forge hooks.

Like the three others, this module holds no logic: it wires the contract
(`DESIGN.md` §2.2) onto the modules that do the work.

The domain is **self-contained**: it reads no other section of forge.yml. Its
meeting with the other domains happens through the facets, compared by
`forge validate` — `namespaces` with Terraform and Helm, `ingress_hosts` with
Helm. A chart exposing `boutique.example.net` while the probe looks at
`api.example.net` is a defect neither of the two domains can see on its own.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge.interview.prompter import Prompter
from forge.plugins.monitoring import answers as answers_module
from forge.plugins.monitoring import validators as validators_module
from forge.plugins.monitoring.catalog.registry import all_families
from forge.plugins.monitoring.spec import MonitoringSpec
from forge.plugins_api.hookspecs import hookimpl
from forge.plugins_api.types import CatalogEntry, Command, DomainInfo, Issue, Projection
from forge.spec.service import ServiceSpec


@hookimpl
def forge_domain() -> DomainInfo:
    return DomainInfo(
        name="monitoring",
        title="Monitoring",
        summary="Metric collection, alert rules and alert unit tests",
    )


@hookimpl
def forge_spec_model() -> type[MonitoringSpec]:
    return MonitoringSpec


@hookimpl
def forge_template_subdir() -> str:
    return "src/forge/plugins/monitoring/template"


@hookimpl
def forge_answers(spec: Any) -> dict[str, Any]:
    return answers_module.build(spec)


@hookimpl
def forge_validators(spec: Any, outdir: Path) -> list[Command]:
    return validators_module.commands(spec, outdir)


@hookimpl
def forge_check_spec(spec: Any) -> list[Issue]:
    """Checks the sub-model cannot do: it does not see `service:`."""
    if getattr(spec, "monitoring", None) is None:
        return []
    return answers_module.cross_check(spec)


@hookimpl
def forge_projection(spec: Any) -> Projection:
    """What the monitoring domain claims to watch.

    Two facets of the **shared vocabulary**
    (`forge.validate.consistency.FACET_VOCABULARY`):

    * `namespaces` — the partitions observed. Terraform creates them, Helm deploys
      into them, monitoring watches them: all three must name the same ones.
    * `ingress_hosts` — the hosts probed from the outside. It is the facet Helm
      declares for its Ingresses. Watching a host nobody exposes, or exposing a
      host nobody probes, are two symmetrical mistakes no domain can see on its
      own.

    `environments` does not copy `service.environments`: an environment with no
    declared target is not materialised by this domain, and saying so is more
    useful than pretending to watch it.
    """
    monitoring = spec.monitoring
    materialised = tuple(
        env.name
        for env in spec.service.environments
        if monitoring.overrides(env.name).targets
    )
    namespaces = sorted(
        {
            monitoring.overrides(env.name).namespace or spec.service.name
            for env in spec.service.environments
        }
    )
    return Projection(
        service_name=spec.service.name,
        environments=materialised,
        labels=dict(spec.service.labels),
        facets={
            "namespaces": tuple(namespaces),
            "ingress_hosts": answers_module.probe_hosts(spec),
        },
    )


@hookimpl
def forge_catalog() -> list[CatalogEntry]:
    """Rule families browsable through `forge catalog monitoring`."""
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
    """Long description of a family: its role, its alerts, its traps."""
    lines = [family.details or family.summary, ""]
    lines.append("Alerts:")
    for alert in family.alerts:
        lines.append(f"  - {alert.name} ({alert.severity.value}, for: {alert.for_duration})")
        lines.append(f"      {alert.summary}")
    if family.exporters:
        lines += ["", f"Requires: {', '.join(family.exporters)}"]
    if family.traps:
        lines += ["", "Points to watch:"]
        lines += [f"  - {trap}" for trap in family.traps]
    return "\n".join(lines)


@hookimpl
def forge_interview(prompter: Prompter, service: ServiceSpec) -> dict[str, Any] | None:
    from forge.plugins.monitoring import interview

    return interview.run(prompter, service)
