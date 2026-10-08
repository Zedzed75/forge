"""End-to-end tests of the CLI, backed by the `demo` plugin.

They check the whole wiring — interview, spec, copier render, validation,
comparison — and not the detail of each layer, which is covered elsewhere.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from forge import pipeline
from forge.cli import CHANGELOG_URL, app, run_new
from forge.plugins_api.manager import BUILTIN_PLUGINS, ForgeManager
from forge.render.copier_runner import ANSWERS_FILENAME, PACKAGE_RELPATH
from tests.conftest import (
    DEMO_PLUGIN,
    GOLDEN_DIR,
    REPO_ROOT,
    SPECS_DIR,
    stable_text,
    tree_files,
)
from tests.scripted_prompter import ScriptedPrompter

runner = CliRunner()

#: Reference case rendered by the installed-forge test. A shipped domain, not
#: `demo`: the demo plugin is only registered through FORGE_PLUGINS, which an
#: installed forge has no reason to carry.
INSTALL_CASE = "ansible-ci"

#: Answers replaying the full interview: the service block, then the demo domain.
#: The values are the ones the reference specs use.
INTERVIEW = [
    "storefront",              # service name
    "Online store",            # description
    "Platform Team",           # owner
    "",                        # contact address
    "dev,prod",                # environments
    True,                      # is one of them production?
    "prod",                    # which one
    "dev.example.net",         # dev domain
    "example.net",             # prod domain
    True,                      # generate the demo domain?
    "bonjour",                 # greeting
    "cpu,requetes",            # widgets
    "gauge",                   # kind of the cpu widget
    "counter",                 # kind of the requetes widget
]


def _invoke(args: list[str], monkeypatch: pytest.MonkeyPatch, plugins: str = DEMO_PLUGIN):
    monkeypatch.setenv("FORGE_PLUGINS", plugins)
    return runner.invoke(app, args)


# ---------------------------------------------------------------------------
# Surface
# ---------------------------------------------------------------------------


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "forge" in result.stdout


def test_plugins_lists_the_registered_domains(monkeypatch):
    result = _invoke(["plugins"], monkeypatch)
    assert result.exit_code == 0
    assert "demo" in result.stdout


def test_plugins_says_so_plainly_when_there_is_none(monkeypatch):
    """A branch only reachable when no domain is shipped nor declared."""
    monkeypatch.setattr("forge.plugins_api.manager.BUILTIN_PLUGINS", ())
    result = runner.invoke(app, ["plugins"])
    assert result.exit_code == 0
    assert "no registered domain" in result.stdout


def test_plugins_lists_the_shipped_domains():
    """The Ansible domain is available without declaring anything."""
    result = runner.invoke(app, ["plugins"])
    assert result.exit_code == 0
    assert "ansible" in result.stdout


def test_catalog_lists_the_entries(monkeypatch):
    result = _invoke(["catalog", "demo"], monkeypatch)
    assert result.exit_code == 0
    assert "gauge" in result.stdout


def test_catalog_details_one_entry(monkeypatch):
    result = _invoke(["catalog", "demo", "gauge"], monkeypatch)
    assert result.exit_code == 0
    assert "detailed" in result.stdout


def test_catalog_refuses_an_unknown_entry(monkeypatch):
    result = _invoke(["catalog", "demo", "sonar"], monkeypatch)
    assert result.exit_code == 1


def test_catalog_refuses_an_unknown_domain(monkeypatch):
    # A name no plugin will ever carry: "terraform" served here until it became
    # a real domain (phase 7).
    result = _invoke(["catalog", "nonexistent"], monkeypatch)
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# generate
# ---------------------------------------------------------------------------


def test_generate_produces_the_expected_tree(tmp_path, monkeypatch):
    result = _invoke(
        ["generate", "-s", str(SPECS_DIR / "demo-full.yml"), "-o", str(tmp_path)],
        monkeypatch,
    )
    assert result.exit_code == 0, result.stdout
    assert (tmp_path / "forge.yml").is_file()
    assert (tmp_path / "README.md").is_file()
    assert (tmp_path / "demo" / ".copier-answers.yml").is_file()
    assert (tmp_path / "demo" / "environments" / "prod" / "cpu.yml").is_file()


def test_generate_in_dry_run_writes_nothing(tmp_path, monkeypatch):
    result = _invoke(
        [
            "generate",
            "-s",
            str(SPECS_DIR / "demo-full.yml"),
            "-o",
            str(tmp_path),
            "--dry-run",
        ],
        monkeypatch,
    )
    assert result.exit_code == 0
    assert list(tmp_path.iterdir()) == []


def test_generate_refuses_an_unknown_domain(tmp_path, monkeypatch):
    result = _invoke(
        [
            "generate",
            "-s",
            str(SPECS_DIR / "demo-full.yml"),
            "-o",
            str(tmp_path),
            "--only",
            "terraform",
        ],
        monkeypatch,
    )
    assert result.exit_code == 1


def test_generate_says_so_when_no_spec_can_be_found(tmp_path, monkeypatch):
    result = _invoke(["generate", "-o", str(tmp_path)], monkeypatch)
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# validate / diff on an already generated project
# ---------------------------------------------------------------------------


def test_validate_passes_on_a_freshly_generated_project(demo_project, monkeypatch):
    target, _, _ = demo_project
    result = _invoke(["validate", "-o", str(target)], monkeypatch)
    assert result.exit_code == 0, result.stdout
    assert "no difference" in result.stdout


def test_diff_sees_no_difference_right_after_generation(demo_project, monkeypatch):
    target, _, _ = demo_project
    result = _invoke(["diff", "-o", str(target)], monkeypatch)
    assert result.exit_code == 0, result.stdout
    assert "up to date" in result.stdout


def test_diff_reports_a_file_deleted_from_the_target(demo_project, tmp_path, monkeypatch):
    target, model, manager = demo_project
    copy = tmp_path / "copy"
    copy.mkdir()
    import shutil

    shutil.copytree(target / "demo", copy / "demo")
    (copy / "demo" / "environments" / "prod" / "cpu.yml").unlink()
    shutil.copy(target / "forge.yml", copy / "forge.yml")

    result = _invoke(["diff", "-o", str(copy)], monkeypatch)
    assert result.exit_code == 0, result.stdout
    assert "environments/prod/cpu.yml" in result.stdout


# ---------------------------------------------------------------------------
# new (scripted interview)
# ---------------------------------------------------------------------------


def test_new_conducts_the_interview_then_generates(tmp_path):
    manager = ForgeManager()
    manager.register_module(DEMO_PLUGIN)
    prompter = ScriptedPrompter(INTERVIEW)
    result = run_new(
        tmp_path,
        manager,
        prompter,
        spec_out=tmp_path / "forge.yml",
    )
    assert prompter.exhausted
    assert result.domains == ["demo"]
    assert (tmp_path / "forge.yml").is_file()
    assert (tmp_path / "demo" / "environments" / "dev" / "cpu.yml").is_file()


def test_new_writes_a_replayable_spec(tmp_path):
    manager = ForgeManager()
    manager.register_module(DEMO_PLUGIN)
    run_new(
        tmp_path / "project",
        manager,
        ScriptedPrompter(INTERVIEW),
        spec_out=tmp_path / "forge.yml",
        dry_run=True,
    )
    data, model = pipeline.load_spec(tmp_path / "forge.yml", manager)
    assert model.service.name == "storefront"
    assert model.domain_names() == ("demo",)
    assert [w["name"] for w in data["demo"]["widgets"]] == ["cpu", "requetes"]


def test_new_allows_declining_a_domain(tmp_path):
    manager = ForgeManager()
    manager.register_module(DEMO_PLUGIN)
    answers = list(INTERVIEW[:9]) + [False]
    result = run_new(
        tmp_path,
        manager,
        ScriptedPrompter(answers),
        spec_out=tmp_path / "forge.yml",
        dry_run=True,
    )
    assert result.domains == []


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_update_replays_the_template_on_a_generated_project(tmp_path, monkeypatch):
    """`copier update` requires a git target repository: that is what the core does."""
    import subprocess

    from tests.conftest import build_project, template_is_dirty

    if template_is_dirty():
        pytest.skip("template not committed: copier update cannot compare two refs")

    build_project(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
        cwd=tmp_path,
        check=True,
    )
    result = _invoke(["update", "-o", str(tmp_path)], monkeypatch)
    assert result.exit_code == 0, result.stdout
    assert "demo" in result.stdout
    assert (tmp_path / "demo" / "environments" / "prod" / "cpu.yml").is_file()
    # An update that moved files is the only place forge can tell the user that
    # a rename may ask something of them outside the generated tree.
    assert CHANGELOG_URL in result.stdout


def test_update_ignores_a_domain_that_was_never_generated(tmp_path, monkeypatch):
    result = _invoke(["update", "-o", str(tmp_path)], monkeypatch)
    assert result.exit_code == 0
    assert "none" in result.stdout
    # Nothing moved, so there is nothing to go and read: pointing at the
    # changelog here would train the user to ignore the line.
    assert CHANGELOG_URL not in result.stdout


def test_the_plugin_template_path_is_the_declared_one(tmp_path):
    manager = ForgeManager()
    manager.register_module(DEMO_PLUGIN)
    hooks = manager.domain("demo")
    assert (Path(pipeline.copier_runner.template_root()) / hooks.template_subdir()).is_dir()


# ---------------------------------------------------------------------------
# Packaging
# ---------------------------------------------------------------------------
# forge had never been usable from an install: the template root was looked up at
# the repository root, which does not exist in a wheel. Nothing in the suite
# noticed, because every other test runs from a checkout where that path is there
# by construction. These two tests are the ones that would have caught it, and
# they are the only ones that look at forge the way a user who ran `pip install`
# does.
# ---------------------------------------------------------------------------


def _build_wheel(into: Path) -> Path:
    """Build the wheel into `into` and return it, or skip when uv is missing."""
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv missing: the wheel cannot be built")
    subprocess.run(
        [uv, "build", "--wheel", "--out-dir", str(into)],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    wheels = list(into.glob("*.whl"))
    assert len(wheels) == 1, f"exactly one wheel expected: {wheels}"
    return wheels[0]


@pytest.mark.integration
def test_the_wheel_ships_the_whole_template_root(tmp_path):
    """Everything the renderer reads must be inside the wheel, under `forge/`.

    `copier.yml` and `partials/` live at the repository root, so they only get in
    through the `force-include` table in `pyproject.toml`. Nothing else would warn
    if that table were dropped or mistyped: non-.py files are the usual trap of a
    build backend, and a checkout keeps working either way.
    """
    with zipfile.ZipFile(_build_wheel(tmp_path)) as archive:
        shipped = set(archive.namelist())

    manager = ForgeManager()
    for module in BUILTIN_PLUGINS:
        manager.register_module(module)
    prefix = f"{PACKAGE_RELPATH}/"
    expected_dirs = [
        # The wheel carries the shortened form, which is what an installed forge
        # asks `resolve_subdir` for.
        f"forge/{manager.domain(name).template_subdir().removeprefix(prefix)}/"
        for name in manager.domain_names()
    ]

    for path in ("forge/copier.yml", "forge/partials/header.jinja"):
        assert path in shipped, f"{path} missing from the wheel"
    for directory in expected_dirs:
        assert any(name.startswith(directory) for name in shipped), (
            f"no template shipped under {directory}"
        )


@pytest.mark.integration
def test_an_installed_forge_generates_the_same_project_as_a_checkout(tmp_path):
    """The acceptance criterion itself: install the wheel, generate, compare.

    Deliberately end to end and deliberately slow. It is the only test that proves
    the claim forge makes on PyPI — that installing it gives you a working
    generator — and the defect it guards against was invisible to all 600-odd other
    tests precisely because they share the repository with the code they exercise.

    The venv is built with no access to this checkout, and the comparison is
    against the stored golden tree, so a wheel that renders *something* but not the
    right thing fails too. `_commit` differs by design: an installed forge renders
    from a plain directory, so copier records no template commit (DESIGN.md §8
    Q2-bis).
    """
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv missing: the wheel cannot be built")
    wheel = _build_wheel(tmp_path / "dist")

    venv = tmp_path / "venv"
    subprocess.run([uv, "venv", "-q", str(venv)], check=True, capture_output=True)
    subprocess.run(
        [uv, "pip", "install", "-q", str(wheel)],
        check=True,
        capture_output=True,
        env={**os.environ, "VIRTUAL_ENV": str(venv)},
    )
    forge_exe = next(
        path
        for path in (venv / "Scripts" / "forge.exe", venv / "bin" / "forge")
        if path.exists()
    )

    project = tmp_path / "project"
    project.mkdir()
    spec = project / "forge.yml"
    spec.write_bytes((SPECS_DIR / f"{INSTALL_CASE}.yml").read_bytes())
    result = subprocess.run(
        [str(forge_exe), "generate", "-s", str(spec), "-o", str(project / "out")],
        capture_output=True,
        text=True,
        # Run from the venv, not from the checkout: a cwd inside the repository
        # would let a path-relative lookup succeed and hide the very defect.
        cwd=venv,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    reference = GOLDEN_DIR / INSTALL_CASE
    produced = project / "out"
    assert tree_files(produced) == tree_files(reference), (
        "an installed forge produced a different tree than the golden one"
    )
    differences = [
        name
        for name in tree_files(reference)
        if stable_text(produced / name).encode("utf-8")
        != (reference / name).read_bytes()
        # The answers file records the template root and the commit, both of which
        # legitimately differ between an install and a checkout.
        and not name.endswith(ANSWERS_FILENAME)
    ]
    assert not differences, f"differing content: {', '.join(differences)}"


def test_the_announced_version_is_the_project_s():
    """`forge --version` must tell the truth.

    The version used to be written in `pyproject.toml` **and** in
    `forge/__init__.py`; the two had diverged, and the CLI announced `0.1.0` on a
    repository tagged `v1.1.0`. `pyproject.toml` now reads it from the module,
    and this test checks that the link holds.
    """
    import tomllib

    from forge import __version__

    project = tomllib.loads(
        (REPO_ROOT / "pyproject.toml").read_bytes().decode("utf-8")
    )["project"]
    assert "version" not in project, (
        "the version must not be hardcoded in pyproject.toml: it would be a "
        "second source, and the two would diverge"
    )
    assert project["dynamic"] == ["version"]

    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout
