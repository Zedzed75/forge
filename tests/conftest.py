"""Shared fixtures and the golden harness.

The `demo` plugin serves as the reference domain: it is not registered in
production, the tests declare it explicitly. It is the one exercising the real
mechanisms (nested yields, plugin filters, file filtering).
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any

import pytest

from forge.plugins_api.manager import ForgeManager
from forge.spec.assembly import validate_spec
from forge.spec.io import load_spec_data

#: `pytester` runs a real pytest on a throwaway test file. It is how
#: `pytest_runtest_makereport` below is tested end to end rather than by calling
#: the generator by hand: a report-mangling hook that is only unit-tested is a
#: hook nobody has seen wired up.
pytest_plugins = ["pytester"]

#: Module of the demonstration plugin, as `FORGE_PLUGINS` expects it.
DEMO_PLUGIN = "forge.plugins.demo.plugin"

#: Root of the forge repository, which carries the single copier.yml.
REPO_ROOT = Path(__file__).resolve().parents[1]

#: Reference specs and their matching golden trees.
SPECS_DIR = REPO_ROOT / "tests" / "specs"
GOLDEN_DIR = REPO_ROOT / "tests" / "golden"

#: Lines of the answers file that vary from one machine and one render to the
#: next: they are neutralised before the golden comparison.
_VOLATILE_ANSWERS = (
    (re.compile(r"^_commit:.*$", re.MULTILINE), "_commit: <commit>"),
    (re.compile(r"^_src_path:.*$", re.MULTILINE), "_src_path: <src>"),
)


# ---------------------------------------------------------------------------
# Fail-closed validators
# ---------------------------------------------------------------------------
# The project's central claim is "the generated project passes its own real
# validators". Seven integration tests assert it, and each of them used to skip
# when its tool was missing. That is right on a Windows workstation, where
# ansible-core and promtool cannot run natively -- and wrong in CI, where a
# degraded install step (a moved release URL, a renamed tarball member) turned
# those tests into no-ops while the build stayed green. `FORGE_REQUIRE_TOOLS=1`
# closes that hole: the skip becomes a failure, and a green CI check positively
# proves every domain's validators actually ran.
# ---------------------------------------------------------------------------

#: Environment variable that forbids skipping on a missing validator.
REQUIRE_TOOLS_ENV = "FORGE_REQUIRE_TOOLS"

#: Values of `FORGE_REQUIRE_TOOLS` read as "required". Anything else is off, so
#: `FORGE_REQUIRE_TOOLS=0` disables the flag rather than enabling it by mere
#: presence.
_REQUIRE_TOOLS_TRUTHY = frozenset({"1", "true", "yes", "on"})


#: Outcome of every `integration` test of the session, by node id, reported at
#: the end of the run so the log names what ran instead of implying it.
_INTEGRATION_RESULTS: dict[str, str] = {}


def tools_are_required() -> bool:
    """True when a missing validator must fail the run instead of skipping it."""
    return os.environ.get(REQUIRE_TOOLS_ENV, "").strip().lower() in _REQUIRE_TOOLS_TRUTHY


def require_tools(domain: str, *names: str, requires_linux: bool = True) -> None:
    """Check that every validator of `domain` is available, or stop the test.

    Unset flag: skips, exactly as the seven call sites did before -- the local
    development loop is unchanged. Flag set: fails, naming the domain and every
    missing tool.

    One shared helper on purpose. A fail-closed switch that seven call sites can
    each opt out of is not a switch, and the drift would be invisible: a site
    left behind keeps skipping and the build stays green.
    """
    from forge.validate import tools

    missing = [name for name in names if not tools.probe(name, requires_linux).available]
    if not missing:
        return

    reason = f"domain {domain}: validator(s) missing, natively and in WSL: {', '.join(missing)}"
    if tools_are_required():
        pytest.fail(
            f"{reason}\n"
            f"{REQUIRE_TOOLS_ENV} is set: skipping is forbidden here. This run is "
            "supposed to prove that the generated project passes its real "
            "validators; without the tool it proves nothing, so it fails instead "
            "of reporting a reduced success. Install the tool, or unset "
            f"{REQUIRE_TOOLS_ENV} to get the development behaviour back.",
            pytrace=False,
        )
    pytest.skip(reason)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]):
    """Under `FORGE_REQUIRE_TOOLS`, a skipped `integration` test fails the run.

    `require_tools` closes the hole it knows about: a validator binary that is
    not there. It cannot close the one next to it -- an integration test that
    skips itself for some *other* reason. That hole was open and occupied: the
    single test of `forge update` skipped in every CI run, on all three Python
    versions, because `uv run` wrote an untracked `uv.lock` and
    `template_is_dirty` then did exactly what it was written to do. Nobody saw
    it, because the build was green and the skip line scrolled past.

    So the rule is stated once here, for the whole marker, instead of at each
    call site: a run that claims to prove something about generated projects may
    not let an integration test report success without having run. A test that
    legitimately has to skip in CI is not an integration test and must lose the
    marker -- the structural skip in `test_plugins.py` carries no marker and is
    deliberately left alone.
    """
    report = yield
    if item.get_closest_marker("integration") is None:
        return report

    if (
        report.skipped
        and not hasattr(report, "wasxfail")  # an xfail is a result, not an absence
        and tools_are_required()
    ):
        # A skipped report carries `(path, lineno, "Skipped: <reason>")`.
        reason = report.longrepr[2] if isinstance(report.longrepr, tuple) else str(report.longrepr)
        report.outcome = "failed"
        report.longrepr = (
            f"{reason.removeprefix('Skipped: ')}\n"
            f"{REQUIRE_TOOLS_ENV} is set: an `integration` test may not skip here. "
            "This run is supposed to prove that the generated projects are valid; a "
            "test that did not run proves nothing, and a skip that nobody reads is "
            "worse than a missing test because it reads like coverage. Fix the cause "
            f"named above, drop the `integration` marker, or unset {REQUIRE_TOOLS_ENV} "
            "to get the development behaviour back."
        )

    if report.when == "call" or report.outcome != "passed":
        _INTEGRATION_RESULTS[item.nodeid] = report.outcome
    return report


def pytest_terminal_summary(terminalreporter, exitstatus: int, config: pytest.Config) -> None:
    """Make the log name the integration tests that ran, one line each.

    Reading a CI log for what *did not* run is how `forge update` went untested
    for months: `-rs` lists the skips, the count line gives a total, and nothing
    anywhere named the test. Absence had to be inferred, and nobody inferred it.

    So under the flag the run states it positively. The block is the artifact to
    check when someone asks "did the generated projects really get validated" --
    one line per integration test, with the outcome, instead of a total to
    subtract from.
    """
    if not tools_are_required() or not _INTEGRATION_RESULTS:
        return
    terminalreporter.write_sep("=", f"integration tests that ran ({REQUIRE_TOOLS_ENV} is set)")
    for nodeid, outcome in sorted(_INTEGRATION_RESULTS.items()):
        terminalreporter.write_line(f"{outcome.upper()} {nodeid}")


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--regen-golden",
        action="store_true",
        default=False,
        help="Rewrites the golden references instead of comparing against them.",
    )
    # Deliberately a separate flag from --regen-golden. Re-blessing the golden
    # trees is routine after an intended template change; re-blessing a
    # structural fingerprint means claiming the structure was *meant* to move,
    # which is exactly the claim a reviewer is supposed to examine.
    parser.addoption(
        "--regen-fingerprints",
        action="store_true",
        default=False,
        help="Rewrites the stored structural fingerprints instead of comparing them.",
    )


@pytest.fixture
def regen_golden(request: pytest.FixtureRequest) -> bool:
    """True when the run is asked to re-bless the golden references."""
    return bool(request.config.getoption("--regen-golden"))


@pytest.fixture
def regen_fingerprints(request: pytest.FixtureRequest) -> bool:
    """True when the run is asked to rewrite the stored fingerprints."""
    return bool(request.config.getoption("--regen-fingerprints"))


@pytest.fixture
def manager() -> ForgeManager:
    """Manager holding nothing but the demonstration plugin."""
    instance = ForgeManager()
    instance.register_module(DEMO_PLUGIN)
    return instance


@pytest.fixture
def demo_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Declare the demo plugin for calls that go through `default_manager()`."""
    monkeypatch.setenv("FORGE_PLUGINS", DEMO_PLUGIN)


