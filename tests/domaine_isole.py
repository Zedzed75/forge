"""Domaine factice dont le paquet ne fournit **aucun** module de filtres.

Il vit a la racine de `tests/` — et non dans `tests/domaines_factices/`, qui
possede un `jinja_ext` — pour eprouver le cas d'un plugin qui n'enrichit pas
l'environnement Jinja de copier.
"""

from __future__ import annotations

from typing import Any

from forge.plugins_api.hookspecs import hookimpl
from forge.plugins_api.types import DomainInfo
from tests.domaines_factices import SectionTriviale


@hookimpl
def forge_domain() -> DomainInfo:
    return DomainInfo(name="isole", title="Isole", summary="Domaine factice sans filtres")


@hookimpl
def forge_spec_model() -> type[SectionTriviale]:
    return SectionTriviale


@hookimpl
def forge_template_subdir() -> str:
    return "src/forge/plugins/demo/template"


@hookimpl
def forge_answers(spec: Any) -> dict[str, Any]:
    return {"enabled": spec.isole.enabled}
