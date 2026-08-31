"""Domaine factice **que le plugin pipeline n'a jamais vu**.

C'est le temoin de la promesse de la phase 8 : le domaine `pipeline` engendre un
job par domaine demande *sans connaitre aucun domaine par son nom*. Si cette
promesse tenait par accident — parce que les quatre domaines livres ont ete
ecrits en meme temps que lui — ce module le revelerait.

Il declare en plus un outil que la table d'installation du pipeline ne connait
pas : `outil-maison`. Le pipeline ne doit pas le deviner, mais engendrer une
etape qui echoue en le nommant.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge.plugins_api.hookspecs import hookimpl
from forge.plugins_api.types import Command, DomainInfo, Projection
from tests.domaines_factices import SectionTriviale, projection_standard

#: Outil absent de `forge.plugins.pipeline.tools.INSTALLS`, et qui doit le rester.
OUTIL_INCONNU = "outil-maison"


@hookimpl
def forge_domain() -> DomainInfo:
    return DomainInfo(
        name="inconnu",
        title="Domaine Inconnu",
        summary="Domaine factice que le pipeline n'a jamais vu",
        # Entre le socle (10) et la configuration de machines (30) : le tri par
        # rang doit le placer la, et non a sa position alphabetique.
        deploy_order=20,
    )


@hookimpl
def forge_spec_model() -> type[SectionTriviale]:
    return SectionTriviale


@hookimpl
def forge_template_subdir() -> str:
    return "src/forge/plugins/demo/template"


@hookimpl
def forge_answers(spec: Any) -> dict[str, Any]:
    return {"enabled": spec.inconnu.enabled}


@hookimpl
def forge_projection(spec: Any) -> Projection:
    return projection_standard(spec)


@hookimpl
def forge_validators(spec: Any, outdir: Path) -> list[Command]:
    """Deux commandes, dont un chainage par stdin comme le domaine Helm."""
    return [
        Command(
            label="rendu inconnu",
            tool=OUTIL_INCONNU,
            argv=("render", "--tout"),
            cwd=outdir,
            env=(("NO_COLOR", "1"), ("CHEMIN_LOCAL", "/opt/quelque-part")),
        ),
        Command(
            label="controle inconnu",
            tool=OUTIL_INCONNU,
            argv=("check", "-"),
            cwd=outdir / "sous-repertoire",
            stdin_from="rendu inconnu",
        ),
    ]


@hookimpl
def forge_deploy(spec: Any, outdir: Path, environment: str) -> list[Command]:
    return [
        Command(
            label=f"deploiement inconnu ({environment})",
            tool=OUTIL_INCONNU,
            argv=("apply", "--env", environment),
            cwd=outdir,
        )
    ]