@pytest.fixture
def spec_data() -> dict[str, Any]:
    """Minimal valid specification, which each test may modify.

    The sample values are the ones the reference specs and the golden trees use.
    They stay as they are until the templates and the fixtures are translated
    together; changing them here alone would make the two drift apart.
    """
    return {
        "forge_version": 1,
        "service": {
            "name": "boutique",
            "description": "Boutique en ligne de demonstration",
            "owner": "Equipe Plateforme",
            "owner_email": "plateforme@example.net",
            "labels": {"tier": "frontend"},
            "environments": [
                {"name": "dev", "domain": "dev.example.net"},
                {"name": "prod", "domain": "example.net", "production": True},
            ],
        },
        "demo": {
            "greeting": "bonjour",
            "widgets": [
                {"name": "cpu", "kind": "gauge", "detailed": True},
                {"name": "requetes", "kind": "counter"},
            ],
        },
    }


@pytest.fixture
def spec(spec_data: dict[str, Any], manager: ForgeManager):
    """Validated instance matching `spec_data`."""
    return validate_spec(spec_data, manager)


# ---------------------------------------------------------------------------
# Golden harness
# ---------------------------------------------------------------------------


def spec_files() -> list[Path]:
    """Reference specs, sorted: the order of the test cases is deterministic."""
    return sorted(SPECS_DIR.glob("*.yml"))


