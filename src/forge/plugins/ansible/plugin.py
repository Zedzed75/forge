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
        # Apres le socle, avant la charge applicative : configurer les machines
        # qui accueilleront le service, pas le service lui-meme.
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
    """Ce que le domaine Ansible affirme produire.

    `environments` ne recopie pas `service.environments` : Ansible y declare les
    environnements pour lesquels il a **reellement** des machines. Un
    environnement sans hote produit bien un inventaire, mais vide : le signaler
    est le genre de constat qu'aucun domaine ne peut faire seul, et que la
    comparaison de projections rend visible.

    La facette est nommee `inventory_hosts`, et non `hosts` : le vocabulaire des
    facettes est un espace de noms partage entre domaines (cf.
    `forge.validate.consistency.FACET_VOCABULARY`). Helm declare des hotes lui
    aussi, mais ce sont des noms de domaine d'Ingress : les confondre produisait
    un faux positif sur toute specification a deux domaines.
    """
    ansible: AnsibleSpec = spec.ansible
    materialises = tuple(
        env.name
        for env in spec.service.environments
        if any(hotes for hotes in ansible.hosts.get(env.name, {}).values())
    )
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
        environments=materialises,
        labels=dict(spec.service.labels),
        facets={
            "inventory_hosts": tuple(hotes),
            "groups": tuple(groupe.name for groupe in ansible.groups),
        },
    )


@hookimpl
def forge_validators(spec: Any, outdir: Path) -> list[Command]:
    return validators_module.commands(spec, outdir)


@hookimpl
def forge_deploy(spec: Any, outdir: Path, environment: str) -> list[Command]:
    """Comment ce domaine se deploie. Le coeur ne l'execute jamais."""
    return validators_module.deploy_commands(spec, outdir, environment)


@hookimpl
def forge_check_spec(spec: Any) -> list[Issue]:
    """Controles que la comparaison de projections ne peut pas exprimer.

    Le sous-modele d'un plugin ne voit que sa propre section : il ne peut donc
    pas verifier lui-meme que les environnements cites dans `ansible.hosts`
    existent bien dans `service.environments`. Ce hook, appele avec la spec
    complete et **avant tout rendu**, comble ce trou : une specification
    incoherente est refusee au moment de la generation, pas seulement au
    `forge validate` suivant (arbitrage R2 de la revue d'interface).
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
