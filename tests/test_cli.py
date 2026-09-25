"""End-to-end tests of the CLI, backed by the `demo` plugin.

They check the whole wiring — interview, spec, copier render, validation,
comparison — and not the detail of each layer, which is covered elsewhere.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from forge import pipeline
from forge.cli import app, run_new
from forge.plugins_api.manager import ForgeManager
from tests.conftest import DEMO_PLUGIN, REPO_ROOT, SPECS_DIR
from tests.scripted_prompter import ScriptedPrompter

runner = CliRunner()

#: Answers replaying the full interview: the service block, then the demo domain.
#: The values are the ones the reference specs use, so they stay as they are
#: until the fixtures and the templates are translated together.
INTERVIEW = [
    "boutique",                # service name
    "Boutique en ligne",       # description
    "Equipe Plateforme",       # owner
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
        ["generate", "-s", str(SPECS_DIR / "demo-complet.yml"), "-o", str(tmp_path)],
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
            str(SPECS_DIR / "demo-complet.yml"),
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
            str(SPECS_DIR / "demo-complet.yml"),
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
    assert model.service.name == "boutique"
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


def test_update_ignores_a_domain_that_was_never_generated(tmp_path, monkeypatch):
    result = _invoke(["update", "-o", str(tmp_path)], monkeypatch)
    assert result.exit_code == 0
    assert "none" in result.stdout


def test_the_plugin_template_path_is_the_declared_one(tmp_path):
    manager = ForgeManager()
    manager.register_module(DEMO_PLUGIN)
    hooks = manager.domain("demo")
    assert (Path(pipeline.copier_runner.template_root()) / hooks.template_subdir()).is_dir()


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
