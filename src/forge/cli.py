"""forge's command line interface (DESIGN.md §7).

The CLI carries no logic: it reads arguments, calls `forge.pipeline` and formats
results. Every expected error derives from `ForgeError` and exits with code 1 and
a message, never a Python traceback.

The output is never coloured: it is read by tests as much as by humans, so
`NO_COLOR` has nothing to turn off.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from forge import __version__
from forge.errors import ForgeError, SpecValidationError
from forge.interview.prompter import Prompter, QuestionaryPrompter
from forge.interview.service_flow import ask_domains, ask_service
from forge.plugins_api.manager import ForgeManager, default_manager
from forge.render.copier_runner import DEFAULT_REF, ensure_directory
from forge.spec.assembly import FORGE_VERSION, validate_spec
from forge.spec.io import SPEC_FILENAME, save_spec
from forge.validate.consistency import format_issues
from forge.validate.tools import probe
from forge import pipeline

#: Where `forge update` sends the user to find out what it just moved. A URL and
#: not a path: the user is standing in their generated project, which has no copy
#: of forge's changelog and no reason to acquire one.
CHANGELOG_URL = "https://github.com/Zedzed75/forge/blob/master/CHANGELOG.md"

app = typer.Typer(
    name="forge",
    help="Generates complete, commented IaC projects from a single forge.yml.",
    add_completion=False,
    no_args_is_help=True,
)


def _split(value: str | None) -> list[str] | None:
    """Split an `--only a,b` option into a list, or None if absent."""
    if value is None:
        return None
    names = [part.strip() for part in value.split(",") if part.strip()]
    return names or None


def _echo_plan(manager: ForgeManager, result: pipeline.GenerationResult) -> None:
    """Announce what is about to be produced — or why nothing will be.

    The domains are a **choice**, never a bundle: a project may very well ask for
    only one. But forge still has to say which one, and must not answer with an
    empty project and no explanation when none is requested.
    """
    if not result.domains:
        known = ", ".join(manager.domain_names()) or "none"
        typer.echo(
            "this specification requests no domain: only the repository-level "
            "files will be written.\n"
            f"  available domains: {known}\n"
            "  add the matching section to forge.yml to generate one "
            "(an `ansible:` or `helm:` section, for instance)."
        )
        return
    verb = "would be produced" if result.dry_run else "produced"
    typer.echo(f"domain(s) {verb}:")
    for name in result.domains:
        info = manager.domain(name).info
        typer.echo(f"  {info.outdir}/  {info.title} — {info.summary}")


def _echo_warnings(result: pipeline.GenerationResult) -> None:
    """Print the non-blocking findings reported by the plugins."""
    for issue in result.warnings:
        scope = f" [{', '.join(issue.domains)}]" if issue.domains else ""
        typer.echo(f"[WARNING]{scope} {issue.message}", err=True)
        if issue.hint:
            typer.echo(f"          -> {issue.hint}", err=True)


def _fail(message: str) -> None:
    typer.echo(message, err=True)
    raise typer.Exit(code=1)


@app.callback(invoke_without_command=True)
def main(
    version: bool = typer.Option(
        False, "--version", help="Print the version and exit."
    ),
) -> None:
    """Entry point shared by every subcommand."""
    if version:
        typer.echo(f"forge {__version__}")
        raise typer.Exit()


# ---------------------------------------------------------------------------
# new
# ---------------------------------------------------------------------------


def run_new(
    target: Path,
    manager: ForgeManager,
    prompter: Prompter,
    *,
    spec_out: Path | None = None,
    only: list[str] | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> pipeline.GenerationResult:
    """Conduct the full interview then generate; testable without a terminal."""
    if only is not None:
        unknown = [name for name in only if name not in manager.domain_names()]
        if unknown:
            known = ", ".join(manager.domain_names()) or "none"
            raise SpecValidationError(
                f"unknown domain(s): {', '.join(unknown)} (registered: {known})"
            )
    # The target is checked before the interview: learning that it is invalid
    # after answering a dozen questions would be unacceptable.
    ensure_directory(Path(target), "target directory")

    service = ask_service(prompter)
    available = [
        (info.name, f"{info.title} — {info.summary}")
        for info in manager.domains()
        if only is None or info.name in only
    ]
    chosen = ask_domains(prompter, available)

    data: dict = {"forge_version": FORGE_VERSION, "service": service}
    validated_service = validate_spec(dict(data), manager).service
    for name in chosen:
        section = manager.domain(name).interview(prompter, validated_service)
        if section is not None:
            data[name] = section

    spec = validate_spec(data, manager)
    if spec_out is not None:
        save_spec(data, Path(spec_out), sections=list(spec.domain_names()))
    return pipeline.generate(
        data,
        spec,
        manager,
        target,
        force=force,
        dry_run=dry_run,
        spec_path=Path(spec_out) if spec_out is not None else None,
    )


@app.command("new")
def cmd_new(
    out: Path = typer.Option(Path("."), "--out", "-o", help="Target directory."),
    spec_out: Optional[Path] = typer.Option(
        None, "--spec-out", help="Also write the spec to this location."
    ),
    only: Optional[str] = typer.Option(
        None, "--only", help="Restrict to the named domains (comma-separated list)."
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite existing files."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Write nothing."),
) -> None:
    """Interactive interview, then write forge.yml and generate."""
    manager = default_manager()
    try:
        result = run_new(
            out,
            manager,
            QuestionaryPrompter(),
            spec_out=spec_out,
            only=_split(only),
            force=force,
            dry_run=dry_run,
        )
    except ForgeError as exc:
        _fail(str(exc))
        return
    _echo_plan(manager, result)
    _echo_warnings(result)
    typer.echo(result.summary())


# ---------------------------------------------------------------------------
# generate
# ---------------------------------------------------------------------------


@app.command("generate")
def cmd_generate(
    spec: Optional[Path] = typer.Option(
        None, "--spec", "-s", help=f"Specification to replay (default: {SPEC_FILENAME})."
    ),
    out: Path = typer.Option(Path("."), "--out", "-o", help="Target directory."),
    only: Optional[str] = typer.Option(None, "--only", help="Restrict to the named domains."),
    ref: str = typer.Option(DEFAULT_REF, "--ref", help="Git reference of the template."),
    force: bool = typer.Option(False, "--force", help="Overwrite existing files."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Write nothing."),
) -> None:
    """Regenerate the domains from an existing specification."""
    manager = default_manager()
    try:
        spec_path = pipeline.find_spec_file(spec, out)
        data, model = pipeline.load_spec(spec_path, manager)
        result = pipeline.generate(
            data,
            model,
            manager,
            out,
            only=_split(only),
            ref=ref,
            force=force,
            dry_run=dry_run,
            spec_path=spec_path,
        )
    except ForgeError as exc:
        _fail(str(exc))
        return
    _echo_plan(manager, result)
    _echo_warnings(result)
    typer.echo(result.summary())


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


@app.command("validate")
def cmd_validate(
    spec: Optional[Path] = typer.Option(None, "--spec", "-s", help="Specification to read."),
    out: Path = typer.Option(Path("."), "--out", "-o", help="Directory of the generated project."),
    only: Optional[str] = typer.Option(None, "--only", help="Restrict to the named domains."),
    skip_missing: bool = typer.Option(
        False, "--skip-missing", help="Skip the checks whose tool is missing."
    ),
) -> None:
    """Run every domain's validators, then the cross-domain checks."""
    manager = default_manager()
    try:
        spec_path = pipeline.find_spec_file(spec, out)
        _, model = pipeline.load_spec(spec_path, manager)
        result = pipeline.validate(
            model, manager, out, only=_split(only), skip_missing=skip_missing
        )
    except ForgeError as exc:
        _fail(str(exc))
        return

    for report in result.reports:
        typer.echo(report.summary())
        for check in report.checks:
            typer.echo(f"  {check.line()}")
            if check.detail:
                # `detail` is already bounded by OUTPUT_LINES: re-truncating it
                # here would erase the very line that explains the failure.
                for line in check.detail.splitlines():
                    typer.echo(f"    {line}")
        if report.all_skipped:
            typer.echo(
                f"  WARNING: no check ran for {report.domain}; "
                "this domain is not valid, it has not been verified."
            )
    typer.echo(format_issues(result.issues))
    if not result.ok:
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# update / diff
# ---------------------------------------------------------------------------


