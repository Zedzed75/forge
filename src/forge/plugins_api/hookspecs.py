"""Hookspecs pluggy du projet (DESIGN.md §2.2).

Regle : aucun `firstresult=True` sur les hooks propres a un domaine — ils
seraient silencieusement captes par le premier plugin enregistre. Le coeur
adresse un domaine a la fois via `manager.domain(nom)` (DESIGN.md §2.3).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pluggy

from forge.plugins_api.types import (
    CatalogEntry,
    Command,
    DomainInfo,
    GenerationContext,
    Issue,
    Projection,
)

if TYPE_CHECKING:  # pragma: no cover - uniquement pour les annotations
    from pydantic import BaseModel

    from forge.interview.prompter import Prompter
    from forge.spec.service import ServiceSpec

#: Nom du projet pluggy ; identique cote hookspec et hookimpl.
PROJECT_NAME = "forge"

hookspec = pluggy.HookspecMarker(PROJECT_NAME)
hookimpl = pluggy.HookimplMarker(PROJECT_NAME)


@hookspec
def forge_domain() -> DomainInfo:
    """Identite du domaine. Seul hook obligatoire pour etre decouvert."""


@hookspec
def forge_spec_model() -> type[BaseModel]:
    """Sous-modele pydantic validant la section <domaine> de forge.yml.

    Le coeur assemble le modele racine a partir des sous-modeles enregistres :
    chaque section est optionnelle, l'absence de section signifie « domaine non
    genere ». Le coeur ne connait rien de son contenu.
    """


@hookspec
def forge_interview(prompter: Prompter, service: ServiceSpec) -> dict[str, Any] | None:
    """Conduit l'entretien du domaine et retourne sa section de forge.yml.

    Le plugin pilote son questionnaire a travers le protocole `Prompter` fourni
    par le coeur, jamais questionary directement : c'est ce qui rend l'entretien
    rejouable en test. Retourne None si l'utilisateur decline le domaine.
    """


@hookspec
def forge_template_subdir() -> str:
    """Chemin du gabarit copier, relatif a la racine du depot forge.

    Exemple : "src/forge/plugins/ansible/template". Passe a copier via
    `_subdirectory` (DESIGN.md §5).
    """


@hookspec
def forge_answers(spec: Any, context: GenerationContext) -> dict[str, Any]:
    """Projette la spec unifiee vers le dict `domain` passe a copier.

    Sortie JSON-serialisable et deterministe : elle est ecrite telle quelle dans
    `.copier-answers.yml` et rejouee par `copier update`.

    `context` decrit **les autres domaines demandes par la specification**, dans
    le vocabulaire du contrat : leur `DomainInfo`, leur `Projection`, leurs
    `Command` de validation et de deploiement. Un plugin qui n'en a pas besoin
    ne declare pas le parametre — pluggy n'appelle un hookimpl qu'avec les
    arguments qu'il nomme, et les trois premiers domaines s'en passent.

    Il existe pour le domaine `pipeline`, dont la sortie depend des autres
    sections : il doit engendrer un job par domaine present **sans connaitre
    aucun domaine par son nom**. Le coeur n'ordonnance rien pour autant — il
    transmet des faits qu'il calculait deja.
    """


@hookspec
def forge_validators(spec: Any, outdir: Path) -> list[Command]:
    """Commandes externes validant le domaine genere, dans l'ordre d'execution."""


@hookspec
def forge_deploy(spec: Any, outdir: Path, environment: str) -> list[Command]:
    """Commandes deployant ce domaine dans `environment` (facultatif).

    Symetrique de `forge_validators`, et soumis a la meme regle : le plugin
    decrit **quoi lancer**, jamais comment l'executer. La difference est qu'un
    deploiement touche a une infrastructure reelle — le coeur ne les lance
    jamais lui-meme. Elles n'existent que pour etre **ecrites** dans un pipeline
    par le domaine `pipeline`, qui ne saurait pas les inventer.

    Un domaine qui ne l'implemente pas fait engendrer une etape a completer,
    plutot qu'une commande devinee.
    """


@hookspec
def forge_projection(spec: Any) -> Projection:
    """Ce que le domaine affirme produire, pour les controles inter-domaines."""


@hookspec
def forge_check_spec(spec: Any) -> list[Issue]:
    """Controles que le sous-modele du domaine ne peut pas faire lui-meme.

    Un sous-modele pydantic ne voit que **sa** section : il peut verifier que
    les groupes qu'il cite existent, jamais que les environnements existent,
    puisque ceux-ci sont declares dans le bloc partage `service:`.

    Le coeur appelle ce hook juste apres l'assemblage du modele, **avant tout
    rendu** : une specification incoherente doit etre refusee au moment de la
    generation, pas seulement au `forge validate` suivant. Un `Issue` de niveau
    `error` arrete la generation ; un `warning` est affiche et laisse passer.

    A distinguer de `forge_consistency`, qui porte sur le projet **deja ecrit**
    et recoit donc les repertoires de sortie.
    """


@hookspec
def forge_consistency(spec: Any, outdirs: dict[str, Path]) -> list[Issue]:
    """Controles supplementaires propres au plugin (echappatoire).

    Seul hook appele sur *tous* les plugins a la fois ; les resultats sont
    concatenes. A n'utiliser que pour ce que `forge_projection` ne peut pas dire.
    """


@hookspec
def forge_catalog() -> list[CatalogEntry] | None:
    """Catalogue consultable via `forge catalog <domaine>` (facultatif)."""
