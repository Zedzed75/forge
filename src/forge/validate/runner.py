"""Execution of the validation commands declared by the plugins.

The plugin declares *what* to run (`forge_validators` -> `list[Command]`); the
core decides *how*: subprocess or WSL fallback, timeout, capture, stdin
chaining, and report. The report model comes from helm-forge, which was more
complete than its ansible-forge counterpart (MIGRATION.md §5.4).

A missing tool produces an installation message, never a Python traceback.
"""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from forge.errors import PluginError
from forge.plugins_api.types import Command
from forge.validate import tools, wsl

#: Possible states of a check.
Status = Literal["ok", "failed", "missing", "skipped", "timeout"]

#: Number of output lines kept per failing command.
OUTPUT_LINES = 40


@dataclass
class Check:
    """Result of one validation command."""

    #: Label declared by the plugin.
    label: str

    #: Binary invoked.
    tool: str

    #: Final state.
    status: Status

    #: Return code of the process, or None if nothing was run.
    returncode: int | None = None

    #: Execution time, in seconds.
    duration: float = 0.0

    #: Complete standard output (may feed another command's stdin).
    stdout: str = ""

    #: Error output, truncated for display.
    stderr: str = ""

    #: Readable explanation in case of failure or missing tool.
    detail: str = ""

    @property
    def ok(self) -> bool:
        """True if the command is not a failure (success or accepted skip)."""
        return self.status in ("ok", "skipped")

    def line(self) -> str:
        """Report line, without the tool output."""
        marks = {
            "ok": "OK  ",
            "failed": "FAILED",
            "missing": "MISSING",
            "skipped": "SKIPPED",
            "timeout": "TIMEOUT",
        }
        return f"[{marks[self.status]}] {self.label} ({self.duration:.1f}s)"


@dataclass
class Report:
    """The whole set of checks of one domain."""

    domain: str
    checks: list[Check] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True if no check failed."""
        return all(check.ok for check in self.checks)

    def failures(self) -> list[Check]:
        """Failing checks, in execution order."""
        return [check for check in self.checks if not check.ok]

    def skipped(self) -> list[Check]:
        """Skipped checks: they proved nothing."""
        return [check for check in self.checks if check.status == "skipped"]

    @property
    def all_skipped(self) -> bool:
        """True if the domain declared checks and none of them ran.

        A "green" report where nothing executed is a trap: the CI must see it,
        otherwise `--skip-missing` turns a missing tool into a success.
        """
        return bool(self.checks) and all(
            check.status == "skipped" for check in self.checks
        )

    def summary(self) -> str:
        """Compact summary: one count per state."""
        counts: dict[str, int] = {}
        for check in self.checks:
            counts[check.status] = counts.get(check.status, 0) + 1
        detail = ", ".join(f"{count} {status}" for status, count in sorted(counts.items()))
        return f"{self.domain}: {detail or 'no check'}"


def _excerpt(text: str, lines: int = OUTPUT_LINES) -> str:
    """Readable excerpt of a tool output: head AND tail, never the tail alone.

    Infrastructure tools announce the cause at the **top** of their output
    (`Error: values.yaml:3 unknown key`) then unroll context. Keeping only the
    tail, as the first version did, amounted to erasing the useful information
    and printing nothing but a truncation marker.
    """
    stripped = text.strip()
    if not stripped:
        return ""
    parts = stripped.splitlines()
    if len(parts) <= lines:
        return "\n".join(parts)
    head = max(lines // 2, 1)
    tail = max(lines - head, 1)
    omitted = len(parts) - head - tail
    return "\n".join(
        [*parts[:head], f"  [... {omitted} line(s) omitted ...]", *parts[-tail:]]
    )


def run_command(
    command: Command, default_cwd: Path, stdin: str | None = None
) -> Check:
    """Run a command, natively or through WSL, and return its result."""
    cwd = Path(command.cwd or default_cwd)
    status = tools.probe(command.tool, command.requires_linux)
    if not status.available:
        return Check(
            label=command.label,
            tool=command.tool,
            status="missing",
            detail=tools.missing_message(
                command.tool, command.install_hint, command.requires_linux
            ),
        )

    started = time.monotonic()
    supplement = dict(command.env)
    try:
        if status.location == tools.WSL:
            completed = wsl.run_in_wsl(
                command.tool,
                command.argv,
                cwd,
                timeout=command.timeout,
                env=supplement,
                stdin=stdin,
            )
        else:
            completed = subprocess.run(
                [command.tool, *command.argv],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=command.timeout,
                env={**os.environ, **supplement} if supplement else None,
                input=stdin,
                errors="replace",
            )
    except subprocess.TimeoutExpired:
        return Check(
            label=command.label,
            tool=command.tool,
            status="timeout",
            duration=time.monotonic() - started,
            detail=f"the {command.timeout}s time limit was exceeded",
        )
    except OSError as exc:
        return Check(
            label=command.label,
            tool=command.tool,
            status="failed",
            duration=time.monotonic() - started,
            detail=str(exc),
        )

    duration = time.monotonic() - started
    return Check(
        label=command.label,
        tool=command.tool,
        status="ok" if completed.returncode == 0 else "failed",
        returncode=completed.returncode,
        duration=duration,
        stdout=completed.stdout or "",
        stderr=_excerpt(completed.stderr or ""),
        detail="" if completed.returncode == 0 else _excerpt(
            completed.stderr or completed.stdout or ""
        ),
    )


def run_commands(
    domain: str,
    commands: list[Command],
    default_cwd: Path,
    *,
    skip_missing: bool = False,
) -> Report:
    """Run the commands in order, chaining the requested stdin.

    `skip_missing` turns a missing tool into an accepted skip rather than a
    failure: useful in development, never in CI.
    """
    report = Report(domain=domain)
    outputs: dict[str, str] = {}
    declared = {command.label for command in commands}
    for command in commands:
        stdin = None
        if command.stdin_from is not None:
            if command.stdin_from not in declared:
                # A source label that does not exist is a fault in the plugin,
                # not an execution hazard. Reporting it as a plain skip would
                # make `forge validate` go green without having run the command.
                known = ", ".join(sorted(declared)) or "none"
                raise PluginError(
                    f"domain '{domain}' chains command \"{command.label}\" onto "
                    f"\"{command.stdin_from}\", which is declared nowhere "
                    f"(known labels: {known})"
                )
            if command.stdin_from not in outputs:
                report.checks.append(
                    Check(
                        label=command.label,
                        tool=command.tool,
                        status="skipped",
                        detail=(
                            f"source command \"{command.stdin_from}\" produced no "
                            "usable output"
                        ),
                    )
                )
                continue
            stdin = outputs[command.stdin_from]
        check = run_command(command, default_cwd, stdin=stdin)
        if check.status == "missing" and skip_missing:
            check.status = "skipped"
        if check.status == "ok":
            outputs[command.label] = check.stdout
        report.checks.append(check)
    return report
