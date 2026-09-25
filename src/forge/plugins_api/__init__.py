"""Plugin contract: exchanged types, hookspecs and the management facade."""

from forge.plugins_api.types import (
    CatalogEntry,
    Command,
    DomainInfo,
    Issue,
    Projection,
)

__all__ = ["CatalogEntry", "Command", "DomainInfo", "Issue", "Projection"]
