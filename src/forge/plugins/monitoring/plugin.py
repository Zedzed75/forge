"""Plugin de domaine monitoring : implementation des hooks de forge.

Comme les trois autres, ce module ne contient aucune logique : il branche le
contrat (`DESIGN.md` §2.2) sur les modules qui font le travail.

Le domaine est **autonome** : il ne lit aucune autre section de forge.yml. Sa
rencontre avec les autres domaines se fait par les facettes, comparees par
`forge validate` — `namespaces` avec Terraform et Helm, `ingress_hosts` avec
Helm. Un chart qui expose `boutique.example.net` pendant que la sonde regarde
`api.example.net` est un defaut qu'aucun des deux domaines ne peut voir seul.
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
        summary="Collecte, regles d'alerte et tests unitaires d'alerte",
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
    """Controles que le sous-modele ne peut pas faire : il ne voit pas `service:`."""
    if getattr(spec, "monitoring", None) is None:
        return []
    return answers_module.cross_check(spec)


@hookimpl
def forge_projection(spec: Any) -> Projection:
    """Ce que le domaine monitoring affirme surveiller.

    Deux facettes du **vocabulaire partage**
    (`forge.validate.consistency.FACET_VOCABULARY`) :

    * `namespaces` — les cloisons observees. Terraform les cree, Helm y deploie,
      le monitoring les regarde : les trois doivent nommer les memes.
    * `ingress_hosts` — les hotes sondes de l'exterieur. C'est la facette que
      Helm declare pour ses Ingress. Surveiller un hote que personne n'expose,
      ou exposer un hote que personne ne sonde, sont deux erreurs symetriques
      qu'aucun domaine ne peut voir seul.

    `environments` ne recopie pas `service.environments` : un environnement sans
    aucune cible declaree n'est pas materialise par ce domaine, et le dire est
    plus utile que de pretendre le surveiller.
    """
    monitoring = spec.monitoring
    materialises = tuple(
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
        environments=materialises,
        labels=dict(spec.service.labels),
        facets={
            "namespaces": tuple(namespaces),
            "ingress_hosts": answers_module.probe_hosts(spec),
        },
    )


@hookimpl
def forge_catalog() -> list[CatalogEntry]:
    """Familles de regles consultables par `forge catalog monitoring`."""
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
    """Description longue d'une famille : son role, ses alertes, ses pieges."""
    lignes = [famille.details or famille.summary, ""]
    lignes.append("Alertes :")
    for alerte in famille.alerts:
        lignes.append(f"  - {alerte.name} ({alerte.severity.value}, for: {alerte.for_duration})")
        lignes.append(f"      {alerte.summary}")
    if famille.exporters:
        lignes += ["", f"Exige : {', '.join(famille.exporters)}"]
    if famille.traps:
        lignes += ["", "Points de vigilance :"]
        lignes += [f"  - {piege}" for piege in famille.traps]
    return "\n".join(lignes)


@hookimpl
def forge_interview(prompter: Prompter, service: ServiceSpec) -> dict[str, Any] | None:
    from forge.plugins.monitoring import interview

    return interview.run(prompter, service)
