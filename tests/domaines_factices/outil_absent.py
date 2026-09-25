"""Fake domain whose validator relies on a tool that does not exist.

It exercises, end to end, the two behaviours the core promises in the face of a
missing tool: explicit failure by default, accepted skip with `--skip-missing` —
together with a warning, because a green report where nothing ran is a trap.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge.plugins_api.hookspecs import hookimpl
from forge.plugins_api.types import Command, DomainInfo, Projection
from tests.domaines_factices import TrivialSection, standard_projection

#: Binary deliberately impossible to find on every platform.
MISSING_TOOL = "forge-tool-that-does-not-exist"


@hookimpl
def forge_domain() -> DomainInfo:
    return DomainInfo(
        name="fragile", title="Fragile", summary="Fake domain with a missing tool"
    )


@hookimpl
def forge_spec_model() -> type[TrivialSection]:
    return TrivialSection


@hookimpl
def forge_template_subdir() -> str:
    return "src/forge/plugins/demo/template"


@hookimpl
def forge_answers(spec: Any) -> dict[str, Any]:
    return {"enabled": spec.fragile.enabled}


@hookimpl
def forge_projection(spec: Any) -> Projection:
    return standard_projection(spec)


@hookimpl
def forge_validators(spec: Any, outdir: Path) -> list[Command]:
    return [
        Command(
            label="fragile: missing tool",
            tool=MISSING_TOOL,
            cwd=outdir,
            install_hint="this tool does not exist, that is the point of the test",
        )
    ]
