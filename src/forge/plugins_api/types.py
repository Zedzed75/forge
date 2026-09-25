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
