"""Plugin `demo` — test bench for the plugin contract, reserved for the tests.

It is not registered by default (`BUILTIN_PLUGINS` is empty): the tests declare
it through `FORGE_PLUGINS=forge.plugins.demo.plugin`. Its reason to exist is to
exercise, from phase 2 onwards, the mechanisms the real plugins would use in
phases 3 and 4:

* **nested** `yield` tags (environment x widget) in paths;
* plugin filter injected by a Jinja extension (`forge.plugins.demo.jinja_ext`);
* file filtering by `[% if %]` on a path segment;
* external validation command, with a fallback when the tool is missing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field, field_validator

from forge.interview.prompter import Prompter
from forge.plugins_api.hookspecs import hookimpl
from forge.plugins_api.types import CatalogEntry, Command, DomainInfo, Projection
from forge.spec.names import require_unique
from forge.spec.service import ServiceSpec
from forge.spec.types import DnsLabel, ForgeModel

#: Widget kinds the demonstration domain recognises.
WIDGET_KINDS = ("gauge", "counter", "log")


class DemoWidget(ForgeModel):
    """A widget to materialise in every environment."""

    #: Name of the widget: a DNS label, also used as the file name.
    name: DnsLabel

    #: Kind of widget; determines the generated content.
    kind: str = "gauge"

    #: Marks a widget producing an extra file (exercises the `[% if %]`).
    detailed: bool = False

    @field_validator("kind")
    @classmethod
    def _known_kind(cls, value: str) -> str:
        if value not in WIDGET_KINDS:
            raise ValueError(f"unknown kind: {value} (expected: {', '.join(WIDGET_KINDS)})")
        return value


class DemoSpec(ForgeModel):
    """`demo:` section of forge.yml."""

    #: Widgets to generate, in declaration order.
    widgets: list[DemoWidget] = Field(min_length=1)

    #: Greeting repeated in the header of the generated files. The value is
    #: fixture data, not prose: `demo-minimal` renders this default into its
    #: `.copier-answers.yml`, so it moves with the reference specs, not here.
    greeting: str = "bonjour"

    @field_validator("widgets")
    @classmethod
    def _unique_names(cls, value: list[DemoWidget]) -> list[DemoWidget]:
        require_unique((widget.name for widget in value), "widget names")
        return value


@hookimpl
def forge_domain() -> DomainInfo:
    return DomainInfo(
        name="demo",
        title="Demo",
        summary="Demonstration domain, used by the core tests",
    )


@hookimpl
def forge_spec_model() -> type[DemoSpec]:
    return DemoSpec


@hookimpl
def forge_template_subdir() -> str:
    return "src/forge/plugins/demo/template"


@hookimpl
def forge_answers(spec: Any) -> dict[str, Any]:
    """Project the spec onto the `domain` dict, with a frozen key order."""
    demo: DemoSpec = spec.demo
    return {
        "greeting": demo.greeting,
        "environments": [
            {"name": env.name, "production": env.production}
            for env in spec.service.environments
        ],
        "widgets": [
            {"name": widget.name, "kind": widget.kind, "detailed": widget.detailed}
            for widget in demo.widgets
        ],
    }


@hookimpl
def forge_projection(spec: Any) -> Projection:
    return Projection(
        service_name=spec.service.name,
        environments=tuple(env.name for env in spec.service.environments),
        labels=dict(spec.service.labels),
        facets={"widgets": tuple(widget.name for widget in spec.demo.widgets)},
    )


@hookimpl
def forge_validators(spec: Any, outdir: Path) -> list[Command]:
    """A deliberately mundane command: the demo domain validates nothing real."""
    return [
        Command(
            label="demo: version of git",
            tool="git",
            argv=("--version",),
            cwd=outdir,
            install_hint="install git and add it to the PATH",
        )
    ]


@hookimpl
def forge_catalog() -> list[CatalogEntry]:
    return [
        CatalogEntry(
            name=kind,
            summary=f"Widget of kind {kind}",
            details=f"Generates one file per environment for a {kind} widget.",
            options={"detailed": "adds one detail file per widget"},
        )
        for kind in WIDGET_KINDS
    ]


@hookimpl
def forge_interview(prompter: Prompter, service: ServiceSpec) -> dict[str, Any] | None:
    """Minimal interview: it checks the wiring of the hook, not the ergonomics.

    The core has already asked *which* domains to generate: the plugin does not
    ask again. It declines by returning None, here when no widget is named.
    """
    greeting = prompter.text("Greeting used in the headers", default="bonjour")
    names = prompter.text("Widgets, separated by commas", default="cpu,memory")
    widgets = []
    for name in (part.strip() for part in names.split(",")):
        if not name:
            continue
        kind = prompter.select(
            f"Kind of the {name} widget",
            choices=[(kind, kind) for kind in WIDGET_KINDS],
            default="gauge",
        )
        widgets.append({"name": name, "kind": kind})
    if not widgets:
        return None
    return {"greeting": greeting, "widgets": widgets}
