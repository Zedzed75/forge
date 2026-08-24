"""Domaine factice qui ordonne les environnements a l'envers.

Il declenche un controle inter-domaines de niveau **avertissement** : le pendant
de `divergent`, pour verifier qu'un avertissement ne fait pas echouer
`forge validate`.
"""

from __future__ import annotations

from typing import Any

from forge.plugins_api.hookspecs import hookimpl
from forge.plugins_api.types import DomainInfo, Projection
from tests.domaines_factices import SectionTriviale


@hookimpl
def forge_domain() -> DomainInfo:
    return DomainInfo(
        name="desordre", title="Desordre", summary="Domaine factice mal ordonne"
    )


@hookimpl
def forge_spec_model() -> type[SectionTriviale]:
    return SectionTriviale


@hookimpl
def forge_template_subdir() -> str:
    return "src/forge/plugins/demo/template"


@hookimpl
def forge_answers(spec: Any) -> dict[str, Any]:
    return {"enabled": spec.desordre.enabled}


@hookimpl
def forge_projection(spec: Any) -> Projection:
    return Projection(
        service_name=spec.service.name,
        environments=tuple(reversed([env.name for env in spec.service.environments])),
        labels=dict(spec.service.labels),
    )
