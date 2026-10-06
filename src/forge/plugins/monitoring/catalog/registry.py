"""Access to the catalogue of rule families.

The same role as the registries of the three other domains: a single entry point,
so that the canonical order is that of the catalogue and not that of the
specification. Two specifications that quote the same families in a different
order must produce the same project.
"""

from __future__ import annotations

from forge.plugins.monitoring.catalog.alerts import Alert
from forge.plugins.monitoring.catalog.families import BY_NAME, FAMILIES, Family


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


def all_alerts() -> tuple[Alert, ...]:
    """All the alerts of the catalogue, families taken together."""
    return tuple(alert for family in FAMILIES for alert in family.alerts)
