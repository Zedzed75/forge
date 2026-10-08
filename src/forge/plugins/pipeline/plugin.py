"""Pipeline domain plugin: implementation of the forge hooks.

This plugin differs from the three others on one single point: its
`forge_answers` declares the `context` parameter. pluggy only calls a hookimpl
with the arguments it names — the three other domains therefore had nothing to
change when that parameter was added to the hookspec.

What it does **not** do, and which is the substance of phase 8:

* it knows no domain by its name — the word "helm" appears in this package only
  in documentation and in the tool installation table, where it designates a
  binary, not a section of forge.yml;
* it invents no command — each domain declares its own (`forge_validators`,
  `forge_deploy`), and a domain silent about deployment is named in the generated
  pipeline rather than guessed;
* it does not make the core a scheduler — the core assembles a
  `GenerationContext` from hooks it already called, and draws no conclusion from
  it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge.interview.prompter import Prompter
from forge.plugins.pipeline import answers as answers_module
from forge.plugins.pipeline import tools as tools_module
from forge.plugins.pipeline import validators as validators_module
from forge.plugins.pipeline.spec import PipelineSpec
from forge.plugins_api.hookspecs import hookimpl
from forge.plugins_api.types import (
    CatalogEntry,
    Command,
    DomainInfo,
    GenerationContext,
    Issue,
)
from forge.spec.service import ServiceSpec


@hookimpl
def forge_domain() -> DomainInfo:
    return DomainInfo(
        name="pipeline",
        title="Pipeline",
        summary="Integration pipeline: one job per domain, build, deploy",
        # A CI file only exists where its tool reads it: neither GitHub nor
        # GitLab looks for it in a subdirectory. The only domain of the project
        # whose output is the root of the repository.
        outdir=".",
    )


@hookimpl
def forge_spec_model() -> type[PipelineSpec]:
    return PipelineSpec


@hookimpl
def forge_template_subdir() -> str:
    return "src/forge/plugins/pipeline/template"


@hookimpl
def forge_answers(spec: Any, context: GenerationContext) -> dict[str, Any]:
    """The only hookimpl of the project to declare `context`: it is its reason for being."""
    return answers_module.build(spec, context)


@hookimpl
def forge_validators(spec: Any, outdir: Path) -> list[Command]:
    return validators_module.commands(spec, outdir)


@hookimpl
def forge_check_spec(spec: Any) -> list[Issue]:
    """Checks the sub-model cannot do: it does not see `service:`."""
    if getattr(spec, "pipeline", None) is None:
        return []
    return answers_module.cross_check(spec)


@hookimpl
def forge_catalog() -> list[CatalogEntry]:
    """Tools the pipeline knows how to install.

    The catalogue of this domain is not a list of resources but the answer to the
    only question a user asks here: "will my pipeline know how to install what my
    domains want to run?"
    """
    return [
        CatalogEntry(
            name=recipe.name,
            summary=recipe.summary,
            details=_details(recipe),
        )
        for recipe in tools_module.INSTALLS
    ]


def _details(recipe: Any) -> str:
    """How the pipeline installs this tool, literally."""
    lines = ["Installed by the pipeline with:", ""]
    if recipe.requires:
        lines.append(f"  # system packages: {', '.join(recipe.requires)}")
    lines += [f"  {line}" for line in recipe.steps]
    if recipe.exports:
        lines += ["", "Variables set afterwards:"]
        lines += [f"  {key}={value}" for key, value in sorted(recipe.exports.items())]
    lines += [
        "",
        "A tool absent from this list is never guessed: the generated pipeline",
        "carries a step that fails while naming it.",
    ]
    return "\n".join(lines)


@hookimpl
def forge_interview(prompter: Prompter, service: ServiceSpec) -> dict[str, Any] | None:
    from forge.plugins.pipeline import interview

    return interview.run(prompter, service)
