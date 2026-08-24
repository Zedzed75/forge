"""Plugin de domaine Ansible : implementation des hooks de forge.

Ce module ne contient aucune logique : il branche le contrat de plugin
(`DESIGN.md` §2.2) sur les modules qui font le travail — `spec` pour le modele,
`answers` pour la projection vers copier, `validators` pour les commandes
externes, `catalog` pour le catalogue de roles, `interview` pour l'entretien.
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
        summary="Projet Ansible complet : inventaires, playbooks et roles commentes",
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
    """Ce que le domaine Ansible affirme produire.

    La facette `hosts` est declaree parce qu'un autre domaine peut parler des
    memes machines (les hotes d'Ingress cote Helm, par exemple) : le coeur
    comparera alors les deux declarations sans rien savoir d'Ansible.
    """
    ansible: AnsibleSpec = spec.ansible
    hotes = sorted(
        {
            hote.name
            for par_groupe in ansible.hosts.values()
            for hotes in par_groupe.values()
            for hote in hotes
        }
    )
    return Projection(
        service_name=spec.service.name,
        environments=tuple(env.name for env in spec.service.environments),
        labels=dict(spec.service.labels),
        facets={
            "hosts": tuple(hotes),
            "groups": tuple(groupe.name for groupe in ansible.groups),
        },
    )


@hookimpl
def forge_validators(spec: Any, outdir: Path) -> list[Command]:
    return validators_module.commands(spec, outdir)


@hookimpl
def forge_consistency(spec: Any, outdirs: dict[str, Path]) -> list[Issue]:
    """Controles que la comparaison de projections ne peut pas exprimer.

    Le sous-modele d'un plugin ne voit que sa propre section : il ne peut donc
    pas verifier lui-meme que les environnements cites dans `ansible.hosts`
    existent bien dans `service.environments`. Ce hook, appele avec la spec
    complete, comble ce trou. (Point a reprendre a la revue d'interface de la
    phase 4 : le contrat manque d'un controle croise au moment de la validation
    du modele, pas seulement a celui de la validation du projet genere.)
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
