"""Hookspecs pluggy du projet (DESIGN.md §2.2).

Regle : aucun `firstresult=True` sur les hooks propres a un domaine — ils
seraient silencieusement captes par le premier plugin enregistre. Le coeur
adresse un domaine a la fois via `manager.domain(nom)` (DESIGN.md §2.3).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pluggy

from forge.plugins_api.types import CatalogEntry, Command, DomainInfo, Issue, Projection

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
def forge_answers(spec: Any) -> dict[str, Any]:
    """Projette la spec unifiee vers le dict `domain` passe a copier.

    Sortie JSON-serialisable et deterministe : elle est ecrite telle quelle dans
    `.copier-answers.yml` et rejouee par `copier update`.
    """


@hookspec
def forge_validators(spec: Any, outdir: Path) -> list[Command]:
    """Commandes externes validant le domaine genere, dans l'ordre d'execution."""


@hookspec
def forge_projection(spec: Any) -> Projection:
    """Ce que le domaine affirme produire, pour les controles inter-domaines."""


@hookspec
def forge_consistency(spec: Any, outdirs: dict[str, Path]) -> list[Issue]:
    """Controles supplementaires propres au plugin (echappatoire).

    Seul hook appele sur *tous* les plugins a la fois ; les resultats sont
    concatenes. A n'utiliser que pour ce que `forge_projection` ne peut pas dire.
    """


@hookspec
def forge_catalog() -> list[CatalogEntry] | None:
    """Catalogue consultable via `forge catalog <domaine>` (facultatif)."""