def load_case(path: Path, manager: ForgeManager) -> tuple[dict[str, Any], Any]:
    """Load a reference spec and validate it."""
    data = load_spec_data(path)
    return data, validate_spec(data, manager)


def stable_text(path: Path) -> str:
    """Content of a generated file, stripped of what varies per machine.

    Read as **bytes**: `read_text` translates CRLF to LF while reading, which
    would blind the golden comparison to a line-ending regression — precisely
    what the normalisation is supposed to guarantee.
    """
    text = path.read_bytes().decode("utf-8")
    if path.name == ".copier-answers.yml":
        for pattern, replacement in _VOLATILE_ANSWERS:
            text = pattern.sub(replacement, text)
    return text


def tree_files(root: Path) -> list[str]:
    """Relative paths of every file under `root`, sorted."""
    return sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and ".git" not in path.parts
    )


def bless(source: Path, destination: Path) -> None:
    """Replace the golden tree `destination` with `source`."""
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)
    for path in sorted(destination.rglob("*")):
        if path.is_file():
            path.write_text(stable_text(path), encoding="utf-8", newline="\n")


def template_is_dirty() -> bool:
    """True if the template repository carries uncommitted changes.

    `copier update` compares two git references: a project rendered from a dirty
    working tree references a temporary commit, unreachable afterwards. The
    update tests are therefore skipped until the repository is clean.
    """
    import subprocess

    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):  # pragma: no cover
        return True
    return bool(result.stdout.strip())


def render_all_plugins(spec_path: Path, target: Path) -> Path:
    """Render one reference spec with the demo plugin and every shipped domain.

    Shared by the golden harness and the fingerprint harness so both observe the
    exact same rendering. A spec that does not declare a section simply does not
    generate that domain, so registering every plugin is harmless.
    """
    from forge import pipeline
    from forge.plugins_api.manager import BUILTIN_PLUGINS

    manager = ForgeManager()
    for module in (DEMO_PLUGIN, *BUILTIN_PLUGINS):
        manager.register_module(module)
    data, model = load_case(spec_path, manager)
    pipeline.generate(data, model, manager, target)
    return target


def build_project(target: Path, spec_name: str = "demo-full") -> tuple[Any, ForgeManager]:
    """Generate a demonstration project into `target` (a real copier render)."""
    from forge import pipeline

    instance = ForgeManager()
    instance.register_module(DEMO_PLUGIN)
    data, model = load_case(SPECS_DIR / f"{spec_name}.yml", instance)
    pipeline.generate(data, model, instance, target)
    return model, instance


@pytest.fixture(scope="session")
def demo_project(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Any, ForgeManager]:
    """Project generated once per session: the copier render is slow."""
    target = tmp_path_factory.mktemp("demo-project")
    model, instance = build_project(target)
    return target, model, instance


@pytest.fixture(autouse=True)
def _clean_forge_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate each test from the session's environment variables."""
    for name in ("FORGE_PLUGINS", "FORGE_TEMPLATE_SRC", "FORGE_PLUGIN_JINJA"):
        monkeypatch.delenv(name, raising=False)
    # `monkeypatch` restores the original value at the end of the test: no state
    # leaks from one test to the next, unlike a direct os.environ write.
    monkeypatch.setenv("PYTHONIOENCODING", "utf-8")
