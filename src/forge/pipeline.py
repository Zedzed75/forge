"""Sequencing of forge's operations, independently of the CLI.

The CLI does nothing but read arguments and print results; everything that
follows is callable from the tests without a terminal. Every operation starts
from an already loaded `forge.yml` and a plugin manager, never from global state.
"""

from __future__ import annotations

import importlib.util
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from forge.errors import SpecFileError, SpecValidationError
from forge.plugins_api.manager import DomainHooks, ForgeManager
from forge.plugins_api.types import DomainInfo, Issue, Projection
from forge.render import copier_runner, scaffold
from forge.render.diff import DomainDiff, count_changed_lines, diff_trees
from forge.spec.assembly import ForgeSpecBase, resolve_domains, validate_spec
from forge.spec.io import SPEC_FILENAME, load_spec_data
from forge.validate.consistency import compare_projections
from forge.validate.runner import Report, run_commands


@dataclass
class GenerationResult:
    """What a generation produced."""

    target: Path
    domains: list[str] = field(default_factory=list)
    repo_files: list[Path] = field(default_factory=list)
    dry_run: bool = False

    #: `warning`-level findings reported by the plugins before rendering.
    #: Errors, for their part, have already stopped the generation.
    warnings: list[Issue] = field(default_factory=list)

    def summary(self) -> str:
        """One-line summary — never the full tree."""
        prefix = "dry run: " if self.dry_run else ""
        listed = ", ".join(self.domains) or "none"
        return f"{prefix}{self.target} — domains: {listed}"


@dataclass
class ValidationResult:
    """Per-domain reports and cross-domain findings."""

    reports: list[Report] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True if no report fails and no finding is an error."""
        return all(report.ok for report in self.reports) and not any(
            issue.level == "error" for issue in self.issues
        )


def load_spec(spec_path: Path, manager: ForgeManager) -> tuple[dict[str, Any], ForgeSpecBase]:
    """Load `forge.yml` and return (raw dict, validated instance)."""
    data = load_spec_data(spec_path)
    return data, validate_spec(data, manager)


def find_spec_file(spec_path: Path | None, target: Path) -> Path:
    """Resolve the path of the `forge.yml`: the one asked for, else the target's."""
    if spec_path is not None:
        return Path(spec_path)
    candidate = Path(target) / SPEC_FILENAME
    if candidate.is_file():
        return candidate
    local = Path(SPEC_FILENAME)
    if local.is_file():
        return local
    raise SpecFileError(
        f"no specification found: neither {candidate}, nor ./{SPEC_FILENAME}. "
        "Pass --spec."
    )


def plugin_jinja_module(hooks: DomainHooks) -> str:
    """The plugin's filter module, if it provides one (`jinja_ext` convention).

    That is how a plugin enriches the Jinja environment without touching the root
    copier.yml or the core.
    """
    module_name = getattr(hooks.plugin, "__name__", "")
    if not module_name:
        return ""
    package = module_name.rsplit(".", 1)[0]
    candidate = f"{package}.jinja_ext"
    try:
        if importlib.util.find_spec(candidate) is not None:
            return candidate
    except (ImportError, ValueError):  # pragma: no cover - depends on the install
        return ""
    return ""


def domain_data(spec: ForgeSpecBase, hooks: DomainHooks) -> dict[str, Any]:
    """Assemble the copier answers of one domain."""
    return copier_runner.build_data(
        plugin=hooks.name,
        template_subdir=hooks.template_subdir(),
        forge_version=spec.forge_version,
        service=spec.service.model_dump(mode="json"),
        domain=hooks.answers(spec),
    )


def indexed_domains(spec: ForgeSpecBase, manager: ForgeManager) -> list[DomainInfo]:
    """Domains the specification asks for, whatever the `--only` filter.

    It is this list — and not the list of domains actually rendered — that feeds
    the repository-level index: an `--only ansible` must not make `helm/` vanish
    from the README of a project whose `helm:` section exists.
    """
    return [manager.domain(name).info for name in spec.domain_names()]


