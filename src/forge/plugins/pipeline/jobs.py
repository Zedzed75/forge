"""Derivation of the jobs from what the other domains declare.

The heart of phase 8. **No domain name appears here**: everything comes from the
`GenerationContext`, which only speaks `DomainInfo`, `Command` and `Projection`.
Adding a domain to forge therefore adds a job to this pipeline without one line
of this module changing — that is the property to preserve.

Three non-trivial translations are done here, and they are worth reading:

* **the stdin chaining.** `forge validate` runs `kubeconform` on the output of
  `helm template` while keeping the latter in memory. A CI file has no such
  memory: the source writes into a file, the consumer reads it back. A
  redirection rather than a pipe, because `pipefail` does not exist in the
  `/bin/sh` of a Debian image and a pipe would hide the failure of the source
  there.
* **the working directory.** `Command.cwd` is a path relative to the root of the
  project — the core builds it that way for this module. It becomes
  `working-directory` on GitHub, a `cd` on GitLab.
* **the human approval.** GitLab declares it in the file (`when: manual`); GitHub
  declares it in the repository settings, the file only carrying the name of the
  environment. The GitHub template says so in a comment rather than letting one
  believe the file is enough.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from typing import Any

from forge.plugins.pipeline import tools
from forge.plugins.pipeline.enums import JobKind
from forge.plugins_api.types import Command, DomainSummary, GenerationContext

#: Prefix of the intermediate files of the stdin chaining.
STDIN_PREFIX = "/tmp/forge-"


@dataclass
class Step:
    """A job step: a label, shell lines, a context."""

    name: str
    run: list[str] = field(default_factory=list)
    workdir: str = ""
    env: dict[str, str] = field(default_factory=dict)

    def script(self) -> list[str]:
        """Self-contained lines: directory and variables carried by the line itself.

        GitLab has neither `working-directory` nor per-step variables — a job is
        one single script. The `cd` is enclosed in a subshell so that it does not
        leak onto the next line.
        """
        prefix = "".join(f"{key}={shlex.quote(value)} " for key, value in sorted(self.env.items()))
        lines = []
        for line in self.run:
            complete = prefix + line
            if self.workdir:
                complete = f"(cd {shlex.quote(self.workdir)} && {complete})"
            lines.append(complete)
        return lines

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "run": self.run,
            "workdir": self.workdir,
            "env": self.env,
            "script": self.script(),
        }


@dataclass
class Job:
    """A job of the pipeline."""

    key: str
    name: str
    kind: str
    steps: list[Step] = field(default_factory=list)
    needs: list[str] = field(default_factory=list)
    environment: str = ""
    manual: bool = False
    default_branch_only: bool = False
    #: Tools this job installs, and those it does not know how to install.
    tool_names: list[str] = field(default_factory=list)
    unknown_tools: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "kind": self.kind,
            "steps": [step.as_dict() for step in self.steps],
            "needs": self.needs,
            "environment": self.environment,
            "manual": self.manual,
            "default_branch_only": self.default_branch_only,
            "tools": self.tool_names,
            "unknown_tools": self.unknown_tools,
        }


# ---------------------------------------------------------------------------
# Translation of a Command into a step
# ---------------------------------------------------------------------------


def _slug(label: str) -> str:
    """File identifier derived from a command label."""
    kept = [c if c.isalnum() else "-" for c in label.lower()]
    return "".join(kept).strip("-").replace("---", "-").replace("--", "-")


def _shell(command: Command, redirection: str = "") -> str:
    """Shell line equivalent to a command, arguments quoted where needed."""
    pieces = [command.tool, *command.argv]
    line = " ".join(shlex.quote(piece) for piece in pieces)
    return f"{line} {redirection}".rstrip()


def portable_env(command: Command) -> dict[str, str]:
    """Environment variables of a command, purged of what is local.

    `Command.env` configures a run **on the workstation**: the path of the Ansible
    collections, a Terraform provider cache, a Kubernetes schema mirror. These
    values are read from the process environment at generation time; copying them
    into a CI file would write the path of a development workstation there, and
    would make the output **depend on the machine that produced it** — a golden
    file could no longer be compared.

    The criterion is deliberately coarse — a value that looks like a path is set
    aside — but it errs in the right direction: what remains (`NO_COLOR=1`,
    `TF_IN_AUTOMATION=1`) is behaviour tuning, valid everywhere. What a tool needs
    to find on the runner is supplied by its installation recipe, written for the
    runner.
    """
    return {
        key: value
        for key, value in command.env
        if not _looks_like_a_path(value)
    }


def _looks_like_a_path(value: str) -> bool:
    """True when the value designates a location on the filesystem."""
    return "/" in value or "\\" in value or (len(value) > 1 and value[1] == ":")


def _workdir(command: Command) -> str:
    """Working directory, relative to the root of the project."""
    if command.cwd is None:
        return ""
    path = command.cwd.as_posix()
    return "" if path in (".", "") else path


def steps_for(commands: tuple[Command, ...]) -> list[Step]:
    """Translate a sequence of `Command`s into steps, stdin chaining included."""
    sources = {
        command.stdin_from for command in commands if command.stdin_from
    }
    steps: list[Step] = []
    for command in commands:
        redirection = ""
        if command.label in sources:
            redirection = f"> {STDIN_PREFIX}{_slug(command.label)}.out"
        elif command.stdin_from:
            redirection = f"< {STDIN_PREFIX}{_slug(command.stdin_from)}.out"
        steps.append(
            Step(
                name=command.label,
                run=[_shell(command, redirection)],
                workdir=_workdir(command),
                env=portable_env(command),
            )
        )
    return steps


def install_step(
    names: tuple[str, ...], provider: str
) -> tuple[Step | None, list[str], list[str]]:
    """Tool installation step, and the known / unknown split.

    The variables a recipe sets are not carried over the same way: each `run:` of
    GitHub is a fresh shell, and only one written into `$GITHUB_ENV` survives to
    the next step; a GitLab job is one single shell, where an `export` is enough.
    """
    known, unknown = tools.resolve(names)
    lines: list[str] = []
    packages = tools.system_packages(known)
    if packages:
        lines.append(
            "if command -v apt-get >/dev/null; then apt-get update -qq && "
            f"apt-get install -y -qq --no-install-recommends {' '.join(packages)}; fi"
        )
    exports: dict[str, str] = {}
    for recipe in known:
        lines.extend(recipe.steps)
        exports.update(recipe.exports)
    for key, value in sorted(exports.items()):
        if provider == "github":
            lines.append(f'echo "{key}={value}" >> "$GITHUB_ENV"')
        else:
            lines.append(f'export {key}="{value}"')
    for missing in unknown:
        # Never guessed: the step fails while naming the missing tool, rather than
        # letting the job fail further on with a "command not found".
        #
        # This message is a line of the generated CI file, not prose of the
        # plugin. No golden spec declares an unknown tool, so no reference
        # output carries it — which is why translating it moves nothing.
        lines.append(
            f'echo "forge cannot install {missing}: complete this step" >&2'
        )
        lines.append("exit 1")
    if not lines:
        return None, [recipe.name for recipe in known], unknown
    return (
        Step(name="Install the tools", run=lines),
        [recipe.name for recipe in known],
        unknown,
    )


# ---------------------------------------------------------------------------
# Building the jobs
# ---------------------------------------------------------------------------


def _job_for_commands(
    key: str, name: str, kind: JobKind, commands: tuple[Command, ...], provider: str
) -> Job:
    """Job installing what is needed, then running `commands` in order."""
    names = tuple(sorted({command.tool for command in commands}))
    installation, known, unknown = install_step(names, provider)
    steps = [installation] if installation else []
    steps += steps_for(commands)
    return Job(
        key=key,
        name=name,
        kind=kind.value,
        steps=steps,
        tool_names=known,
        unknown_tools=unknown,
    )


def validate_jobs(context: GenerationContext, provider: str) -> list[Job]:
    """One validation job per requested domain, the pipeline itself included.

    The `pipeline` domain validates its own output: it is a domain like any other
    from the point of view of this module, and excluding it would be the only
    place where it treated itself apart.
    """
    jobs: list[Job] = []
    for summary in context.domains:
        if not summary.validators:
            continue
        jobs.append(
            _job_for_commands(
                key=f"validate-{summary.name}",
                name=f"Validate {summary.info.title}",
                kind=JobKind.VALIDATE,
                commands=summary.validators,
                provider=provider,
            )
        )
    return jobs


def build_job(build: Any, service_name: str, provider: str) -> Job:
    """Job building and publishing the image.

    No credential is written: the connection to the registry uses the token the CI
    tool already supplies (`GITHUB_TOKEN`, `CI_REGISTRY_PASSWORD`).
    """
    image = build.image or service_name
    reference = f"{build.registry}/{image}"
    platforms = ",".join(build.platforms)
    lines = [
        "docker buildx create --use --name forge-builder 2>/dev/null || "
        "docker buildx use forge-builder",
        " ".join(
            [
                "docker buildx build",
                f"--platform {platforms}",
                f"--file {shlex.quote(build.dockerfile)}",
                # Quotes mandatory around the expansion: without them, shellcheck
                # reports SC2086 ("double quote to prevent globbing and word
                # splitting") and actionlint fails the job. It is not zeal: a tag
                # containing a blank or a wildcard character would be split into
                # several arguments.
                f'--tag "{reference}:$FORGE_IMAGE_TAG"',
                "--push" if build.push else "--load",
                shlex.quote(build.context),
            ]
        ),
    ]
    job = Job(
        key="build",
        name="Build the image",
        kind=JobKind.BUILD.value,
        steps=[Step(name=f"docker buildx build ({reference})", run=lines)],
        default_branch_only=build.push,
    )
    job.steps[0].env = {"FORGE_IMAGE_TAG": _tag_expression(provider)}
    return job


def _tag_expression(provider: str) -> str:
    """Expression giving the tag of the image, specific to each CI tool.

    The tag is the fingerprint of the commit, never `latest`: two builds of the
    same `latest` produce two different images under the same name, and nothing
    says which one is running.
    """
    return "${{ github.sha }}" if provider == "github" else "$CI_COMMIT_SHA"


def deploy_jobs(
    context: GenerationContext,
    environments: tuple[str, ...],
    production: str,
    provider: str,
    *,
    manual_for_production: bool,
    sequential: bool,
    needs: list[str],
) -> list[Job]:
    """One deployment job per environment, all domains taken together.

    One single job per environment rather than one per (domain, environment)
    pair: within the same environment, the domains deploy in the order they
    declare themselves (`DomainInfo.deploy_order`) — the base layer before what
    rests on it. Sorting by name would have sent a chart off before the
    infrastructure that creates its namespace, which no generic sort could have
    guessed.
    """
    ordered = sorted(context.domains, key=lambda s: (s.info.deploy_order, s.name))
    jobs: list[Job] = []
    previous: str | None = None
    for name in environments:
        commands: list[Command] = []
        for summary in ordered:
            commands.extend(_deployment_for(summary, name))
        if not commands:
            continue
        job = _job_for_commands(
            key=f"deploy-{name}",
            # Key and label are both identifiers, appearances notwithstanding:
            # on GitHub the key names the job in `needs:` and the label is the
            # name of the "required status check" a branch protection rule
            # compares against. Neither is translatable prose, so both stay in
            # English.
            name=f"Deploy {name}",
            kind=JobKind.DEPLOY,
            commands=tuple(commands),
            provider=provider,
        )
        job.environment = name
        job.default_branch_only = True
        job.manual = manual_for_production and name == production
        job.needs = list(needs) + ([previous] if sequential and previous else [])
        jobs.append(job)
        previous = job.key
    return jobs


def _deployment_for(summary: DomainSummary, environment: str) -> tuple[Command, ...]:
    """Deployment commands of the domain for this environment, or nothing."""
    for name, commands in summary.deployments:
        if name == environment:
            return commands
    return ()


def undeployed(
    context: GenerationContext, environments: tuple[str, ...], self_name: str
) -> list[str]:
    """Requested domains that do not say how they deploy.

    The pipeline does not invent their command: it names them, so that the absence
    of a deployment job is an observation and not an oversight.

    The calling domain excludes itself: a pipeline does not deploy itself, it is
    the deployment. That is the **only** place in this module where a domain is
    treated differently from the others, and it owes that only to its own identity
    — never to the knowledge of another.
    """
    if not environments:
        return []
    return sorted(
        summary.name
        for summary in context.domains
        if summary.name != self_name
        and not any(_deployment_for(summary, name) for name in environments)
    )
