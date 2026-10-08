"""Registry of the Helm resource families.

Counterpart of `plugins/ansible/catalog/registry.py`. The catalogue order fixes
the order of the component slots, hence that of the generated files: sorting it
differently would change the output.
"""

from __future__ import annotations

from forge.errors import SpecValidationError
from forge.plugins.helm.catalog.definition import ComponentFamily
from forge.plugins.helm.catalog.families import FAMILIES

#: Families indexed by name, in catalogue order.
FAMILY_CATALOG: dict[str, ComponentFamily] = {family.name: family for family in FAMILIES}


def family_names() -> list[str]:
    """Family names, in catalogue order."""
    return [family.name for family in FAMILIES]


def all_families() -> tuple[ComponentFamily, ...]:
    """All the families, in catalogue order."""
    return FAMILIES


def get_family(name: str) -> ComponentFamily:
    """Return the `name` family, or raise `SpecValidationError`."""
    try:
        return FAMILY_CATALOG[name]
    except KeyError:
        known = ", ".join(family_names())
        raise SpecValidationError(
            f"Unknown resource family: '{name}'. Available families: {known}."
        ) from None
