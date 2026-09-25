"""Fake domain that orders the environments backwards.

It triggers a cross-domain check at **warning** level: the counterpart of
`divergent`, to check that a warning does not make `forge validate` fail.
"""

from __future__ import annotations

from typing import Any

from forge.plugins_api.hookspecs import hookimpl
from forge.plugins_api.types import DomainInfo, Projection
from tests.fake_domains import TrivialSection


@hookimpl
def forge_domain() -> DomainInfo:
    return DomainInfo(
        name="desordre", title="Desordre", summary="Badly ordered fake domain"
    )


@hookimpl
def forge_spec_model() -> type[TrivialSection]:
    return TrivialSection


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
