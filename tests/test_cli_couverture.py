"""Coverage of the paths the initial suite did not touch.

Every test in this module matches a defect demonstrated by the audit of the
core: a behaviour that could be deleted from the code entirely without a single
test going red. They stay apart from the rest of the CLI tests to remain
readable, and because they need **several** registered domains, which the `demo`
plugin alone does not allow.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from forge import pipeline
from forge.cli import app
from forge.errors import RenderError
from forge.plugins_api.manager import ForgeManager
from forge.spec.assembly import validate_spec
from forge.spec.io import save_spec
from tests.conftest import DEMO_PLUGIN, REPO_ROOT, SPECS_DIR, build_project, load_case

runner = CliRunner()

#: Modules of the fake domains, importable through `FORGE_PLUGINS`.
OTHER = "tests.domaines_factices.autre"
NORMAL = "tests.domaines_factices.normal"
DIVERGENT = "tests.domaines_factices.divergent"
DISORDER = "tests.domaines_factices.desordre"
FRAGILE = "tests.domaines_factices.outil_absent"

#: Fake domain whose package provides no filter module.
ISOLATED = "tests.domaine_isole"

#: Keys of forge.yml that are not domain sections.
CORE_KEYS = ("forge_version", "service")


def _invoke(args: list[str], monkeypatch: pytest.MonkeyPatch, plugins: str = DEMO_PLUGIN):
    monkeypatch.setenv("FORGE_PLUGINS", plugins)
    return runner.invoke(app, args)


def _manager(*modules: str) -> ForgeManager:
    """Manager populated with the requested plugin modules."""
    instance = ForgeManager()
    for module in modules or (DEMO_PLUGIN,):
        instance.register_module(module)
    return instance


def _write_spec(path: Path, data: dict) -> Path:
    """Write a test specification, without going through the CLI."""
    sections = [key for key in data if key not in CORE_KEYS]
    save_spec(data, path, sections=sections)
    return path


def _two_domain_spec() -> dict:
    """Specification asking for the `demo` domain AND the `autre` domain."""
    section = {"greeting": "bonjour", "widgets": [{"name": "cpu", "kind": "gauge"}]}
    return {
        "forge_version": 1,
        "service": {
            "name": "boutique",
            "description": "Boutique en ligne",
            "owner": "Equipe Plateforme",
            "environments": [{"name": "prod", "production": True}],
        },
        "demo": dict(section),
        "autre": dict(section),
    }


def _fake_spec(*domains: str) -> dict:
    """Specification enabling nothing but content-free fake domains."""
    data: dict = {
        "forge_version": 1,
        "service": {
            "name": "boutique",
            "description": "Boutique en ligne",
            "owner": "Equipe Plateforme",
            "environments": [{"name": "dev"}, {"name": "prod", "production": True}],
        },
    }
    for name in domains:
        data[name] = {"enabled": True}
    return data


# ---------------------------------------------------------------------------
# --only filtering: it requires two registered domains
# ---------------------------------------------------------------------------


def test_only_generates_nothing_but_the_requested_domain(tmp_path):
    """Without this filter, `--only helm` would also regenerate `ansible/`,
    overwriting files the user had explicitly excluded."""
    manager = _manager(DEMO_PLUGIN, OTHER)
    data = _two_domain_spec()
    pipeline.generate(data, validate_spec(data, manager), manager, tmp_path, only=["demo"])

    assert (tmp_path / "demo").is_dir()
    assert not (tmp_path / "autre").exists()


def test_only_does_not_remove_the_other_domains_from_the_index(tmp_path):
    """The repository-level index describes the SPECIFICATION, not the last filter."""
    manager = _manager(DEMO_PLUGIN, OTHER)
    data = _two_domain_spec()
    pipeline.generate(data, validate_spec(data, manager), manager, tmp_path, only=["demo"])

    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "`demo/`" in readme
    assert "`autre/`" in readme
    assert "#   - autre" in (tmp_path / "forge.yml").read_text(encoding="utf-8")


def test_both_domains_are_generated_without_a_filter(tmp_path):
    manager = _manager(DEMO_PLUGIN, OTHER)
    data = _two_domain_spec()
    result = pipeline.generate(data, validate_spec(data, manager), manager, tmp_path)

    assert result.domains == ["autre", "demo"]
    assert (tmp_path / "autre" / "environments" / "prod" / "cpu.yml").is_file()
    assert (tmp_path / "demo" / "environments" / "prod" / "cpu.yml").is_file()


# ---------------------------------------------------------------------------
# validate: exit code and missing tools
# ---------------------------------------------------------------------------


def test_validate_exits_1_when_a_cross_domain_check_fails(tmp_path, monkeypatch):
    """Without this test, losing exit code 1 would break nothing."""
    spec_path = _write_spec(tmp_path / "forge.yml", _fake_spec("normal", "divergent"))
    result = _invoke(
        ["validate", "-s", str(spec_path), "-o", str(tmp_path)],
        monkeypatch,
        plugins=f"{NORMAL},{DIVERGENT}",
    )
    assert result.exit_code == 1, result.stdout
    assert "ERROR" in result.stdout
    assert "service name" in result.stdout


def test_validate_exits_0_on_a_mere_warning(tmp_path, monkeypatch):
    spec_path = _write_spec(tmp_path / "forge.yml", _fake_spec("normal", "desordre"))
    result = _invoke(
        ["validate", "-s", str(spec_path), "-o", str(tmp_path)],
        monkeypatch,
        plugins=f"{NORMAL},{DISORDER}",
    )
    assert result.exit_code == 0, result.stdout
    assert "WARNING" in result.stdout


def test_validate_fails_when_a_tool_is_missing(tmp_path, monkeypatch):
    spec_path = _write_spec(tmp_path / "forge.yml", _fake_spec("fragile"))
    result = _invoke(
        ["validate", "-s", str(spec_path), "-o", str(tmp_path)],
        monkeypatch,
        plugins=FRAGILE,
    )
    assert result.exit_code == 1
    assert "MISSING" in result.stdout
    assert "that is the point of the test" in result.stdout


def test_skip_missing_passes_but_warns_that_nothing_was_checked(tmp_path, monkeypatch):
    spec_path = _write_spec(tmp_path / "forge.yml", _fake_spec("fragile"))
    result = _invoke(
        ["validate", "-s", str(spec_path), "-o", str(tmp_path), "--skip-missing"],
        monkeypatch,
        plugins=FRAGILE,
    )
    assert result.exit_code == 0, result.stdout
    assert "SKIPPED" in result.stdout
    assert "WARNING" in result.stdout


# ---------------------------------------------------------------------------
# update: the integration test is not enough, it does not run on a dirty repo
# ---------------------------------------------------------------------------


def test_update_calls_copier_for_every_generated_domain(tmp_path, monkeypatch):
    """Always executed: it kills the "an update that updates nothing" mutation."""
    build_project(tmp_path)
    calls: list[dict] = []

    def spy(**kwargs):
        calls.append(kwargs)
        return kwargs["dst"]

    monkeypatch.setattr(pipeline.copier_runner, "run_update", spy)
    updated = pipeline.update(_manager(), tmp_path, ref="v1.2.3", conflict="rej")

    assert updated == ["demo"]
    assert len(calls) == 1
    assert calls[0]["dst"] == tmp_path / "demo"
    assert calls[0]["ref"] == "v1.2.3"
    assert calls[0]["conflict"] == "rej"


def test_update_refuses_an_unknown_domain(tmp_path, monkeypatch):
    """A typo in a CI script must not exit 0."""
    result = _invoke(["update", "-o", str(tmp_path), "--only", "dmeo"], monkeypatch)
    assert result.exit_code == 1


def test_update_refuses_a_domain_named_but_never_generated(tmp_path):
    with pytest.raises(RenderError, match="copier-answers"):
        pipeline.update(_manager(), tmp_path, only=["demo"])


# ---------------------------------------------------------------------------
# generate: conflicts, the user's forge.yml, system errors
# ---------------------------------------------------------------------------


def test_generate_refuses_to_overwrite_a_modified_file_without_force(tmp_path, monkeypatch):
    """Without this check, copier opens a prompt and breaks under Git Bash."""
    build_project(tmp_path)
    target = tmp_path / "demo" / "README.md"
    target.write_text("edited by hand\n", encoding="utf-8")

    result = _invoke(
        ["generate", "-s", str(SPECS_DIR / "demo-complet.yml"), "-o", str(tmp_path)],
        monkeypatch,
    )
    assert result.exit_code == 1
    assert target.read_text(encoding="utf-8") == "edited by hand\n"

    force = _invoke(
        [
            "generate",
            "-s",
            str(SPECS_DIR / "demo-complet.yml"),
            "-o",
            str(tmp_path),
            "--force",
        ],
        monkeypatch,
    )
    assert force.exit_code == 0, force.stdout
    # Generated content: still French until the templates are translated.
    assert "Domaine demo" in target.read_text(encoding="utf-8")


def test_generate_preserves_the_comments_of_the_target_s_forge_yml(tmp_path, monkeypatch):
    """The target's spec is the source of truth: re-serialising it would mutilate it."""
    build_project(tmp_path)
    spec_path = tmp_path / "forge.yml"
    spec_path.write_text(
        spec_path.read_text(encoding="utf-8") + "\n# HOUSE NOTE: do not touch\n",
        encoding="utf-8",
    )

    result = _invoke(["generate", "-o", str(tmp_path), "--force"], monkeypatch)
    assert result.exit_code == 0, result.stdout
    assert "HOUSE NOTE" in spec_path.read_text(encoding="utf-8")


