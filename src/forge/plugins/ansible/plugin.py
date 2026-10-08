"""Ansible domain plugin: implementation of the forge hooks.

This module holds no logic: it wires the plugin contract (`DESIGN.md` §2.2) onto
the modules that do the work — `spec` for the model, `answers` for the projection
towards copier, `validators` for the external commands, `catalog` for the role
catalogue, `interview` for the interview.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge.interview.prompter import Prompter
from forge.plugins.ansible import answers as answers_module
from forge.plugins.ansible import validators as validators_module
from forge.plugins.ansible.catalog.registry import all_roles
from forge.plugins.ansible.spec import AnsibleSpec
from forge.plugins_api.hookspecs import hookimpl
from forge.plugins_api.types import CatalogEntry, Command, DomainInfo, Issue, Projection
from forge.spec.service import ServiceSpec


@hookimpl
def forge_domain() -> DomainInfo:
    return DomainInfo(
        name="ansible",
        title="Ansible",
        summary="Complete Ansible project: commented inventories, playbooks and roles",
        # After the base layer, before the application payload: configure the
        # machines that will host the service, not the service itself.
        deploy_order=30,
    )


@hookimpl
def forge_spec_model() -> type[AnsibleSpec]:
    return AnsibleSpec


@hookimpl
def forge_template_subdir() -> str:
    return "src/forge/plugins/ansible/template"


@hookimpl
def forge_answers(spec: Any) -> dict[str, Any]:
    return answers_module.build(spec)


@hookimpl
def forge_projection(spec: Any) -> Projection:
    """What the Ansible domain claims to produce.

    `environments` does not copy `service.environments`: Ansible declares there
    the environments it **actually** has machines for. An environment with no host
    does produce an inventory, but an empty one: reporting it is the kind of
    observation no domain can make on its own, and that comparing projections
    makes visible.

    The facet is named `inventory_hosts`, not `hosts`: the facet vocabulary is a
    namespace shared between domains (cf.
    `forge.validate.consistency.FACET_VOCABULARY`). Helm declares hosts too, but
    they are Ingress domain names: conflating them produced a false positive on
    every two-domain specification.
    """
    ansible: AnsibleSpec = spec.ansible
    materialised = tuple(
        env.name
        for env in spec.service.environments
        if any(hosts for hosts in ansible.hosts.get(env.name, {}).values())
    )
    hosts = sorted(
        {
            host.name
            for by_group in ansible.hosts.values()
            for group_hosts in by_group.values()
            for host in group_hosts
        }
    )
    return Projection(
        service_name=spec.service.name,
        environments=materialised,
        labels=dict(spec.service.labels),
        facets={
            "inventory_hosts": tuple(hosts),
            "groups": tuple(group.name for group in ansible.groups),
        },
    )


@hookimpl
def forge_validators(spec: Any, outdir: Path) -> list[Command]:
    return validators_module.commands(spec, outdir)


@hookimpl
def forge_deploy(spec: Any, outdir: Path, environment: str) -> list[Command]:
    """How this domain deploys itself. The core never runs it."""
    return validators_module.deploy_commands(spec, outdir, environment)


@hookimpl
def forge_check_spec(spec: Any) -> list[Issue]:
    """Checks the comparison of projections cannot express.

    The sub-model of a plugin only sees its own section: it therefore cannot check
    by itself that the environments quoted in `ansible.hosts` really exist in
    `service.environments`. This hook, called with the complete spec and **before
    any rendering**, fills that hole: an incoherent specification is refused at
    generation time, not merely at the next `forge validate` (arbitration R2 of
    the interface review).
    """
    if getattr(spec, "ansible", None) is None:
        return []
    return answers_module.cross_check(spec)


@hookimpl
def forge_catalog() -> list[CatalogEntry]:
    return [
        CatalogEntry(
            name=role.name,
            summary=role.summary,
            details=getattr(role, "description", "") or role.summary,
            options={option.name: option.description for option in role.options},
        )
        for role in all_roles()
    ]


@hookimpl
def forge_interview(prompter: Prompter, service: ServiceSpec) -> dict[str, Any] | None:
    from forge.plugins.ansible import interview

    return interview.run(prompter, service)
