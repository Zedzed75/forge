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

The flag governs a second rule, added after the hole was found still open next
to it: under `FORGE_REQUIRE_TOOLS`, an `integration` test that skips for *any*
reason fails the run. `require_tools` could not have caught the case that
motivated it -- `forge update` skipping on a dirty checkout, silently, in every
CI run -- because no tool was missing. That rule lives in
`tests/conftest.py::pytest_runtest_makereport` and is asserted here too.
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
    "test_cross_domain.py": 1,
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
# A skipped integration test is a failure, whatever the reason
# ---------------------------------------------------------------------------
# `require_tools` only governs the skips it owns. These exercise the hook that
# governs every other one, on a throwaway test file run by a real pytest: the
# reason a skip appears is irrelevant, only that it appeared under the flag.
# ---------------------------------------------------------------------------

#: A throwaway suite with one skipping integration test and one skipping plain
#: test. The plain one is the control: the hook must not touch it, because the
#: real suite has a legitimate unmarked skip (`test_plugins.py`) that must
#: survive the flag.
_SKIPPING_SUITE = """
    import pytest

    @pytest.mark.integration
    def test_marked():
        pytest.skip("the dirt the hook is supposed to catch")

    def test_unmarked():
        pytest.skip("structural, and none of the hook's business")
"""


@pytest.fixture
def skipping_suite(pytester: pytest.Pytester, monkeypatch):
    """Lay out the throwaway suite plus the hook under test, and nothing else."""
    pytester.makeconftest(
        "from tests.conftest import (  # noqa: F401\n"
        "    pytest_runtest_makereport,\n"
        "    pytest_terminal_summary,\n"
        ")\n"
    )
    pytester.makeini("[pytest]\nmarkers = integration: needs an external tool\n")
    pytester.makepyfile(test_skipping=_SKIPPING_SUITE)
    # The subprocess starts in the throwaway directory, where `tests` is not
    # importable: the repository root has to be handed over explicitly.
    monkeypatch.setenv("PYTHONPATH", str(REPO_ROOT))
    return pytester


def test_a_skipped_integration_test_fails_when_the_flag_is_set(skipping_suite, monkeypatch):
    """The regression this closes: the skip is now red instead of invisible."""
    monkeypatch.setenv(REQUIRE_TOOLS_ENV, "1")
    result = skipping_suite.runpytest_subprocess("-rs")
    result.assert_outcomes(failed=1, skipped=1)
    result.stdout.fnmatch_lines(["*the dirt the hook is supposed to catch*"])
    result.stdout.fnmatch_lines([f"*{REQUIRE_TOOLS_ENV} is set*"])


def test_an_unmarked_skip_survives_the_flag(skipping_suite, monkeypatch):
    """`test_plugins.py`'s structural skip is intended, and must stay a skip."""
    monkeypatch.setenv(REQUIRE_TOOLS_ENV, "1")
    result = skipping_suite.runpytest_subprocess("-rs")
    result.stdout.fnmatch_lines(["*none of the hook's business*"])
    result.assert_outcomes(skipped=1, failed=1)


def test_both_skips_stand_when_the_flag_is_unset(skipping_suite, monkeypatch):
    """A development machine keeps skipping what it cannot run."""
    monkeypatch.delenv(REQUIRE_TOOLS_ENV, raising=False)
    result = skipping_suite.runpytest_subprocess("-rs")
    result.assert_outcomes(skipped=2, failed=0)


def test_the_log_names_the_integration_tests_that_ran(skipping_suite, monkeypatch):
    """The green log has to say "this ran", not leave it to be inferred."""
    monkeypatch.setenv(REQUIRE_TOOLS_ENV, "1")
    result = skipping_suite.runpytest_subprocess("-rs")
    result.stdout.fnmatch_lines(
        [
            f"*integration tests that ran ({REQUIRE_TOOLS_ENV} is set)*",
            "FAILED test_skipping.py::test_marked",
        ]
    )
    # The unmarked test is not an integration test and has no business in the
    # block: a list padded with everything is a list nobody reads.
    assert "test_unmarked" not in result.stdout.str().split("integration tests that ran")[-1]


def test_the_block_stays_out_of_the_way_when_the_flag_is_unset(skipping_suite, monkeypatch):
    monkeypatch.delenv(REQUIRE_TOOLS_ENV, raising=False)
    result = skipping_suite.runpytest_subprocess("-rs")
    assert "integration tests that ran" not in result.stdout.str()


def test_a_passing_integration_test_is_left_alone(pytester, monkeypatch):
    """The hook must only ever touch a skip; anything else would be a trap."""
    pytester.makeconftest("from tests.conftest import pytest_runtest_makereport  # noqa: F401")
    pytester.makeini("[pytest]\nmarkers = integration: needs an external tool\n")
    pytester.makepyfile(
        test_running="""
        import pytest

        @pytest.mark.integration
        def test_marked():
            assert True

        @pytest.mark.integration
        @pytest.mark.xfail(reason="an xfail is a result, not an absence")
        def test_expected_failure():
            assert False
        """
    )
    monkeypatch.setenv("PYTHONPATH", str(REPO_ROOT))
    monkeypatch.setenv(REQUIRE_TOOLS_ENV, "1")
    result = pytester.runpytest_subprocess()
    result.assert_outcomes(passed=1, xfailed=1, failed=0)


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
