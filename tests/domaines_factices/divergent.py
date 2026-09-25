"""Fake domain that lies about the service name.

It triggers a cross-domain check at **error** level: the only way to exercise
`forge validate`'s exit code 1 without depending on an external tool. It
declares no validator, so that the failure really comes from the projection and
not from a command.
"""

from __future__ import annotations

from typing import Any

from forge.plugins_api.hookspecs import hookimpl
from forge.plugins_api.types import DomainInfo, Projection
from tests.domaines_factices import TrivialSection


@hookimpl
def forge_domain() -> DomainInfo:
    return DomainInfo(
        name="divergent", title="Divergent", summary="Inconsistent fake domain"
    )


@hookimpl
def forge_spec_model() -> type[TrivialSection]:
    return TrivialSection


@hookimpl
def forge_template_subdir() -> str:
    return "src/forge/plugins/demo/template"


@hookimpl
def forge_answers(spec: Any) -> dict[str, Any]:
    return {"enabled": spec.divergent.enabled}


@hookimpl
def forge_projection(spec: Any) -> Projection:
    return Projection(
        service_name="another-service",
        environments=tuple(env.name for env in spec.service.environments),
        labels=dict(spec.service.labels),
    )
