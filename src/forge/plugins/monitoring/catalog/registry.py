"""Acces au catalogue des familles de regles.

Meme role que les registres des trois autres domaines : une seule porte
d'entree, pour que l'ordre canonique soit celui du catalogue et non celui de la
specification. Deux specifications qui citent les memes familles dans un ordre
different doivent produire le meme projet.
"""

from __future__ import annotations

from forge.plugins.monitoring.catalog.alerts import Alert
from forge.plugins.monitoring.catalog.families import BY_NAME, FAMILIES, Family


def all_families() -> tuple[Family, ...]:
    """Toutes les familles, dans l'ordre canonique."""
    return FAMILIES


def family_names() -> tuple[str, ...]:
    """Noms des familles, dans l'ordre canonique."""
    return tuple(famille.name for famille in FAMILIES)


def get_family(name: str) -> Family:
    """Famille `name`, ou `KeyError`. Le sous-modele valide deja les noms."""
    return BY_NAME[name]


def selected(names: list[str] | tuple[str, ...]) -> tuple[Family, ...]:
    """Familles retenues, remises dans l'ordre canonique et dedoublonnees."""
    demandees = set(names)
    return tuple(famille for famille in FAMILIES if famille.name in demandees)


def all_alerts() -> tuple[Alert, ...]:
    """Toutes les alertes du catalogue, familles confondues."""
    return tuple(alerte for famille in FAMILIES for alerte in famille.alerts)
