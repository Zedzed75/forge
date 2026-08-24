"""Domaine factice conforme : sert de reference aux controles inter-domaines."""

from __future__ import annotations

from typing import Any

from forge.plugins_api.hookspecs import hookimpl
from forge.plugins_api.types import DomainInfo, Projection
from tests.domaines_factices import SectionTriviale, projection_standard


@hookimpl
def forge_domain() -> DomainInfo:
    return DomainInfo(name="normal", title="Normal", summary="Domaine factice conforme")


@hookimpl
def forge_spec_model() -> type[SectionTriviale]:
    return SectionTriviale


@hookimpl
def forge_template_subdir() -> str:
    return "src/forge/plugins/demo/template"


@hookimpl
def forge_answers(spec: Any) -> dict[str, Any]:
    return {"enabled": spec.normal.enabled}


@hookimpl
def forge_projection(spec: Any) -> Projection:
    return projection_standard(spec)