@app.command("update")
def cmd_update(
    out: Path = typer.Option(Path("."), "--out", "-o", help="Directory of the generated project."),
    only: Optional[str] = typer.Option(None, "--only", help="Restrict to the named domains."),
    ref: str = typer.Option(DEFAULT_REF, "--ref", help="Git reference of the template."),
    conflict: str = typer.Option(
        "inline", "--conflict", help="copier conflict strategy: inline or rej."
    ),
) -> None:
    """Apply the template's evolutions to an already generated project."""
    manager = default_manager()
    try:
        updated = pipeline.update(
            manager, out, only=_split(only), ref=ref, conflict=conflict
        )
    except ForgeError as exc:
        _fail(str(exc))
        return
    typer.echo(f"domains updated: {', '.join(updated) or 'none'}")
    if updated:
        # The moment the user is told their files moved is the only moment the
        # changelog is worth reading, so the pointer is printed here rather than
        # written into the generated project: a line in the generated README
        # would be authored once, then owned by the user and re-merged by every
        # later update, which is a permanent conflict site for a link that never
        # changes. Nothing is printed when no domain moved.
        typer.echo(f"what moved, and what it asks of you: {CHANGELOG_URL}")


@app.command("diff")
def cmd_diff(
    spec: Optional[Path] = typer.Option(None, "--spec", "-s", help="Specification to read."),
    out: Path = typer.Option(Path("."), "--out", "-o", help="Directory of the generated project."),
    only: Optional[str] = typer.Option(None, "--only", help="Restrict to the named domains."),
    ref: str = typer.Option(DEFAULT_REF, "--ref", help="Git reference of the template."),
) -> None:
    """Summarise the difference between the target and a fresh render (never the full diff)."""
    manager = default_manager()
    try:
        spec_path = pipeline.find_spec_file(spec, out)
        data, model = pipeline.load_spec(spec_path, manager)
        diffs = pipeline.diff(
            data, model, manager, out, only=_split(only), ref=ref, spec_path=spec_path
        )
    except ForgeError as exc:
        _fail(str(exc))
        return
    for entry in diffs:
        typer.echo(entry.summary())
        for name in entry.added:
            typer.echo(f"  + {name}")
        for name in entry.removed:
            typer.echo(f"  - {name}")
        for name, lines in entry.modified:
            typer.echo(f"  ~ {name} ({lines} line(s))")


