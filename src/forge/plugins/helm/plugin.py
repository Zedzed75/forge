"""Plugin de domaine Helm : implementation des hooks de forge.

Ce module ne contient aucune logique : il branche le contrat de plugin
(`DESIGN.md` §2.2) sur les modules qui font le travail — `spec` pour le modele,
`answers` pour la projection vers copier, `validators` pour les commandes
externes, `catalog` pour les familles de ressources, `interview` pour
l'entretien.
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
        summary="Chart Helm complet : values commentees, gabarits et validation stricte",
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
    """Comment ce domaine se deploie. Le coeur ne l'execute jamais."""
    return validators_module.deploy_commands(spec, outdir, environment)


@hookimpl
def forge_check_spec(spec: Any) -> list[Issue]:
    """Controles que le sous-modele ne peut pas faire : il ne voit pas `service:`."""
    if getattr(spec, "helm", None) is None:
        return []
    return answers_module.cross_check(spec)


@hookimpl
def forge_projection(spec: Any) -> Projection:
    """Ce que le domaine Helm affirme produire.

    Les noms de facette appartiennent a un **vocabulaire partage** entre
    domaines (cf. `forge.validate.consistency.FACET_VOCABULARY`) : `ingress_hosts`
    designe les noms de domaine par lesquels le service est joignable de
    l'exterieur, et non les machines d'un inventaire — Ansible declare
    `inventory_hosts`, ce qui n'est pas la meme chose. Les avoir tous deux
    nommes `hosts` produisait un faux positif sur toute specification a deux
    domaines : c'est le premier defaut qu'a revele la rencontre de deux domaines
    reels.
    """
    projection = answers_module.build(spec)
    hotes = sorted(
        {
            surcharge["ingress_host"]
            for env in projection["environments"]
            for surcharge in env["components"].values()
            if surcharge.get("ingress_host")
        }
    )
    namespaces = sorted({env["namespace"] for env in projection["environments"]})
    return Projection(
        service_name=spec.service.name,
        environments=tuple(env.name for env in spec.service.environments),
        labels=dict(spec.service.labels),
        facets={"ingress_hosts": tuple(hotes), "namespaces": tuple(namespaces)},
    )


@hookimpl
def forge_catalog() -> list[CatalogEntry]:
    """Familles de ressources consultables par `forge catalog helm`."""
    return [
        CatalogEntry(
            name=famille.name,
            summary=famille.summary,
            details=_details(famille),
            options=famille.option_descriptions(),
        )
        for famille in all_families()
    ]


def _details(famille: Any) -> str:
    """Description longue d'une famille : son role, puis ses pieges.

    Les pieges sont affiches a l'utilisateur parce qu'ils expliquent des choix
    du chart genere qui paraitraient arbitraires sans eux.
    """
    lignes = [
        famille.details or famille.summary,
        "",
        f"Produit : {famille.kind} ({famille.api_version})",
    ]
    if famille.requires:
        lignes.append(f"Exige : {', '.join(famille.requires)}")
    if famille.traps:
        lignes += ["", "Points de vigilance :"]
        lignes += [f"  - {piege}" for piege in famille.traps]
    return "\n".join(lignes)


@hookimpl
def forge_interview(prompter: Prompter, service: ServiceSpec) -> dict[str, Any] | None:
    from forge.plugins.helm import interview

    return interview.run(prompter, service)