def check_spec(spec: ForgeSpecBase, manager: ForgeManager, names: list[str]) -> list[Issue]:
    """Ask every domain about the consistency of the specification.

    Called **before any rendering**: a plugin sub-model only sees its own
    section, so it cannot check on its own anything touching the shared
    `service:` block. Without this check an inconsistent specification would be
    generated without a murmur and the error would only surface at the next
    `forge validate` (arbitration R2 of the interface review).
    """
    issues: list[Issue] = []
    for name in names:
        issues.extend(manager.domain(name).check_spec(spec))
    return issues


def raise_on_errors(issues: list[Issue]) -> list[Issue]:
    """Stop on errors, return the warnings to display."""
    errors = [issue for issue in issues if issue.level == "error"]
    if errors:
        detail = "\n".join(
            f"  - {issue.message}" + (f"\n    -> {issue.hint}" if issue.hint else "")
            for issue in errors
        )
        raise SpecValidationError(
            f"inconsistent specification ({len(errors)} error(s)):\n{detail}"
        )
    return [issue for issue in issues if issue.level == "warning"]


def generate(
    spec_data: dict[str, Any],
    spec: ForgeSpecBase,
    manager: ForgeManager,
    target: Path,
    *,
    only: list[str] | None = None,
    ref: str = copier_runner.DEFAULT_REF,
    force: bool = False,
    dry_run: bool = False,
    spec_path: Path | None = None,
) -> GenerationResult:
    """Render every requested domain under `target/<outdir>`."""
    target = Path(target)
    names = resolve_domains(spec, manager, only)
    result = GenerationResult(target=target, domains=names, dry_run=dry_run)
    # The cross-checks run BEFORE rendering: better to write nothing at all than
    # to write a project we know to be inconsistent.
    result.warnings = raise_on_errors(check_spec(spec, manager, names))
    if dry_run:
        return result

    copier_runner.ensure_directory(target, "target directory")
    src = copier_runner.template_root()
    for name in names:
        hooks = manager.domain(name)
        copier_runner.run_copy(
            dst=target / hooks.info.outdir,
            data=domain_data(spec, hooks),
            src=src,
            ref=ref,
            force=force,
            plugin_jinja=plugin_jinja_module(hooks),
        )
    # The repository-level files are written last: a rendering failure must not
    # leave behind the index of a project that does not exist.
    result.repo_files = scaffold.write_repo_files(
        target,
        spec_data,
        indexed_domains(spec, manager),
        force=force,
        spec_path=spec_path,
    )
    return result


def update(
    manager: ForgeManager,
    target: Path,
    *,
    only: list[str] | None = None,
    ref: str = copier_runner.DEFAULT_REF,
    conflict: str = "inline",
) -> list[str]:
    """Replay `copier update` on every domain already generated under `target`.

    `update` does not read a `forge.yml`: the `--only` filter is therefore
    validated against the **registered** domains, not against a specification. An
    unknown name must fail here, otherwise a typo in a CI script would produce
    "no domain updated" and a return code of 0.
    """
    target = Path(target)
    updated: list[str] = []
    if only is not None:
        unknown = [name for name in only if name not in manager.domain_names()]
        if unknown:
            known = ", ".join(manager.domain_names()) or "none"
            raise SpecValidationError(
                f"unknown domain(s): {', '.join(unknown)} (registered: {known})"
            )
    src = copier_runner.template_root()
    for info in manager.domains():
        if only is not None and info.name not in only:
            continue
        outdir = target / info.outdir
        if not (outdir / copier_runner.ANSWERS_FILENAME).is_file():
            if only is not None:
                # Domain named explicitly but never generated: silence would let
                # a CI go green without updating anything. The message is the one
                # `run_update` already words.
                copier_runner.run_update(dst=outdir, src=src, ref=ref, conflict=conflict)
            continue
        copier_runner.run_update(
            dst=outdir,
            src=src,
            ref=ref,
            conflict=conflict,
            plugin_jinja=plugin_jinja_module(manager.domain(info.name)),
        )
        updated.append(info.name)
    return updated


#: Name given, in a comparison report, to the repository-level files.
ROOT_LABEL = "(root)"


