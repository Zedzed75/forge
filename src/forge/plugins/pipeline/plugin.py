"""Plugin de domaine pipeline : implementation des hooks de forge.

Ce plugin se distingue des trois autres sur un seul point : son `forge_answers`
declare le parametre `context`. pluggy n'appelle un hookimpl qu'avec les
arguments qu'il nomme — les trois autres domaines n'ont donc rien eu a changer
quand ce parametre a ete ajoute au hookspec.

Ce qu'il **ne** fait pas, et qui est le fond de la phase 8 :

* il ne connait aucun domaine par son nom — le mot « helm » n'apparait dans ce
  paquet que dans de la documentation et dans la table d'installation des
  outils, ou il designe un binaire, pas une section de forge.yml ;
* il n'invente aucune commande — chaque domaine declare les siennes
  (`forge_validators`, `forge_deploy`), et un domaine muet sur le deploiement
  est nomme dans le pipeline genere plutot que devine ;
* il ne fait rien du coeur un ordonnanceur — le coeur assemble un
  `GenerationContext` a partir de hooks qu'il appelait deja, et n'en tire
  aucune conclusion.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge.interview.prompter import Prompter
from forge.plugins.pipeline import answers as answers_module
from forge.plugins.pipeline import tools as tools_module
from forge.plugins.pipeline import validators as validators_module
from forge.plugins.pipeline.spec import PipelineSpec
from forge.plugins_api.hookspecs import hookimpl
from forge.plugins_api.types import (
    CatalogEntry,
    Command,
    DomainInfo,
    GenerationContext,
    Issue,
)
from forge.spec.service import ServiceSpec


@hookimpl
def forge_domain() -> DomainInfo:
    return DomainInfo(
        name="pipeline",
        title="Pipeline",
        summary="Integration pipeline: one job per domain, build, deploy",
        # Un fichier de CI n'existe que la ou son outil le lit : ni GitHub ni
        # GitLab ne le cherchent dans un sous-repertoire. Seul domaine du projet
        # dont la sortie est la racine du depot.
        outdir=".",
    )


@hookimpl
def forge_spec_model() -> type[PipelineSpec]:
    return PipelineSpec


@hookimpl
def forge_template_subdir() -> str:
    return "src/forge/plugins/pipeline/template"


@hookimpl
def forge_answers(spec: Any, context: GenerationContext) -> dict[str, Any]:
    """Seul hookimpl du projet a declarer `context` : c'est sa raison d'etre."""
    return answers_module.build(spec, context)


@hookimpl
def forge_validators(spec: Any, outdir: Path) -> list[Command]:
    return validators_module.commands(spec, outdir)


@hookimpl
def forge_check_spec(spec: Any) -> list[Issue]:
    """Controles que le sous-modele ne peut pas faire : il ne voit pas `service:`."""
    if getattr(spec, "pipeline", None) is None:
        return []
    return answers_module.cross_check(spec)


@hookimpl
def forge_catalog() -> list[CatalogEntry]:
    """Outils que le pipeline sait installer.

    Le catalogue de ce domaine n'est pas une liste de ressources mais la reponse
    a la seule question qu'un utilisateur se pose ici : « mon pipeline
    saura-t-il installer ce que mes domaines veulent lancer ? »
    """
    return [
        CatalogEntry(
            name=recette.name,
            summary=recette.summary,
            details=_details(recette),
        )
        for recette in tools_module.INSTALLS
    ]


def _details(recette: Any) -> str:
    """Comment le pipeline installe cet outil, litteralement."""
    lignes = [f"Installe par le pipeline avec :", ""]
    if recette.requires:
        lignes.append(f"  # paquets systeme : {', '.join(recette.requires)}")
    lignes += [f"  {ligne}" for ligne in recette.steps]
    if recette.exports:
        lignes += ["", "Variables posees ensuite :"]
        lignes += [f"  {cle}={valeur}" for cle, valeur in sorted(recette.exports.items())]
    lignes += [
        "",
        "Un outil absent de cette liste n'est jamais devine : le pipeline genere",
        "porte une etape qui echoue en le nommant.",
    ]
    return "\n".join(lignes)


@hookimpl
def forge_interview(prompter: Prompter, service: ServiceSpec) -> dict[str, Any] | None:
    from forge.plugins.pipeline import interview

    return interview.run(prompter, service)
