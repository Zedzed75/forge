"""Proof that `FORGE_REQUIRE_TOOLS` really closes the door.

Comments in this module are in English: new test infrastructure, no French
precedent, and no effect on generated output.

An untested fail-closed switch is worth nothing -- worse than nothing, because
it reads like a guarantee. The whole value of the flag is what happens on the
day an install step in `.github/workflows/ci.yml` silently degrades, and that
day must not be the first time the code path runs. So the two branches are
asserted directly, on a deliberately absent tool, plus the anti-drift guard that
matters most: that all seven integration tests really do go through the one
shared helper.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.validate import tools
from tests.conftest import (
    REPO_ROOT,
    REQUIRE_TOOLS_ENV,
    require_tools,
    tools_are_required,
)

#: A binary name no machine can have, used to exercise the real probe.
NEVER_INSTALLED = "forge-validator-that-cannot-exist"

#: The seven skip sites the flag governs, and the module each lives in.
EXPECTED_CALL_SITES = {
    "test_inter_domaines.py": 1,
    "test_plugin_ansible.py": 1,
    "test_plugin_helm.py": 1,
    "test_plugin_monitoring.py": 1,
    "test_plugin_pipeline.py": 1,
    "test_plugin_terraform.py": 1,
}


@pytest.fixture
def absent(monkeypatch: pytest.MonkeyPatch):
    """Report every tool as absent, whatever this machine actually has."""
    monkeypatch.setattr(
        tools,
        "probe",
        lambda name, *args, **kwargs: tools.ToolStatus(name=name, location=None),
    )


@pytest.fixture
def present(monkeypatch: pytest.MonkeyPatch):
    """Report every tool as available."""
    monkeypatch.setattr(
        tools,
        "probe",
        lambda name, *args, **kwargs: tools.ToolStatus(
            name=name, location=tools.NATIVE, version="1.0"
        ),
    )


def test_a_missing_tool_skips_when_the_flag_is_unset(absent, monkeypatch):
    """The development loop is untouched: a Windows workstation still skips."""
    monkeypatch.delenv(REQUIRE_TOOLS_ENV, raising=False)
    with pytest.raises(pytest.skip.Exception) as skipped:
        require_tools("helm", "kubeconform")
    assert "kubeconform" in str(skipped.value)
    assert "helm" in str(skipped.value)


def test_a_missing_tool_fails_when_the_flag_is_set(absent, monkeypatch):
    """The point of the whole exercise: in CI the same situation is a red build."""
    monkeypatch.setenv(REQUIRE_TOOLS_ENV, "1")
    with pytest.raises(pytest.fail.Exception) as failed:
        require_tools("monitoring", "promtool")
    message = str(failed.value)
    assert "promtool" in message, message
    assert "monitoring" in message, message
    assert REQUIRE_TOOLS_ENV in message, message


def test_the_failure_names_every_missing_tool(absent, monkeypatch):
    """Naming one of four missing tools would send the reader on three round trips."""
    monkeypatch.setenv(REQUIRE_TOOLS_ENV, "1")
    with pytest.raises(pytest.fail.Exception) as failed:
        require_tools("ansible+helm", "ansible-playbook", "ansible-lint", "helm", "kubeconform")
    message = str(failed.value)
    for name in ("ansible-playbook", "ansible-lint", "helm", "kubeconform"):
        assert name in message, message


def test_a_partially_missing_set_reports_only_what_is_missing(monkeypatch):
    monkeypatch.setenv(REQUIRE_TOOLS_ENV, "1")
    monkeypatch.setattr(
        tools,
        "probe",
        lambda name, *args, **kwargs: tools.ToolStatus(
            name=name, location=None if name == "tflint" else tools.NATIVE
        ),
    )
    with pytest.raises(pytest.fail.Exception) as failed:
        require_tools("terraform", "terraform", "tflint")
    message = str(failed.value)
    assert "tflint" in message
    assert "terraform, tflint" not in message


def test_an_available_tool_lets_the_test_run(present, monkeypatch):
    """Both flag states: the helper must never get in the way when tools exist."""
    monkeypatch.setenv(REQUIRE_TOOLS_ENV, "1")
    require_tools("helm", "helm", "kubeconform")
    monkeypatch.delenv(REQUIRE_TOOLS_ENV, raising=False)
    require_tools("helm", "helm", "kubeconform")


def test_a_tool_that_really_is_absent_fails_without_any_stubbing(monkeypatch):
    """The real probe, the real filesystem, the real failure.

    The tests above stub `probe`, which proves the branch and not the wiring.
    This one asks for a binary that cannot exist and goes through
    `shutil.which` for real. `requires_linux=False` keeps it off the WSL bridge,
    which would cost a subprocess for a foregone conclusion.
    """
    monkeypatch.setenv(REQUIRE_TOOLS_ENV, "1")
    with pytest.raises(pytest.fail.Exception) as failed:
        require_tools("scratch", NEVER_INSTALLED, requires_linux=False)
    assert NEVER_INSTALLED in str(failed.value)

    monkeypatch.delenv(REQUIRE_TOOLS_ENV, raising=False)
    with pytest.raises(pytest.skip.Exception):
        require_tools("scratch", NEVER_INSTALLED, requires_linux=False)


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "On", " 1 "])
def test_the_flag_is_read_as_set(value, monkeypatch):
    monkeypatch.setenv(REQUIRE_TOOLS_ENV, value)
    assert tools_are_required()


@pytest.mark.parametrize("value", ["", "0", "false", "no", "off", "maybe"])
def test_the_flag_is_read_as_unset(value, monkeypatch):
    """`FORGE_REQUIRE_TOOLS=0` must disable the flag, not enable it by presence."""
    monkeypatch.setenv(REQUIRE_TOOLS_ENV, value)
    assert not tools_are_required()


def test_the_flag_is_unset_by_default(monkeypatch):
    monkeypatch.delenv(REQUIRE_TOOLS_ENV, raising=False)
    assert not tools_are_required()


# ---------------------------------------------------------------------------
# Anti-drift
# ---------------------------------------------------------------------------


def _test_modules() -> list[Path]:
    """Every test module except this one and the helper's own home."""
    return [
        path
        for path in sorted((REPO_ROOT / "tests").glob("test_*.py"))
        if path.name != Path(__file__).name
    ]


def test_every_integration_test_goes_through_the_shared_helper():
    """A site left behind would keep skipping, and the build would stay green.

    This is the failure mode the helper exists to prevent, so it is asserted on
    the source itself rather than trusted. Adding a sixth domain means adding a
    line here -- deliberately: a new domain whose validators can quietly fail to
    run is the exact regression this pull request closes.
    """
    counted = {}
    for path in _test_modules():
        calls = sum(
            1
            for line in path.read_text(encoding="utf-8").splitlines()
            if "require_tools(" in line and not line.lstrip().startswith(("from ", "import "))
        )
        if calls:
            counted[path.name] = calls
    assert counted == EXPECTED_CALL_SITES
    # Six calls for seven historical skip sites: `test_plugin_ansible.py` had two
    # consecutive `pytest.skip` calls, one per tool, now a single call naming both.
    assert sum(counted.values()) == 6


def test_no_test_module_probes_a_validator_behind_the_helper():
    """`tools.probe` outside the helper is how the fail-closed switch would rot."""
    offenders = []
    for path in _test_modules():
        # test_validate.py tests `probe` itself; that is its subject, not a
        # validator gate, and it never skips on the result.
        if path.name == "test_validate.py":
            continue
        if "probe(" in path.read_text(encoding="utf-8"):
            offenders.append(path.name)
    assert not offenders, offenders
