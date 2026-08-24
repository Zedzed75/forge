"""Second domaine reellement generable, pour eprouver le filtrage `--only`.

Il reutilise le gabarit du plugin `demo` — aucun fichier de gabarit n'est ajoute
a l'arborescence de production — mais ecrit dans son propre sous-repertoire.
"""

from __future__ import annotations

from typing import Any

from forge.plugins.demo.plugin import DemoSpec
from forge.plugins_api.hookspecs import hookimpl
from forge.plugins_api.types import DomainInfo, Projection


@hookimpl
def forge_domain() -> DomainInfo:
    return DomainInfo(
        name="autre",
        title="Autre",
        summary="Second domaine generable, utilise par les tests de filtrage",
        outdir="autre",
    )


@hookimpl
def forge_spec_model() -> type[DemoSpec]:
    return DemoSpec


@hookimpl
def forge_template_subdir() -> str:
    return "src/forge/plugins/demo/template"


@hookimpl
def forge_answers(spec: Any) -> dict[str, Any]:
    section: DemoSpec = spec.autre
    return {
        "greeting": section.greeting,
        "environments": [
            {"name": env.name, "production": env.production}
            for env in spec.service.environments
        ],
        "widgets": [
            {"name": w.name, "kind": w.kind, "detailed": w.detailed}
            for w in section.widgets
        ],
    }


@hookimpl
def forge_projection(spec: Any) -> Projection:
    return Projection(
        service_name=spec.service.name,
        environments=tuple(env.name for env in spec.service.environments),
        labels=dict(spec.service.labels),
        facets={"widgets": tuple(w.name for w in spec.autre.widgets)},
    )