# ---------------------------------------------------------------------------
# plugins / catalog
# ---------------------------------------------------------------------------


@app.command("plugins")
def cmd_plugins(
    spec: Optional[Path] = typer.Option(
        None, "--spec", "-s", help="Specification used to query the validators."
    ),
    out: Path = typer.Option(Path("."), "--out", "-o", help="Directory of the project."),
) -> None:
    """List the registered domains and the state of their external tools."""
    manager = default_manager()
    domains = manager.domains()
    if not domains:
        typer.echo("no registered domain")
        return

    # A plugin builds its commands from the specification (one per environment,
    # for instance). Without it the state of the tools is unavailable: forge says
    # so, instead of swallowing the error and letting the user believe the plugin
    # declares no validator.
    model = None
    try:
        model = pipeline.load_spec(pipeline.find_spec_file(spec, out), manager)[1]
    except ForgeError:
        model = None

    requested = set(model.domain_names()) if model is not None else set()
    if model is not None:
        typer.echo(
            f"specification read: {len(requested)} domain(s) requested out of "
            f"{len(domains)} available.\n"
        )

    for info in domains:
        if model is None:
            state = ""
        elif info.name in requested:
            state = "  [requested by the specification]"
        else:
            state = "  [not requested — add a section to generate it]"
        typer.echo(f"{info.name} — {info.title}: {info.summary}{state}")
        typer.echo(f"  forge.yml section: {info.name}:    output: {info.outdir}/")
        hooks = manager.domain(info.name)
        try:
            commands = hooks.validators(model, out / info.outdir)
        except (AttributeError, TypeError):
            typer.echo(
                "  tool state unavailable without a specification "
                "(run the command inside a generated project, or pass --spec)"
            )
            continue
        seen: set[str] = set()
        for command in commands:
            if command.tool in seen:
                continue
            seen.add(command.tool)
            typer.echo(f"  {probe(command.tool, command.requires_linux).describe()}")


@app.command("catalog")
def cmd_catalog(
    domain: str = typer.Argument(..., help="Domain whose catalogue is consulted."),
    entry: Optional[str] = typer.Argument(None, help="Specific entry to detail."),
) -> None:
    """Print the catalogue provided by a plugin (roles, components...)."""
    manager = default_manager()
    try:
        entries = manager.domain(domain).catalog()
    except ForgeError as exc:
        _fail(str(exc))
        return
    if not entries:
        typer.echo(f"domain {domain} publishes no catalogue")
        return
    if entry is None:
        for item in entries:
            typer.echo(f"{item.name} — {item.summary}")
        return
    for item in entries:
        if item.name == entry:
            typer.echo(f"{item.name} — {item.summary}")
            if item.details:
                typer.echo(item.details)
            for option, description in sorted(item.options.items()):
                typer.echo(f"  {option}: {description}")
            return
    _fail(f"unknown entry in the {domain} catalogue: {entry}")


if __name__ == "__main__":  # pragma: no cover
    app()