def test_generate_towards_a_file_gives_a_readable_error(tmp_path, monkeypatch):
    file_path = tmp_path / "report.txt"
    file_path.write_text("x", encoding="utf-8")
    result = _invoke(
        ["generate", "-s", str(SPECS_DIR / "demo-complet.yml"), "-o", str(file_path)],
        monkeypatch,
    )
    assert result.exit_code == 1
    assert "Traceback" not in result.stdout


# ---------------------------------------------------------------------------
# diff: the repository-level files do not go through copier
# ---------------------------------------------------------------------------


def test_diff_also_compares_the_repository_level_files(tmp_path, monkeypatch):
    """Without this, `forge diff` would report "up to date" about what it did not look at."""
    build_project(tmp_path)
    (tmp_path / "README.md").write_text("rewritten index\n", encoding="utf-8")

    result = _invoke(["diff", "-o", str(tmp_path)], monkeypatch)
    assert result.exit_code == 0, result.stdout
    assert "(root)" in result.stdout
    assert "README.md" in result.stdout


# ---------------------------------------------------------------------------
# Plugin filters
# ---------------------------------------------------------------------------


def test_plugin_jinja_module_finds_the_plugin_s_filter_module():
    hooks = _manager().domain("demo")
    assert pipeline.plugin_jinja_module(hooks) == "forge.plugins.demo.jinja_ext"


