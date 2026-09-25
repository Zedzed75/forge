"""The pipeline domain — the one whose output depends on the other sections.

The only domain of the project that reads what the others declare. The whole
question is **how**: it must know no domain by name, and receive from the core
facts in the vocabulary of the contract — `DomainInfo`, `Command`, `Projection`.

The witness of that promise is `tests/fake_domains/unknown.py`: a domain the
plugin has never seen, with a tool its installation table does not know. If it
emits a correct job for it without a line changing, the promise holds; otherwise
it held by accident.

This module also locks down the three defects found before phase 8 was parked,
each by a test that would fail if they came back.

The plugin's own messages are still French: the domains are translated with
their templates, so the assertions below quote them as they are.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from forge import pipeline as pipeline_module
from forge.plugins.pipeline import answers, jobs, tools, tree, validators
from forge.plugins.pipeline.spec import PipelineSpec
from forge.plugins_api.manager import BUILTIN_PLUGINS, ForgeManager
from forge.spec.assembly import validate_spec
from forge.spec.io import load_spec_data
from tests.conftest import SPECS_DIR
from tests.fake_domains.unknown import UNKNOWN_TOOL

SPEC_GITHUB = SPECS_DIR / "pipeline-github.yml"
SPEC_GITLAB = SPECS_DIR / "pipeline-seul.yml"

#: Fake domain the pipeline plugin has never seen.
UNKNOWN_PLUGIN = "tests.fake_domains.unknown"


def _manager(*extras: str) -> ForgeManager:
    instance = ForgeManager()
    for module in (*BUILTIN_PLUGINS, *extras):
        instance.register_module(module)
    return instance


def _spec(path: Path = SPEC_GITHUB, *extras: str):
    manager = _manager(*extras)
    data = load_spec_data(path)
    return data, validate_spec(data, manager), manager


def _base(**pipeline) -> dict:
    return {
        "forge_version": 1,
        "service": {
            "name": "boutique",
            "description": "Boutique en ligne",
            "owner": "Equipe",
            "environments": [{"name": "dev"}, {"name": "prod", "production": True}],
        },
        "pipeline": pipeline or {"provider": "github"},
    }


def _generate(tmp_path: Path, path: Path = SPEC_GITHUB, *extras: str):
    data, spec, manager = _spec(path, *extras)
    pipeline_module.generate(data, spec, manager, tmp_path)
    return spec, manager


def _projection(given: dict, *extras: str) -> dict:
    manager = _manager(*extras)
    spec = validate_spec(given, manager)
    return manager.domain("pipeline").answers(spec)


def _issues(given: dict, level: str) -> list[str]:
    spec = validate_spec(given, _manager())
    return [issue.message for issue in answers.cross_check(spec) if issue.level == level]


# ---------------------------------------------------------------------------
# The promise: federate without knowing
# ---------------------------------------------------------------------------


def test_a_domain_never_seen_gets_its_validation_job():
    """The witness of phase 8, and the only test that really proves the promise.

    `unknown` did not exist when the pipeline plugin was written. If it gets a
    correct job without a line changing, then the pipeline reads the context and
    not a list of known domains.
    """
    given = _base(provider="github")
    given["unknown"] = {"enabled": True}
    projection = _projection(given, UNKNOWN_PLUGIN)

    keys = [job["key"] for job in projection["validate_jobs"]]
    assert "valider-unknown" in keys

    job = next(j for j in projection["jobs"] if j["key"] == "valider-unknown")
    assert job["name"] == "Valider Unknown Domain"
    labels = [step["name"] for step in job["steps"]]
    assert "unknown render" in labels and "unknown check" in labels


def test_an_unknown_tool_is_never_guessed():
    """The pipeline names what it cannot install, and makes the step fail.

    A silent step would let the job fall over further on with a "command not
    found", where the cause is no longer visible.
    """
    given = _base(provider="github")
    given["unknown"] = {"enabled": True}
    projection = _projection(given, UNKNOWN_PLUGIN)

    assert UNKNOWN_TOOL in projection["unknown_tools"]
    job = next(j for j in projection["jobs"] if j["key"] == "valider-unknown")
    installation = job["steps"][0]
    assert UNKNOWN_TOOL in " ".join(installation["run"])
    assert "exit 1" in installation["run"]


def test_a_domain_silent_about_deployment_is_named_not_guessed():
    """forge does not invent a deployment command: it says who stays silent."""
    _, spec, manager = _spec(SPEC_GITHUB)
    projection = manager.domain("pipeline").answers(spec)
    # The reference case declares helm and terraform, which know how to deploy.
    assert projection["undeployed"] == []
    assert projection["deploy_jobs"], "the domains that know how to deploy must have done so"


def test_the_pipeline_never_declares_itself_undeployed():
    """A pipeline does not deploy itself: it is the deployment."""
    given = _base(provider="github", deploy={"environments": ["dev"]})
    projection = _projection(given)
    assert "pipeline" not in projection["undeployed"]


# ---------------------------------------------------------------------------
# The three defects found before the domain was parked
# ---------------------------------------------------------------------------


def test_no_workstation_path_enters_the_pipeline(monkeypatch):
    """Defect 1: `Command.env` carries paths computed on the machine.

    Copying them over would carve a developer workstation's path into a CI file,
    and make the output **depend on the machine that produced it** — a golden
    file could no longer be compared.
    """
    monkeypatch.setenv("FORGE_ANSIBLE_COLLECTIONS", "/workstation/path/collections")
    given = _base(provider="github")
    given["unknown"] = {"enabled": True}
    projection = _projection(given, UNKNOWN_PLUGIN)

    rendered = json.dumps(projection)
    assert "/workstation/path" not in rendered
    assert "/opt/somewhere" not in rendered, "the path declared by `unknown` must be dropped"
    # What remains is behaviour configuration, valid anywhere.
    job = next(j for j in projection["jobs"] if j["key"] == "valider-unknown")
    assert job["steps"][1]["env"] == {"NO_COLOR": "1"}


def test_the_projection_does_not_depend_on_the_process_environment(monkeypatch):
    """Corollary of defect 1, checked on the complete output."""
    given = _base(provider="github")
    given["unknown"] = {"enabled": True}

    monkeypatch.delenv("FORGE_ANSIBLE_COLLECTIONS", raising=False)
    without = json.dumps(_projection(given, UNKNOWN_PLUGIN), sort_keys=True)
    monkeypatch.setenv("FORGE_ANSIBLE_COLLECTIONS", "/elsewhere")
    monkeypatch.setenv("FORGE_TF_PLUGIN_CACHE", "/elsewhere/again")
    with_them = json.dumps(_projection(given, UNKNOWN_PLUGIN), sort_keys=True)
    assert without == with_them


def test_the_deployment_follows_the_declared_rank_and_not_the_alphabet():
    """Defect 2: the chart went before the Terraform creating its namespace.

    No generic ordering could have guessed it: it is a property of the domain,
    and `DomainInfo.deploy_order` carries it.
    """
    _, spec, manager = _spec(SPEC_GITHUB)
    projection = manager.domain("pipeline").answers(spec)
    job = projection["deploy_jobs"][0]
    workdirs = [step["workdir"] for step in job["steps"] if step["workdir"]]
    first_terraform = next(i for i, d in enumerate(workdirs) if d.startswith("terraform"))
    first_helm = next(i for i, d in enumerate(workdirs) if d.startswith("helm"))
    assert first_terraform < first_helm, (
        "the foundation must go before what sits on it; alphabetical order would give "
        "the opposite"
    )


def test_the_stdin_chaining_becomes_a_file_redirection():
    """Defect 3: a pipe would hide the failure of the source.

    `pipefail` does not exist in the `/bin/sh` of a Debian image: the source
    writes to a file, the consumer reads it back, and every step carries its own
    exit code.
    """
    given = _base(provider="gitlab")
    given["unknown"] = {"enabled": True}
    projection = _projection(given, UNKNOWN_PLUGIN)

    job = next(j for j in projection["jobs"] if j["key"] == "valider-unknown")
    lines = [line for step in job["steps"] for line in step["run"]]
    source = next(line for line in lines if "render" in line)
    consumer = next(line for line in lines if "check" in line)

    assert "|" not in source and "|" not in consumer
    path = source.split("> ", 1)[1]
    assert consumer.endswith(f"< {path}")


# ---------------------------------------------------------------------------
# What the sub-model refuses, and what the cross-check reports
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("provider", "runner"), [("github", "ubuntu-latest"), ("gitlab", "debian:trixie-slim")]
)
def test_the_default_runner_depends_on_the_tool(provider, runner):
    """GitHub names a machine, GitLab an image: not the same default."""
    assert PipelineSpec(provider=provider).runner == runner


def test_a_repeated_branch_is_refused():
    with pytest.raises(ValueError, match="branches"):
        PipelineSpec(trigger={"branches": ["main", "main"]})


def test_an_unknown_key_is_refused():
    with pytest.raises(ValueError):
        PipelineSpec(providr="github")


def test_the_deployment_order_comes_from_the_shared_block():
    """The dev -> prod promotion is a property of the service, not of the pipeline."""
    spec = PipelineSpec(deploy={"environments": ["prod", "dev"]})
    assert spec.deployed_environments(("dev", "staging", "prod")) == ("dev", "prod")


def test_an_unknown_deployment_environment_is_an_error():
    given = _base(provider="github", deploy={"environments": ["recette"]})
    assert any("recette" in message for message in _issues(given, "error"))


def test_a_production_deployed_without_a_guard_is_reported():
    given = _base(
        provider="github",
        deploy={"environments": ["prod"], "manual_for_production": False},
    )
    assert any("sans approbation humaine" in m for m in _issues(given, "warning"))


def test_a_registry_the_token_does_not_open_is_reported():
    """forge can neither guess nor write a registry secret."""
    given = _base(provider="github", build={"registry": "registry.example.net"})
    assert any("n'ouvre pas" in message for message in _issues(given, "warning"))


def test_the_default_registry_triggers_nothing():
    given = _base(provider="github", build={"registry": "ghcr.io"})
    assert not any("n'ouvre pas" in message for message in _issues(given, "warning"))


def test_the_cross_check_is_silent_without_a_pipeline_section():
    class Without:
        pass

    assert answers.cross_check(Without()) == []


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


def test_the_announced_tree_matches_the_generated_files(tmp_path):
    """Arbitration R3, applied to the only domain whose output is the root."""
    spec, _ = _generate(tmp_path)
    produced = {
        path.relative_to(tmp_path).as_posix()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert set(tree.expected_paths(spec)) <= produced


def test_the_root_domain_writes_no_repository_level_file(tmp_path):
    """It shares its root with `README.md`, `forge.yml` and `.gitattributes`.

    Writing one of them would overwrite them, or make the generation fail without
    `--force`.
    """
    spec, _ = _generate(tmp_path)
    announced = set(tree.expected_paths(spec))
    assert not (announced & tree.REPO_LEVEL_FILES)


@pytest.mark.parametrize(
    ("path", "expected", "absent"),
    [
        (SPEC_GITHUB, tree.GITHUB_WORKFLOW, tree.GITLAB_CONFIG),
        (SPEC_GITLAB, tree.GITLAB_CONFIG, tree.GITHUB_WORKFLOW),
    ],
    ids=["github", "gitlab"],
)
def test_only_the_requested_dialect_is_written(path, expected, absent, tmp_path):
    _generate(tmp_path, path)
    assert (tmp_path / expected).is_file()
    assert not (tmp_path / absent).exists()


@pytest.mark.parametrize("path", [SPEC_GITHUB, SPEC_GITLAB], ids=["github", "gitlab"])
def test_the_emitted_file_is_valid_yaml(path, tmp_path):
    spec, _ = _generate(tmp_path, path)
    content = (tmp_path / tree.workflow_path(spec)).read_bytes().decode("utf-8")
    document = yaml.safe_load(content)
    assert isinstance(document, dict) and document


def test_the_dependencies_between_jobs_name_existing_jobs(tmp_path):
    """A dangling `needs` is accepted by the file and refused by the tool."""
    _, spec, manager = _spec(SPEC_GITHUB)
    projection = manager.domain("pipeline").answers(spec)
    keys = {job["key"] for job in projection["jobs"]}
    for job in projection["jobs"]:
        assert set(job["needs"]) <= keys, job["key"]


def test_the_image_tag_is_the_commit_fingerprint(tmp_path):
    """Never `latest`: two builds of the same `latest` are two images."""
    _, spec, manager = _spec(SPEC_GITHUB)
    projection = manager.domain("pipeline").answers(spec)
    step = projection["build_job"]["steps"][0]
    assert step["env"]["FORGE_IMAGE_TAG"] == "${{ github.sha }}"
    assert ":latest" not in " ".join(step["run"])


def test_no_credential_is_written_into_the_emitted_file(tmp_path):
    spec, _ = _generate(tmp_path)
    content = (tmp_path / tree.workflow_path(spec)).read_bytes().decode("utf-8")
    for pattern in ("password:", "token:", "secret_key", "BEGIN "):
        assert pattern not in content


def test_diff_sees_no_difference_right_after_generation(tmp_path):
    """Exercises `foreign_paths`: a root domain does not compare what is not its own."""
    data, spec, manager = _spec(SPEC_GITHUB)
    pipeline_module.generate(data, spec, manager, tmp_path)
    differences = pipeline_module.diff(
        data, spec, manager, tmp_path, only=["pipeline"], spec_path=tmp_path / "forge.yml"
    )
    for difference in differences:
        assert difference.empty, difference.summary()


# ---------------------------------------------------------------------------
# Installation table and validators
# ---------------------------------------------------------------------------


def test_every_tool_declared_by_a_shipped_domain_is_installable():
    """A tool the pipeline cannot install makes its job unusable."""
    manager = _manager()
    missing: set[str] = set()
    for path in sorted(SPECS_DIR.glob("*.yml")):
        data = load_spec_data(path)
        if not (set(data) & set(manager.domain_names())):
            continue
        spec = validate_spec(data, manager)
        for name in manager.domain_names():
            if getattr(spec, name, None) is None:
                continue
            for command in manager.domain(name).validators(spec, Path(name)):
                if not tools.known(command.tool):
                    missing.add(f"{name}:{command.tool}")
    assert missing == set(), f"tools with no installation recipe: {sorted(missing)}"


def test_the_tool_versions_are_pinned():
    """"The latest version" changes behaviour one morning with no commit."""
    for recipe in tools.INSTALLS:
        for line in recipe.steps:
            assert "latest/download" not in line, recipe.name


@pytest.mark.parametrize(
    ("path", "tool"), [(SPEC_GITHUB, "actionlint"), (SPEC_GITLAB, "yamllint")], ids=["github", "gitlab"]
)
def test_the_validator_depends_on_the_dialect(path, tool, tmp_path):
    _, spec, _ = _spec(path)
    commands = validators.commands(spec, tmp_path)
    assert [command.tool for command in commands] == [tool]
    assert tree.workflow_path(spec) in commands[0].argv


# ---------------------------------------------------------------------------
# Interview
# ---------------------------------------------------------------------------


def test_the_interview_produces_a_valid_section():
    from forge.plugins.pipeline import interview
    from tests.scripted_prompter import ScriptedPrompter

    service = validate_spec(_base(provider="github"), _manager()).service
    prompter = ScriptedPrompter(
        [
            "github",       # CI tool
            "main",         # main branch
            True,           # trigger on pull requests
            True,           # build an image
            "ghcr.io",      # registry
            "boutique",     # image repository
            True,           # deploy
            ["dev"],        # deployed environments
        ]
    )
    section = interview.run(prompter, service)
    assert prompter.exhausted, f"answers not consumed: {prompter.answers}"
    model = PipelineSpec.model_validate(section)
    assert model.is_github
    assert model.deployed_environments(("dev", "prod")) == ("dev",)


def test_the_interview_stops_at_validating_when_no_environment_is_selected():
    from forge.plugins.pipeline import interview
    from tests.scripted_prompter import ScriptedPrompter

    service = validate_spec(_base(provider="github"), _manager()).service
    prompter = ScriptedPrompter(["github", "main", True, False, True, []])
    section = interview.run(prompter, service)
    assert prompter.exhausted
    assert "deploy" not in section


# ---------------------------------------------------------------------------
# Real validation of the emitted file
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.parametrize(
    ("path", "tool"), [(SPEC_GITHUB, "actionlint"), (SPEC_GITLAB, "yamllint")], ids=["github", "gitlab"]
)
def test_the_generated_pipeline_passes_its_validator(path, tool, tmp_path):
    """`actionlint` knows the schema of GitHub workflows, their expressions and
    their actions. On the GitLab side there is no offline equivalent: the
    guarantee is weaker there, and the domain README says so."""
    from tests.conftest import require_tools

    require_tools("pipeline", tool)

    spec, manager = _generate(tmp_path, path)
    result = pipeline_module.validate(spec, manager, tmp_path, only=["pipeline"])
    failures = [check for report in result.reports for check in report.failures()]
    assert not failures, (
        f"failing validators: {', '.join(c.label for c in failures)}\n"
        + "\n".join(c.detail for c in failures)[:2000]
    )


def test_every_variable_expansion_is_protected_by_quotes():
    """shellcheck (SC2086) makes actionlint fail on a bare expansion.

    Found by CI: shellcheck was not installed on the workstation, so actionlint
    did not run it and the step passed. This is not zeal — a tag containing a
    blank or a wildcard would be split into several arguments by the shell.
    """
    import re

    given = _base(provider="github", build={"registry": "ghcr.io", "image": "acme/x"})
    projection = _projection(given)
    bare = re.compile(r'(?<!")\$[A-Za-z_][A-Za-z0-9_]*')
    for job in projection["jobs"]:
        for step in job["steps"]:
            for line in step["run"]:
                # `2>/dev/null` and already quoted expansions are safe; we only
                # look for the `$VAR` that nothing surrounds.
                offenders = [
                    found.group(0)
                    for found in bare.finditer(line)
                    if f'"{found.group(0)}"' not in line
                    and f'"{found.group(0)}\\"' not in line
                    and not _inside_quotes(line, found.start())
                ]
                assert not offenders, f"{job['key']} / {step['name']}: {offenders}\n{line}"


def _inside_quotes(line: str, position: int) -> bool:
    """True if the character at `position` sits inside a pair of `"`."""
    return line[:position].count('"') % 2 == 1
