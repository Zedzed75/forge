# The plugin contract

**This file is generated. Do not edit it by hand.**

It is produced by `scripts/render_plugin_contract.py` from the modules quoted
below, and `tests/test_plugin_contract_doc.py` fails if the two disagree. To
change the contract, change the module and re-run:

```bash
python scripts/render_plugin_contract.py
```

This was `DESIGN.md` §2.1 and §2.2 until ZED-233. Those sections held a
hand-maintained copy of the same two modules, and the copy had drifted: it
declared `Command.argv` as `list[str]` where the module says
`tuple[str, ...]`, omitted `DomainInfo.deploy_order`, `CatalogEntry`,
`DomainSummary` and `GenerationContext`, and did not mention the
`forge_deploy` hook. That is D13's failure mode, so the fix is a generator
rather than a correction - a correction would only have reset the clock.

The section numbers are unchanged, so an existing citation of "DESIGN.md §2.1"
or "§2.2" resolves here, and `DESIGN.md` §2.1/§2.2 are pointers to this file.
§2.3 and §2.4 stay in `DESIGN.md`: they are prose about *using* the contract,
not a reproduction of it.

This file is named in `TRACKED_PROSE` in `scripts/check_file_sizes.py`, so it
caps itself at the same thresholds as the other registers. Being generated, it
grows only when the contract does - which is the signal that cap is for.

---

## 2.1 Exchanged types

The dataclasses the core and a plugin pass between them. Every field carries its own comment; those comments are the specification.

Source: [`src/forge/plugins_api/types.py`](../src/forge/plugins_api/types.py)