def test_plugin_jinja_module_returns_empty_when_the_plugin_provides_none():
    hooks = _manager(ISOLATED).domain("isole")
    assert pipeline.plugin_jinja_module(hooks) == ""


# ---------------------------------------------------------------------------
# new: the filter is validated before the interview
# ---------------------------------------------------------------------------


def test_new_refuses_an_unknown_domain_before_asking_a_single_question(tmp_path, monkeypatch):
    """Otherwise the user answers ten questions then gets an empty project."""
    result = _invoke(
        ["new", "-o", str(tmp_path), "--only", "ansibel"], monkeypatch
    )
    assert result.exit_code == 1
    assert list(tmp_path.iterdir()) == []


# ---------------------------------------------------------------------------
# update: proof that a template change really reaches the target
# ---------------------------------------------------------------------------


def _git(cwd: Path, *args: str) -> None:
    """Test git command, with a local identity and long paths enabled.

    `core.longpaths` is indispensable under Windows: the segments carrying a
    `yield` tag push the paths past the default limit (MIGRATION.md §2.7).
    """
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=t@example.invalid",
            "-c",
            "user.name=test",
            "-c",
            "core.longpaths=true",
            *args,
        ],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def _template_repository(root: Path) -> Path:
    """Minimal versioned copy of the current template, isolated from the forge repository.

    Copying the strict minimum — the root copier.yml and the demo plugin's
    template — rather than cloning the repository: the test then stays valid even
    when the working tree carries uncommitted changes, which is precisely when an
    update regression is possible.
    """
    template = root / "template"
    subdirectory = Path("src/forge/plugins/demo/template")
    (template / subdirectory).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(REPO_ROOT / "copier.yml", template / "copier.yml")
    shutil.copytree(REPO_ROOT / subdirectory, template / subdirectory)
    _git(template, "init", "-q")
    _git(template, "add", "-A")
    _git(template, "commit", "-qm", "initial template")
    return template


