"""The project's pluggy hookspecs (DESIGN.md §2.2).

Rule: no `firstresult=True` on domain-specific hooks — they would be silently
captured by the first registered plugin. The core addresses one domain at a time
through `manager.domain(name)` (DESIGN.md §2.3).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pluggy

from forge.plugins_api.types import (
    CatalogEntry,
    Command,
    DomainInfo,
    GenerationContext,
    Issue,
    Projection,
)

if TYPE_CHECKING:  # pragma: no cover - annotations only
    from pydantic import BaseModel

    from forge.interview.prompter import Prompter
    from forge.spec.service import ServiceSpec

#: pluggy project name; identical on the hookspec and hookimpl sides.
PROJECT_NAME = "forge"

hookspec = pluggy.HookspecMarker(PROJECT_NAME)
hookimpl = pluggy.HookimplMarker(PROJECT_NAME)


@hookspec
def forge_domain() -> DomainInfo:
    """Identity of the domain. The only hook required to be discovered."""


@hookspec
def forge_spec_model() -> type[BaseModel]:
    """Pydantic sub-model validating the <domain> section of forge.yml.

    The core assembles the root model from the registered sub-models: every
    section is optional, and an absent section means "domain not generated". The
    core knows nothing about its content.
    """


@hookspec
def forge_interview(prompter: Prompter, service: ServiceSpec) -> dict[str, Any] | None:
    """Conduct the domain interview and return its forge.yml section.

    The plugin drives its questionnaire through the `Prompter` protocol provided
    by the core, never questionary directly: that is what makes the interview
    replayable in tests. Returns None if the user declines the domain.
    """


@hookspec
def forge_template_subdir() -> str:
    """Path of the copier template, relative to the forge repository root.

    Example: "src/forge/plugins/ansible/template". Passed to copier through
    `_subdirectory` (DESIGN.md §5).

    Declare it as it sits in the repository, as above. An installed forge renders
    from the package directory instead, where the same template is one prefix
    shorter; the core shortens it (`copier_runner.resolve_subdir`) rather than
    asking every plugin to know which of the two roots is in play
    (DESIGN.md §8 Q2-bis).
    """


@hookspec
def forge_answers(spec: Any, context: GenerationContext) -> dict[str, Any]:
    """Project the unified spec onto the `domain` dict passed to copier.

    The output is JSON-serialisable and deterministic: it is written as-is into
    `.copier-answers.yml` and replayed by `copier update`.

    `context` describes **the other domains requested by the specification**, in
    the vocabulary of the contract: their `DomainInfo`, their `Projection`, and
    their validation and deployment `Command`s. A plugin that does not need it
    simply does not declare the parameter — pluggy calls a hookimpl only with the
    arguments it names, and the first three domains do without it.

    It exists for the `pipeline` domain, whose output depends on the other
    sections: it must emit one job per domain present **without knowing any
    domain by name**. The core still orchestrates nothing — it passes on facts it
    was already computing.
    """


@hookspec
def forge_validators(spec: Any, outdir: Path) -> list[Command]:
    """External commands validating the generated domain, in execution order."""


@hookspec
def forge_deploy(spec: Any, outdir: Path, environment: str) -> list[Command]:
    """Commands deploying this domain into `environment` (optional).

    Symmetrical to `forge_validators`, and subject to the same rule: the plugin
    describes **what to run**, never how to run it. The difference is that a
    deployment touches real infrastructure — the core never runs these itself.
    They exist only to be **written** into a pipeline by the `pipeline` domain,
    which could not invent them.

    A domain that does not implement it causes a step to fill in to be emitted,
    rather than a guessed command.
    """


@hookspec
def forge_projection(spec: Any) -> Projection:
    """What the domain claims to produce, for the cross-domain checks."""


@hookspec
def forge_check_spec(spec: Any) -> list[Issue]:
    """Checks the domain sub-model cannot perform on its own.

    A pydantic sub-model only sees **its** section: it can check that the groups
    it names exist, never that the environments exist, since those are declared
    in the shared `service:` block.

    The core calls this hook right after assembling the model, **before any
    rendering**: an inconsistent specification must be refused at generation
    time, not only at the next `forge validate`. An `Issue` of level `error`
    stops generation; a `warning` is printed and lets it through.

    Not to be confused with `forge_consistency`, which covers the **already
    written** project and therefore receives the output directories.
    """


@hookspec
def forge_consistency(spec: Any, outdirs: dict[str, Path]) -> list[Issue]:
    """Extra checks specific to the plugin (escape hatch).

    The only hook called on *all* plugins at once; the results are concatenated.
    To be used only for what `forge_projection` cannot express.
    """


@hookspec
def forge_catalog() -> list[CatalogEntry] | None:
    """Catalogue browsable through `forge catalog <domain>` (optional)."""