```python
"""Types exchanged between the core and the plugins (DESIGN.md §2.1).

All immutable: a plugin cannot alter after the fact what it declared, and the
core can compare or hash them without surprise.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class DomainInfo:
    """Identity of a generatable domain."""

    #: Section key in forge.yml and plugin name (e.g. "ansible").
    name: str

    #: Display label (e.g. "Ansible").
    title: str

    #: One-line summary, printed by `forge plugins`.
    summary: str

    #: Output subdirectory in the target; defaults to `name`.
    outdir: str = ""

    #: Deployment rank: **the smallest goes first**. The foundation before what
    #: sits on it — a namespace before the chart installed into it.
    #:
    #: It exists because no generic ordering could replace it. Alphabetical order
    #: deployed the chart before the infrastructure hosting its namespace;
    #: registration order would have made a real deployment depend on the order
    #: of a list of modules. It is a property of the domain, so the domain
    #: declares it — the core merely sorts.
    #:
    #: The default puts a domain after infrastructure and machine configuration:
    #: the most frequent case, that of an application workload.
    deploy_order: int = 50

    def __post_init__(self) -> None:
        if not self.outdir:
            object.__setattr__(self, "outdir", self.name)


@dataclass(frozen=True)
class Command:
    """An external validation command declared by a plugin."""

    #: Label reused as-is in the report (e.g. "helm lint (prod)").
    label: str

    #: Binary to locate (e.g. "helm", "ansible-lint").
    tool: str

    #: Arguments, without the binary.
    argv: tuple[str, ...] = ()

    #: Working directory; defaults to the domain directory.
    cwd: Path | None = None

    #: Label of a command whose stdout feeds this one's stdin.
    stdin_from: str | None = None

    #: Maximum execution time, in seconds.
    timeout: int = 300

    #: Environment variables added to those of the process, sorted at execution
    #: time so they stay deterministic. Some tools can only be configured
    #: through this channel — `ANSIBLE_COLLECTIONS_PATH`, `HELM_CACHE_HOME`… —
    #: and the plugin is the only one that knows which it needs.
    env: tuple[tuple[str, str], ...] = ()

    #: Message printed when the binary is absent from the PATH.
    install_hint: str = ""

    #: Allows the WSL fallback under Windows (tool that does not run natively).
    requires_linux: bool = False


@dataclass(frozen=True)
class Issue:
    """A cross-domain validation finding."""

    #: "error" makes `forge validate` fail; "warning" is only reported.
    level: Literal["error", "warning"]

    #: Actionable sentence describing the problem.
    message: str

    #: Suggested fix.
    hint: str = ""

    #: Domains involved, to situate the finding.
    domains: tuple[str, ...] = ()


@dataclass(frozen=True)
class Projection:
    """What a domain claims to produce, with no domain vocabulary.

    The core compares projections with one another: two domains declaring the
    same facet must declare the same value. That mechanism — and not rules of the
    form "if ansible then…" — is what implements the cross-domain checks
    (DESIGN.md §2.1, decision Q4).
    """

    #: Service name as this domain uses it.
    service_name: str

    #: Environments this domain materialises, in order.
    environments: tuple[str, ...]

    #: Labels this domain puts on what it produces.
    labels: dict[str, str] = field(default_factory=dict)

    #: Free-form facets; compared only when two domains declare them.
    facets: dict[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class CatalogEntry:
    """An entry in a domain catalogue (Ansible role, Helm component...)."""

    #: Identifier used in forge.yml.
    name: str

    #: One-line summary.
    summary: str

    #: Long description, printed by `forge catalog <domain> <entry>`.
    details: str = ""

    #: Recognised options: name -> description.
    options: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class DomainSummary:
    """What a domain requested by the specification declares about itself.

    Assembled by the core from hooks that already existed — no new knowledge
    enters here. It serves the `pipeline` domain, which must emit one job per
    domain present **without knowing any domain by name**: all it reads here is
    contract vocabulary (`DomainInfo`, `Command`, `Projection`).
    """

    #: Identity of the domain.
    info: DomainInfo

    #: What the domain claims to produce, or None if it does not declare it.
    projection: Projection | None = None

    #: Validation commands, paths **relative to the project root**.
    validators: tuple[Command, ...] = ()

    #: Deployment commands, per environment, in specification order:
    #: `(("prod", (cmd, ...)), ...)`. Empty when the domain does not declare how
    #: to deploy itself — in which case the pipeline generates a step to fill in
    #: rather than a guessed command.
    deployments: tuple[tuple[str, tuple[Command, ...]], ...] = ()

    @property
    def name(self) -> str:
        """Name of the domain."""
        return self.info.name

    def tools(self) -> tuple[str, ...]:
        """External tools named by this domain, sorted and deduplicated."""
        named = {command.tool for command in self.validators}
        named |= {
            command.tool for _, commands in self.deployments for command in commands
        }
        return tuple(sorted(named))


@dataclass(frozen=True)
class GenerationContext:
    """The core's view of the requested domains, passed to `forge_answers`.

    The core orchestrates nothing: it passes on facts it already computes, in
    the vocabulary of the contract. It is up to the plugin to decide what to do
    with them.
    """

    #: Domains requested by the specification, in registration order.
    domains: tuple[DomainSummary, ...] = ()

    def names(self) -> tuple[str, ...]:
        """Names of the requested domains."""
        return tuple(summary.name for summary in self.domains)

    def get(self, name: str) -> DomainSummary | None:
        """Summary of domain `name`, or None if it is not requested."""
        for summary in self.domains:
            if summary.name == name:
                return summary
        return None

    def others(self, name: str) -> tuple[DomainSummary, ...]:
        """Every requested domain except `name`."""
        return tuple(summary for summary in self.domains if summary.name != name)

    def tools(self) -> tuple[str, ...]:
        """External tools named by all the domains together, sorted."""
        return tuple(sorted({tool for s in self.domains for tool in s.tools()}))
```

---

## 2.2 Hookspecs

The pluggy hook specifications. `forge_domain` is mandatory; the rest are optional, and a domain implements the ones it needs.

Source: [`src/forge/plugins_api/hookspecs.py`](../src/forge/plugins_api/hookspecs.py)

```python
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
```
