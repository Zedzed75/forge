"""Domaine factice dont le validateur repose sur un outil qui n'existe pas.

Il sert a eprouver, de bout en bout, les deux comportements que le coeur promet
face a un outil manquant : echec explicite par defaut, saut assume avec
`--skip-missing` — accompagne d'un avertissement, car un rapport vert ou rien
n'a tourne est un piege.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge.plugins_api.hookspecs import hookimpl
from forge.plugins_api.types import Command, DomainInfo, Projection
from tests.domaines_factices import SectionTriviale, projection_standard

#: Binaire volontairement introuvable sur toutes les plateformes.
OUTIL_ABSENT = "outil-forge-qui-n-existe-pas"


@hookimpl
def forge_domain() -> DomainInfo:
    return DomainInfo(
        name="fragile", title="Fragile", summary="Domaine factice a outil manquant"
    )


@hookimpl
def forge_spec_model() -> type[SectionTriviale]:
    return SectionTriviale


@hookimpl
def forge_template_subdir() -> str:
    return "src/forge/plugins/demo/template"


@hookimpl
def forge_answers(spec: Any) -> dict[str, Any]:
    return {"enabled": spec.fragile.enabled}


@hookimpl
def forge_projection(spec: Any) -> Projection:
    return projection_standard(spec)


@hookimpl
def forge_validators(spec: Any, outdir: Path) -> list[Command]:
    return [
        Command(
            label="fragile : outil absent",
            tool=OUTIL_ABSENT,
            cwd=outdir,
            install_hint="cet outil n'existe pas, c'est le but du test",
        )
    ]
