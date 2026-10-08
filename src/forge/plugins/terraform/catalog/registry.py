"""Access to the catalogue of Terraform families.

The same role as `forge.plugins.ansible.catalog.registry` and its Helm
equivalent: a single entry point, so that the canonical order is that of the
catalogue and not that of the specification. Two specifications that quote the
same families in a different order must produce the same project.
"""

from __future__ import annotations

from forge.plugins.terraform.catalog.families import BY_NAME, FAMILIES, Family
from forge.plugins.terraform.catalog.providers import Provider, resolve
from forge.plugins.terraform.variables import COMMON_VARIABLES, Variable


def all_families() -> tuple[Family, ...]:
    """All the families, in canonical order."""
    return FAMILIES


def family_names() -> tuple[str, ...]:
    """Family names, in canonical order."""
    return tuple(family.name for family in FAMILIES)


def get_family(name: str) -> Family:
    """The `name` family, or `KeyError`. The sub-model already validates the names."""
    return BY_NAME[name]


def selected(names: list[str] | tuple[str, ...]) -> tuple[Family, ...]:
    """Retained families, put back into canonical order and deduplicated."""
    requested = set(names)
    return tuple(family for family in FAMILIES if family.name in requested)


def providers_for(families: tuple[Family, ...]) -> list[Provider]:
    """Providers the retained families need, sorted by local name."""
    return resolve({name for family in families for name in family.providers})


def variables_for(families: tuple[Family, ...]) -> tuple[Variable, ...]:
    """Variables of the module: the common ones, then those of the retained families.

    Deduplicated by name, keeping the first declaration: two families can
    legitimately ask for the same variable, and it is the common definition that
    must win.
    """
    result: list[Variable] = list(COMMON_VARIABLES)
    known = {variable.name for variable in result}
    for family in families:
        for variable in family.variables:
            if variable.name in known:
                continue
            known.add(variable.name)
            result.append(variable)
    return tuple(result)
