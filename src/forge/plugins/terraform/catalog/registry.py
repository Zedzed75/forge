"""Acces au catalogue des familles Terraform.

Meme role que `forge.plugins.ansible.catalog.registry` et son equivalent Helm :
une seule porte d'entree, pour que l'ordre canonique soit celui du catalogue et
non celui de la specification. Deux specifications qui citent les memes familles
dans un ordre different doivent produire le meme projet.
"""

from __future__ import annotations

from forge.plugins.terraform.catalog.families import BY_NAME, FAMILIES, Family
from forge.plugins.terraform.catalog.providers import Provider, resolve
from forge.plugins.terraform.variables import COMMON_VARIABLES, Variable


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


def providers_for(families: tuple[Family, ...]) -> list[Provider]:
    """Providers necessaires aux familles retenues, tries par nom local."""
    return resolve({nom for famille in families for nom in famille.providers})


def variables_for(families: tuple[Family, ...]) -> tuple[Variable, ...]:
    """Variables du module : les communes, puis celles des familles retenues.

    Dedoublonnees par nom en conservant la premiere declaration : deux familles
    peuvent legitimement demander la meme variable, et c'est la definition
    commune qui doit l'emporter.
    """
    resultat: list[Variable] = list(COMMON_VARIABLES)
    connues = {variable.name for variable in resultat}
    for famille in families:
        for variable in famille.variables:
            if variable.name in connues:
                continue
            connues.add(variable.name)
            resultat.append(variable)
    return tuple(resultat)
