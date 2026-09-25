"""A fake domain **the pipeline plugin has never seen**.

It is the witness of the phase 8 promise: the `pipeline` domain emits one job
per requested domain *without knowing any domain by name*. If that promise held
by accident — because the four shipped domains were written at the same time as
it was — this module would reveal it.

On top of that it declares a tool the pipeline's installation table does not
know: `house-tool`. The pipeline must not guess it, but emit a step that fails
while naming it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge.plugins_api.hookspecs import hookimpl
from forge.plugins_api.types import Command, DomainInfo, Projection
from tests.fake_domains import TrivialSection, standard_projection

#: Tool absent from `forge.plugins.pipeline.tools.INSTALLS`, and meant to stay so.
UNKNOWN_TOOL = "house-tool"


@hookimpl
def forge_domain() -> DomainInfo:
    return DomainInfo(
        name="unknown",
        title="Unknown Domain",
        summary="Fake domain the pipeline has never seen",
        # Between the foundation (10) and machine configuration (30): sorting by
        # rank must place it there, and not at its alphabetical position.
        deploy_order=20,
    )


@hookimpl
def forge_spec_model() -> type[TrivialSection]:
    return TrivialSection


@hookimpl
def forge_template_subdir() -> str:
    return "src/forge/plugins/demo/template"


@hookimpl
def forge_answers(spec: Any) -> dict[str, Any]:
    return {"enabled": spec.unknown.enabled}


@hookimpl
def forge_projection(spec: Any) -> Projection:
    return standard_projection(spec)


@hookimpl
def forge_validators(spec: Any, outdir: Path) -> list[Command]:
    """Two commands, one of them chained through stdin like the Helm domain."""
    return [
        Command(
            label="unknown render",
            tool=UNKNOWN_TOOL,
            argv=("render", "--all"),
            cwd=outdir,
            env=(("NO_COLOR", "1"), ("LOCAL_PATH", "/opt/somewhere")),
        ),
        Command(
            label="unknown check",
            tool=UNKNOWN_TOOL,
            argv=("check", "-"),
            cwd=outdir / "subdirectory",
            stdin_from="unknown render",
        ),
    ]


@hookimpl
def forge_deploy(spec: Any, outdir: Path, environment: str) -> list[Command]:
    return [
        Command(
            label=f"unknown deployment ({environment})",
            tool=UNKNOWN_TOOL,
            argv=("apply", "--env", environment),
            cwd=outdir,
        )
    ]