@pytest.mark.integration
def test_update_applies_a_template_change(tmp_path, monkeypatch):
    """The heart of `forge update`: a template change must reach an already
    delivered project. Without this assertion, the copier call could be removed
    entirely without a test flinching."""
    template = _template_repository(tmp_path)
    target = tmp_path / "project"
    monkeypatch.setenv("FORGE_TEMPLATE_SRC", str(template))
    monkeypatch.setenv("FORGE_PLUGINS", DEMO_PLUGIN)

    manager = _manager()
    data, model = load_case(SPECS_DIR / "demo-complet.yml", manager)
    pipeline.generate(data, model, manager, target)

    delivered = target / "demo" / "README.md"
    assert "ADDED IN VERSION 2" not in delivered.read_text(encoding="utf-8")

    # The target must be a clean git repository: copier does a three-way merge.
    _git(target, "init", "-q")
    _git(target, "add", "-A")
    _git(target, "commit", "-qm", "initial project")

    # Template change, committed: this is what `forge update` must bring over.
    source = template / "src/forge/plugins/demo/template/README.md.jinja"
    source.write_text(
        source.read_text(encoding="utf-8") + "\nADDED IN VERSION 2\n",
        encoding="utf-8",
        newline="\n",
    )
    _git(template, "commit", "-qam", "template version 2")

    assert pipeline.update(manager, target) == ["demo"]
    assert "ADDED IN VERSION 2" in delivered.read_text(encoding="utf-8")


@pytest.mark.integration
def test_update_refuses_a_moved_template_without_a_commit(tmp_path, monkeypatch):
    """A project from another machine: forge fixes _src_path, then stops.

    It cannot commit on the user's behalf, and copier refuses a dirty target
    repository: the message therefore has to say what to do.
    """
    template = _template_repository(tmp_path)
    target = tmp_path / "project"
    monkeypatch.setenv("FORGE_TEMPLATE_SRC", str(template))

    manager = _manager()
    data, model = load_case(SPECS_DIR / "demo-complet.yml", manager)
    pipeline.generate(data, model, manager, target)

    _git(target, "init", "-q")
    _git(target, "add", "-A")
    _git(target, "commit", "-qm", "initial project")

    # The project is supposed to come from another machine: its template points
    # elsewhere.
    answers = target / "demo" / ".copier-answers.yml"
    answers.write_text(
        re.sub(
            r"^_src_path:.*$",
            "_src_path: /home/alice/forge",
            answers.read_text(encoding="utf-8"),
            count=1,
            flags=re.MULTILINE,
        ),
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(RenderError, match="commit"):
        pipeline.update(manager, target)
    # The fix was really written: that is what the user has to commit.
    assert template.as_posix() in answers.read_text(encoding="utf-8")
