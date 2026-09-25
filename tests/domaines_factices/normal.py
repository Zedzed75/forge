"""Conforming fake domain: the reference for the cross-domain checks."""

from __future__ import annotations

from typing import Any

from forge.plugins_api.hookspecs import hookimpl
from forge.plugins_api.types import DomainInfo, Projection
from tests.domaines_factices import TrivialSection, standard_projection


@hookimpl
def forge_domain() -> DomainInfo:
    return DomainInfo(name="normal", title="Normal", summary="Conforming fake domain")


@hookimpl
def forge_spec_model() -> type[TrivialSection]:
    return TrivialSection


@hookimpl
def forge_template_subdir() -> str:
    return "src/forge/plugins/demo/template"


@hookimpl
def forge_answers(spec: Any) -> dict[str, Any]:
    return {"enabled": spec.normal.enabled}


@hookimpl
def forge_projection(spec: Any) -> Projection:
    return standard_projection(spec)
