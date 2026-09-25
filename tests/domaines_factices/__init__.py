"""Fake domains used by the core tests.

Every module in this package is a complete plugin, importable by its dotted
path: the tests can therefore declare them through `FORGE_PLUGINS` and exercise
the CLI end to end with **several** domains — which the `demo` plugin alone does
not allow (`--only` filtering, failing cross-domain checks).

They are never registered in production: `BUILTIN_PLUGINS` stays free of them.
"""

from __future__ import annotations

from typing import Any

from forge.plugins_api.types import Projection
from forge.spec.types import ForgeModel


class TrivialSection(ForgeModel):
    """A forge.yml section with no useful content: only the projection matters."""

    #: Symbolic presence, so that the section has at least one field.
    enabled: bool = True


def standard_projection(spec: Any) -> Projection:
    """Projection faithful to the specification: the comparison reference."""
    return Projection(
        service_name=spec.service.name,
        environments=tuple(env.name for env in spec.service.environments),
        labels=dict(spec.service.labels),
    )