def foreign_paths(
    spec_data: dict[str, Any],
    spec: ForgeSpecBase,
    manager: ForgeManager,
    name: str,
) -> frozenset[str]:
    """What a domain writing at the repository root must not compare.

    A domain whose `DomainInfo.outdir` is `.` — the `pipeline` domain, whose
    files only make sense where the CI tool reads them — shares its root with the
    other domains and with the repository-level files. Comparing its target
    against a fresh render without setting those aside would declare them all
    removed.

    Returns an empty set for any domain writing into its own subdirectory: the
    normal case pays nothing.
    """
    info = manager.domain(name).info
    if info.outdir not in (".", ""):
        return frozenset()
    others = {
        other.outdir
        for other in indexed_domains(spec, manager)
        if other.name != name and other.outdir not in (".", "")
    }
    return frozenset(others | set(scaffold.repo_files_content(spec_data, [])))


def diff_repo_files(
    spec_data: dict[str, Any],
    spec: ForgeSpecBase,
    manager: ForgeManager,
    target: Path,
    *,
    spec_path: Path | None = None,
) -> DomainDiff:
    """Compare the repository-level files against what forge would produce.

    They do not go through copier (cf. `render/scaffold`): without this
    comparison, `forge diff` would report "up to date" about files it never
    looked at.
    """
    wanted = scaffold.repo_files_content(spec_data, indexed_domains(spec, manager))
    if spec_path is not None:
        try:
            if Path(spec_path).resolve() == (target / SPEC_FILENAME).resolve():
                # Source of truth, hand-edited: its formatting does not have to
                # match a re-serialisation.
                wanted.pop(SPEC_FILENAME, None)
        except OSError:  # pragma: no cover - invalid path on this machine
            pass

    result = DomainDiff(domain=ROOT_LABEL)
    for name in sorted(wanted):
        path = target / name
        if not path.is_file():
            result.added.append(name)
            continue
        try:
            current = path.read_bytes().decode("utf-8")
        except (UnicodeDecodeError, OSError):
            result.modified.append((name, -1))
            continue
        if current != wanted[name]:
            result.modified.append(
                (name, count_changed_lines(current, wanted[name]))
            )
    return result


def diff(
    spec_data: dict[str, Any],
    spec: ForgeSpecBase,
    manager: ForgeManager,
    target: Path,
    *,
    only: list[str] | None = None,
    ref: str = copier_runner.DEFAULT_REF,
    spec_path: Path | None = None,
) -> list[DomainDiff]:
    """Compare the target against a fresh render, domain by domain (summary only)."""
    target = Path(target)
    names = resolve_domains(spec, manager, only)
    src = copier_runner.template_root()
    diffs: list[DomainDiff] = []
    if only is None:
        diffs.append(
            diff_repo_files(spec_data, spec, manager, target, spec_path=spec_path)
        )
    for name in names:
        hooks = manager.domain(name)
        with tempfile.TemporaryDirectory(prefix="forge-diff-") as tmp:
            fresh = Path(tmp) / hooks.info.outdir
            copier_runner.run_copy(
                dst=fresh,
                data=domain_data(spec, hooks),
                src=src,
                ref=ref,
                force=True,
                plugin_jinja=plugin_jinja_module(hooks),
            )
            diffs.append(
                diff_trees(
                    name,
                    target / hooks.info.outdir,
                    fresh,
                    ignore=foreign_paths(spec_data, spec, manager, name),
                )
            )
    return diffs


def validate(
    spec: ForgeSpecBase,
    manager: ForgeManager,
    target: Path,
    *,
    only: list[str] | None = None,
    skip_missing: bool = False,
) -> ValidationResult:
    """Run every domain's validators, then the cross-domain checks."""
    target = Path(target)
    names = resolve_domains(spec, manager, only)
    result = ValidationResult()
    projections: dict[str, Projection] = {}
    outdirs: dict[str, Path] = {}

    for name in names:
        hooks = manager.domain(name)
        outdir = target / hooks.info.outdir
        outdirs[name] = outdir
        commands = hooks.validators(spec, outdir)
        result.reports.append(
            run_commands(name, commands, outdir, skip_missing=skip_missing)
        )
        projection = hooks.projection(spec)
        if projection is not None:
            projections[name] = projection

    result.issues.extend(check_spec(spec, manager, names))
    result.issues.extend(compare_projections(projections))
    result.issues.extend(manager.consistency(spec, outdirs))
    return result
