"""Domaines factices utilises par les tests du coeur.

Chaque module de ce paquet est un plugin complet, importable par son chemin
pointe : les tests peuvent donc les declarer via `FORGE_PLUGINS` et exercer la
CLI de bout en bout avec **plusieurs** domaines — ce que le seul plugin `demo`
ne permet pas (filtrage `--only`, controles inter-domaines en echec).

Ils ne sont jamais enregistres en production : `BUILTIN_PLUGINS` reste vide.
"""

from __future__ import annotations

from typing import Any

from forge.plugins_api.types import Projection
from forge.spec.types import ForgeModel


class SectionTriviale(ForgeModel):
    """Section de forge.yml sans contenu utile : seule la projection compte."""

    #: Presence symbolique, pour que la section ait au moins un champ.
    enabled: bool = True


def projection_standard(spec: Any) -> Projection:
    """Projection fidele a la specification : la reference de comparaison."""
    return Projection(
        service_name=spec.service.name,
        environments=tuple(env.name for env in spec.service.environments),
        labels=dict(spec.service.labels),
    )
