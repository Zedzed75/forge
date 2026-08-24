"""Domaine factice qui ment sur le nom du service.

Il declenche un controle inter-domaines de niveau **erreur** : c'est le seul
moyen d'eprouver le code de sortie 1 de `forge validate` sans dependre d'un
outil externe. Il ne declare aucun validateur, pour que l'echec vienne bien de
la projection et non d'une commande.
"""

from __future__ import annotations

from typing import Any

from forge.plugins_api.hookspecs import hookimpl
from forge.plugins_api.types import DomainInfo, Projection
from tests.domaines_factices import SectionTriviale


@hookimpl
def forge_domain() -> DomainInfo:
    return DomainInfo(
        name="divergent", title="Divergent", summary="Domaine factice incoherent"
    )


@hookimpl
def forge_spec_model() -> type[SectionTriviale]:
    return SectionTriviale


@hookimpl
def forge_template_subdir() -> str:
    return "src/forge/plugins/demo/template"


@hookimpl
def forge_answers(spec: Any) -> dict[str, Any]:
    return {"enabled": spec.divergent.enabled}


@hookimpl
def forge_projection(spec: Any) -> Projection:
    return Projection(
        service_name="un-autre-service",
        environments=tuple(env.name for env in spec.service.environments),
        labels=dict(spec.service.labels),
    )
