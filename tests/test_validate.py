"""Tests of the validation runner and of the cross-domain checks."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from forge.errors import ForgeError, PluginError
from forge.plugins_api.types import Command, Projection
from forge.validate import tools, wsl
from forge.validate.consistency import compare_projections, format_issues, has_errors
from forge.validate.runner import run_command, run_commands

#: Current interpreter: an external tool guaranteed present, with no network
#: dependency.
PYTHON = sys.executable

#: Binary deliberately impossible to find on every platform.
MISSING = "tool-that-does-not-exist"


def _python(label: str, code: str, **kwargs) -> Command:
    return Command(label=label, tool=PYTHON, argv=("-c", code), **kwargs)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def test_a_command_that_succeeds_is_marked_ok(tmp_path):
    check = run_command(_python("ok", "print('fine')"), tmp_path)
    assert check.status == "ok"
    assert check.returncode == 0
    assert "fine" in check.stdout


def test_a_failing_command_reports_its_output(tmp_path):
    check = run_command(
        _python("ko", "import sys; sys.stderr.write('broken'); sys.exit(3)"), tmp_path
    )
    assert check.status == "failed"
    assert check.returncode == 3
    assert "broken" in check.detail


def test_a_missing_tool_gives_an_installation_message(tmp_path):
    command = Command(
        label="missing",
        tool=MISSING,
        install_hint="install it from the internal repository",
    )
    check = run_command(command, tmp_path)
    assert check.status == "missing"
    assert "install it from the internal repository" in check.detail
    assert "Traceback" not in check.detail


def test_a_timeout_is_reported_without_a_traceback(tmp_path):
    check = run_command(_python("slow", "import time; time.sleep(5)", timeout=1), tmp_path)
    assert check.status == "timeout"
    assert "time limit" in check.detail


def test_skip_missing_turns_the_absence_into_a_skip(tmp_path):
    command = Command(label="missing", tool=MISSING)
    report = run_commands("demo", [command], tmp_path, skip_missing=True)
    assert report.checks[0].status == "skipped"
    assert report.ok


def test_without_skip_missing_the_absence_fails(tmp_path):
    command = Command(label="missing", tool=MISSING)
    report = run_commands("demo", [command], tmp_path)
    assert not report.ok
    assert [check.label for check in report.failures()] == ["missing"]


def test_stdin_is_chained_from_the_source_command(tmp_path):
    commands = [
        _python("produces", "print('payload')"),
        _python(
            "consumes",
            "import sys; data = sys.stdin.read(); sys.exit(0 if 'payload' in data else 1)",
            stdin_from="produces",
        ),
    ]
    report = run_commands("demo", commands, tmp_path)
    assert [check.status for check in report.checks] == ["ok", "ok"]


def test_chaining_onto_a_label_that_does_not_exist_is_a_plugin_error(tmp_path):
    """Contract breach on the plugin side: reporting it as a skip would make
    `forge validate` go green without having run the command."""
    commands = [_python("consumes", "pass", stdin_from="never declared")]
    with pytest.raises(PluginError, match="declared nowhere"):
        run_commands("demo", commands, tmp_path)


def test_a_chain_whose_source_failed_is_skipped_cleanly(tmp_path):
    commands = [
        _python("produces", "import sys; sys.exit(1)"),
        _python("consumes", "pass", stdin_from="produces"),
    ]
    report = run_commands("demo", commands, tmp_path)
    assert [check.status for check in report.checks] == ["failed", "skipped"]
    assert "produces" in report.checks[1].detail


def test_the_output_excerpt_keeps_the_head_where_the_error_is_announced(tmp_path):
    """Infrastructure tools announce the cause on the first line, not the last."""
    code = (
        "import sys\n"
        "sys.stderr.write('Error: values.yaml:3 unknown key\\n')\n"
        "sys.stderr.write(''.join(f'context {i}\\n' for i in range(200)))\n"
        "sys.exit(1)\n"
    )
    check = run_command(_python("verbose", code), tmp_path)
    assert check.status == "failed"
    assert "Error: values.yaml:3 unknown key" in check.detail
    assert "line(s) omitted" in check.detail
    assert not check.detail.splitlines()[0].startswith("  [...")


def test_an_entirely_skipped_report_is_reported(tmp_path):
    """A green report where nothing ran is a trap: it has to be visible."""
    commands = [Command(label="missing", tool=MISSING)]
    report = run_commands("demo", commands, tmp_path, skip_missing=True)
    assert report.all_skipped
    assert [check.label for check in report.skipped()] == ["missing"]


def test_a_partially_executed_report_is_not_reported(tmp_path):
    commands = [
        _python("ok", "pass"),
        Command(label="missing", tool=MISSING),
    ]
    report = run_commands("demo", commands, tmp_path, skip_missing=True)
    assert not report.all_skipped


def test_the_report_summarises_the_states(tmp_path):
    report = run_commands(
        "demo",
        [_python("ok", "pass"), Command(label="missing", tool=MISSING)],
        tmp_path,
    )
    assert report.summary().startswith("demo:")
    assert "1 ok" in report.summary()
    assert "1 missing" in report.summary()


def test_the_command_runs_in_the_domain_directory(tmp_path):
    target = tmp_path / "demo"
    target.mkdir()
    (target / "marker.txt").write_text("x", encoding="utf-8")
    check = run_command(
        _python("cwd", "import pathlib, sys; sys.exit(0 if pathlib.Path('marker.txt').exists() else 1)"),
        target,
    )
    assert check.status == "ok"


def test_probe_finds_a_tool_from_the_path():
    status = tools.probe(PYTHON)
    assert status.available
    assert "available" in status.describe()


def test_probe_reports_a_missing_tool():
    status = tools.probe(MISSING)
    assert not status.available
    assert status.describe().endswith("missing")


# ---------------------------------------------------------------------------
# Cross-domain consistency
# ---------------------------------------------------------------------------


def _projection(**kwargs) -> Projection:
    base = {
        "service_name": "storefront",
        "environments": ("dev", "prod"),
        "labels": {"tier": "frontend"},
        "facets": {},
    }
    base.update(kwargs)
    return Projection(**base)


def test_a_single_domain_triggers_no_check():
    assert compare_projections({"demo": _projection()}) == []


def test_two_aligned_domains_produce_no_finding():
    issues = compare_projections({"a": _projection(), "b": _projection()})
    assert issues == []
    assert "no difference" in format_issues(issues)


def test_a_divergent_service_name_is_an_error():
    issues = compare_projections(
        {"a": _projection(), "b": _projection(service_name="other")}
    )
    assert has_errors(issues)
    assert "service name" in issues[0].message


def test_an_environment_materialised_by_a_single_domain_is_reported():
    """This is the finding only comparing projections can produce.

    A warning, not an error: deploying to production with no configuration
    machine can be perfectly intentional (a purely containerised service). What
    must not happen is that nobody says so.
    """
    issues = compare_projections(
        {"a": _projection(), "b": _projection(environments=("dev",))}
    )
    assert not has_errors(issues)
    assert [issue.level for issue in issues] == ["warning"]
    assert "prod" in issues[0].message
    assert "materialised by a" in issues[0].message
    assert issues[0].hint


def test_a_different_environment_order_is_a_warning():
    issues = compare_projections(
        {"a": _projection(), "b": _projection(environments=("prod", "dev"))}
    )
    assert not has_errors(issues)
    assert issues[0].level == "warning"


def test_a_contradictory_label_is_an_error():
    issues = compare_projections(
        {"a": _projection(), "b": _projection(labels={"tier": "backend"})}
    )
    assert has_errors(issues)
    assert "tier" in issues[0].message


def test_a_facet_declared_by_a_single_domain_is_not_compared():
    issues = compare_projections(
        {"a": _projection(facets={"hosts": ("web-01",)}), "b": _projection()}
    )
    assert issues == []


def test_a_facet_of_the_shared_vocabulary_must_agree():
    issues = compare_projections(
        {
            "a": _projection(facets={"inventory_hosts": ("web-01", "web-02")}),
            "b": _projection(facets={"inventory_hosts": ("web-01",)}),
        }
    )
    assert has_errors(issues)
    assert "web-02" in issues[0].message


def test_a_facet_outside_the_vocabulary_is_not_compared():
    """A facet name is a namespace **shared** between domains.

    Two domains using the same name assert that they talk about the same thing.
    Without that rule the collision is silent: measured in phase 5, Ansible
    declared `hosts` for its machines and Helm for its Ingress hosts, and
    `forge validate` failed on a perfectly consistent specification.
    """
    issues = compare_projections(
        {
            "a": _projection(facets={"house": ("x",)}),
            "b": _projection(facets={"house": ("y",)}),
        }
    )
    assert issues == []


def test_the_vocabulary_tells_the_two_kinds_of_hosts_apart():
    """Inventory machines and Ingress hosts are not the same thing."""
    from forge.validate.consistency import FACET_VOCABULARY

    assert "inventory_hosts" in FACET_VOCABULARY
    assert "ingress_hosts" in FACET_VOCABULARY
    assert "hosts" not in FACET_VOCABULARY, (
        "a name that vague invites precisely the collision we have just fixed"
    )


def test_the_finding_format_puts_errors_before_warnings():
    issues = compare_projections(
        {
            "a": _projection(),
            "b": _projection(environments=("prod", "dev"), labels={"tier": "backend"}),
        }
    )
    rendered = format_issues(issues)
    assert rendered.index("ERROR") < rendered.index("WARNING")


def test_no_projection_produces_no_finding():
    assert compare_projections({}) == []


# ---------------------------------------------------------------------------
# WSL bridge — pure functions, checkable without an installed distribution
# ---------------------------------------------------------------------------


def test_quote_protects_an_apostrophe():
    #  it's said  ->  'it'\''s said'  (close, escaped quote, reopen)
    expected = "'it'" + chr(92) + "''s said'"
    assert wsl.quote("it's said") == expected


def test_to_wsl_path_translates_a_drive_letter():
    assert wsl.to_wsl_path(Path("C:/projects/demo")) == "/mnt/c/projects/demo"


@pytest.mark.parametrize(
    "path",
    ["//nas/share/project", Path("//nas/share/project"), r"\\nas\share\project"],
    ids=["string", "path-object", "windows-separators"],
)
def test_to_wsl_path_refuses_a_unc_path(path):
    """Fabricating a plausible but wrong path would make the copy fail further on.

    The three forms are exercised because the detection used to depend on the
    Python version: up to 3.11, building a `PureWindowsPath` from a `PosixPath`
    reuses the POSIX splitting and loses the UNC prefix. The detection is
    therefore made on the string, before pathlib.
    """
    with pytest.raises(ForgeError, match="UNC"):
        wsl.to_wsl_path(path)


def test_build_command_cleans_the_temporary_directory_with_a_trap():
    """Without the trap, a timeout leaves a copy of the project in /tmp."""
    command = wsl.build_command("helm", ("lint",), Path("C:/projects/demo"), None)
    assert "trap 'rm -rf \"$work\"' EXIT HUP INT TERM" in command
    assert command.count("mktemp") == 1


def test_build_command_protects_the_arguments():
    command = wsl.build_command("helm", ("template", "a b"), Path("C:/p"), None)
    assert "'a b'" in command


def test_build_command_passes_the_environment_variables():
    command = wsl.build_command("ansible-lint", (), Path("C:/p"), {"ANSIBLE_FORCE_COLOR": "0"})
    assert "ANSIBLE_FORCE_COLOR='0'" in command


def test_install_hint_mentions_the_distribution_under_windows(monkeypatch):
    monkeypatch.setattr(wsl, "is_windows", lambda: True)
    assert wsl.WSL_DISTRO in wsl.install_hint("helm")
