"""Registre des familles de ressources Helm.

Pendant de `plugins/ansible/catalog/registry.py`. L'ordre du catalogue fixe
l'ordre des slots de composants, donc celui des fichiers generes : le trier
autrement changerait la sortie.
"""

from __future__ import annotations

from forge.errors import SpecValidationError
from forge.plugins.helm.catalog.definition import ComponentFamily
from forge.plugins.helm.catalog.families import FAMILIES

#: Familles indexees par nom, dans l'ordre du catalogue.
FAMILY_CATALOG: dict[str, ComponentFamily] = {famille.name: famille for famille in FAMILIES}


def family_names() -> list[str]:
    """Noms des familles, dans l'ordre du catalogue."""
    return [famille.name for famille in FAMILIES]


def all_families() -> tuple[ComponentFamily, ...]:
    """Toutes les familles, dans l'ordre du catalogue."""
    return FAMILIES


def get_family(name: str) -> ComponentFamily:
    """Retourne la famille `name`, ou leve `SpecValidationError`."""
    try:
        return FAMILY_CATALOG[name]
    except KeyError:
        connues = ", ".join(family_names())
        raise SpecValidationError(
            f"Famille de ressources inconnue : '{name}'. Familles disponibles : {connues}."
        ) from None


def families_by_selection(selection: str) -> tuple[ComponentFamily, ...]:
    """Familles retenues par un mode de selection (`kind`, `addon`, `derive`)."""
    return tuple(famille for famille in FAMILIES if famille.selection == selection)


def sort_families(names: list[str] | tuple[str, ...]) -> list[str]:
    """Trie des noms de famille dans l'ordre du catalogue, doublons retires."""
    ordre = family_names()
    connues = [nom for nom in dict.fromkeys(names) if nom in ordre]
    return sorted(connues, key=ordre.index)
