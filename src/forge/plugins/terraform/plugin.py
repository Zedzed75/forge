"""Plugin de domaine Terraform : implementation des hooks de forge.

Comme les deux autres plugins, ce module ne contient aucune logique : il branche
le contrat (`DESIGN.md` §2.2) sur les modules qui font le travail.

C'est le premier domaine du projet qui ne vient d'aucun outil legacy. Ce qu'il
demontre — ou non — c'est que le contrat de plugin suffit a ajouter un domaine
sans toucher au coeur. Une seule ligne du coeur change : l'entree de
`BUILTIN_PLUGINS`.
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
        summary="Socle d'infrastructure : namespace, budget, identite de deploiement",
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
def forge_check_spec(spec: Any) -> list[Issue]:
    """Controles que le sous-modele ne peut pas faire : il ne voit pas `service:`."""
    if getattr(spec, "terraform", None) is None:
        return []
    return answers_module.cross_check(spec)


@hookimpl
def forge_projection(spec: Any) -> Projection:
    """Ce que le domaine Terraform affirme produire.

    Une seule facette, et c'est delibere : `namespaces`, du **vocabulaire
    partage** (`forge.validate.consistency.FACET_VOCABULARY`). C'est exactement
    celle que le domaine Helm declare, et la ou les deux domaines doivent
    s'accorder : Terraform cree le cloisonnement, Helm y deploie. Un desaccord
    signifie que le chart vise un namespace que personne ne cree.

    La phase 5 avait etabli le mecanisme sans avoir de vrai desaccord a
    montrer — Ansible et Helm ne partagent aucune facette de ce genre. Ce
    plugin lui donne son premier cas reel.
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
    """Familles de ressources consultables par `forge catalog terraform`."""
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
    """Description longue d'une famille : son role, ce qu'elle pose, ses pieges."""
    lignes = [
        famille.details or famille.summary,
        "",
        f"Pose : {', '.join(famille.resources)}",
        f"Providers : {', '.join(famille.providers)}",
    ]
    if famille.outputs:
        lignes.append(f"Sorties : {', '.join(sorted(famille.outputs))}")
    if famille.traps:
        lignes += ["", "Points de vigilance :"]
        lignes += [f"  - {piege}" for piege in famille.traps]
    return "\n".join(lignes)


@hookimpl
def forge_interview(prompter: Prompter, service: ServiceSpec) -> dict[str, Any] | None:
    from forge.plugins.terraform import interview

    return interview.run(prompter, service)
