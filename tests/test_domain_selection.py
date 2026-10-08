"""The domains are a **choice**, never a bundle.

That is the central promise of the tool: one single description of the service,
and the user decides what to get out of it. One project may need nothing but a
Helm chart; another, nothing but Ansible roles and playbooks; a third, nothing
but a Terraform foundation. Producing several domains at once is **one**
possible use, not the normal use.

Three ways of choosing, all covered here:

* a section absent from `forge.yml` generates nothing;
* `--only` restricts a run to certain domains;
* the `forge new` interview asks which ones to produce.

**This module is written so that it cannot drift.** Nothing in it hardcodes the
number of domains or their names: everything is read from the plugin registry. A
domain added without its single-domain specification makes
`test_every_shipped_domain_has_a_single_domain_specification` fail, so the
promise stays checked on *every* shipped domain, not on the ones we happened to
remember the day the test was written.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from forge import pipeline
from forge.cli import app, run_new
from forge.errors import SpecValidationError
from forge.plugins_api.manager import BUILTIN_PLUGINS, ForgeManager
from forge.spec.assembly import validate_spec
from forge.spec.io import load_spec_data, save_spec
from tests.conftest import REPO_ROOT, SPECS_DIR
from tests.scripted_prompter import ScriptedPrompter

runner = CliRunner()

SPEC_BOTH = SPECS_DIR / "two-domains.yml"


def _manager() -> ForgeManager:
    instance = ForgeManager()
    for module in BUILTIN_PLUGINS:
        instance.register_module(module)
    return instance


#: Shipped domains, read from the registry. No name is hardcoded here: that is
#: what keeps this module tied to the reality of the product.
DOMAINS: tuple[str, ...] = _manager().domain_names()

#: Output subdirectory of each domain, read from its `DomainInfo`.
OUTDIRS: dict[str, str] = {name: _manager().domain(name).info.outdir for name in DOMAINS}

#: One **single-domain** specification per shipped domain: the case where a
#: project needs only that one. The completeness test below forbids adding a
#: domain without adding its own.
SINGLE_DOMAIN_SPECS: dict[str, Path] = {
    "ansible": SPECS_DIR / "ansible-ci.yml",
    "helm": SPECS_DIR / "helm-full.yml",
    "terraform": SPECS_DIR / "terraform-full.yml",
    "monitoring": SPECS_DIR / "monitoring-full.yml",
    "pipeline": SPECS_DIR / "pipeline-only.yml",
}


def _generate(spec_path: Path, target: Path, **kwargs) -> pipeline.GenerationResult:
    manager = _manager()
    data = load_spec_data(spec_path)
    return pipeline.generate(data, validate_spec(data, manager), manager, target, **kwargs)


def _produced_domains(target: Path) -> set[str]:
    """Domains whose output really exists in the target.

    Derived from the registry, never from a list written here: a domain added is
    watched without anyone thinking about it.

    A domain whose output **is** the repository root — the `pipeline` domain,
    whose file only makes sense where the CI tool reads it — has no subdirectory
    to look for: we then check the presence of at least one of the paths it
    announces.
    """
    produced = {
        name
        for name, outdir in OUTDIRS.items()
        if outdir not in (".", "") and (target / outdir).is_dir()
    }
    for name, outdir in OUTDIRS.items():
        if outdir in (".", "") and _writes_at_the_root(target, name):
            produced.add(name)
    return produced


def _writes_at_the_root(target: Path, domain: str) -> bool:
    """True if the root domain wrote at least one of its files.

    The paths are the ones the plugin announces itself, minus the copier answers
    file: that one exists in any generated target, whatever the domain.
    """
    from forge.plugins.pipeline import tree as pipeline_tree

    if domain != "pipeline":  # pragma: no cover - only one root domain
        return False
    return (target / pipeline_tree.GITHUB_WORKFLOW).is_file() or (
        target / pipeline_tree.GITLAB_CONFIG
    ).is_file()


# ---------------------------------------------------------------------------
# The catalogue of cases cannot drift
# ---------------------------------------------------------------------------


def test_every_shipped_domain_has_a_single_domain_specification():
    """A domain added without its single-domain case makes this test fail.

    It is the lock that makes every other test in this module exhaustive: they
    are parametrised on `SINGLE_DOMAIN_SPECS`, and `SINGLE_DOMAIN_SPECS` must
    cover the registry.
    """
    missing = sorted(set(DOMAINS) - set(SINGLE_DOMAIN_SPECS))
    extra = sorted(set(SINGLE_DOMAIN_SPECS) - set(DOMAINS))
    assert not missing, (
        f"shipped domains without a single-domain specification: {missing}. "
        "Add one to tests/specs/ and reference it in SINGLE_DOMAIN_SPECS: the "
        "promise \"the domains are a choice\" must be checked on each of them."
    )
    assert not extra, f"SINGLE_DOMAIN_SPECS names unknown domains: {extra}"


@pytest.mark.parametrize(
    "domain", sorted(SINGLE_DOMAIN_SPECS), ids=sorted(SINGLE_DOMAIN_SPECS)
)
def test_the_reference_specification_really_declares_a_single_domain(domain):
    """Guard on the test data itself."""
    data = load_spec_data(SINGLE_DOMAIN_SPECS[domain])
    declared = sorted(set(data) & set(DOMAINS))
    assert declared == [domain], f"{SINGLE_DOMAIN_SPECS[domain].name} declares {declared}"


# ---------------------------------------------------------------------------
# 1. An absent section generates nothing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "domain", sorted(SINGLE_DOMAIN_SPECS), ids=sorted(SINGLE_DOMAIN_SPECS)
)
def test_a_single_domain_produces_only_itself(domain, tmp_path):
    """The most common use case: a project needs only one domain."""
    result = _generate(SINGLE_DOMAIN_SPECS[domain], tmp_path)
    assert result.domains == [domain]
    assert _produced_domains(tmp_path) == {domain}


@pytest.mark.parametrize(
    "domain", sorted(SINGLE_DOMAIN_SPECS), ids=sorted(SINGLE_DOMAIN_SPECS)
)
def test_a_single_domain_really_produces_files(domain, tmp_path):
    """"Producing only itself" must not come to mean "producing nothing"."""
    _generate(SINGLE_DOMAIN_SPECS[domain], tmp_path)
    root = tmp_path / OUTDIRS[domain]
    files = [path for path in root.rglob("*") if path.is_file()]
    # A domain writing at the root shares it with the repository-level files: we
    # then count what it announces, not what is found there.
    expected = 1 if OUTDIRS[domain] in (".", "") else 5
    assert len(files) > expected, f"{domain}: only {len(files)} file(s)"


def test_a_specification_with_no_domain_says_so_plainly(tmp_path):
    """An empty project with no explanation is not an acceptable answer."""
    spec = tmp_path / "forge.yml"
    save_spec(
        {
            "forge_version": 1,
            "service": {
                "name": "nu",
                "description": "Service sans domaine",
                "owner": "Equipe",
                "environments": [{"name": "prod"}],
            },
        },
        spec,
        sections=[],
    )
    target = tmp_path / "project"
    result = runner.invoke(app, ["generate", "-s", str(spec), "-o", str(target)])

    assert result.exit_code == 0
    assert "no domain" in result.stdout
    assert "available domains" in result.stdout
    # Every shipped domain is offered, not only the ones of the day.
    for name in DOMAINS:
        assert name in result.stdout
    assert _produced_domains(target) == set()


# ---------------------------------------------------------------------------
# 2. `--only` restricts a run
# ---------------------------------------------------------------------------


def test_only_restricts_the_generation_to_one_domain(tmp_path):
    result = _generate(SPEC_BOTH, tmp_path, only=["helm"])
    assert result.domains == ["helm"]
    assert _produced_domains(tmp_path) == {"helm"}


def test_only_accepts_several_domains(tmp_path):
    result = _generate(SPEC_BOTH, tmp_path, only=["ansible", "helm"])
    assert result.domains == ["ansible", "helm"]


@pytest.mark.parametrize(
    "domain", sorted(SINGLE_DOMAIN_SPECS), ids=sorted(SINGLE_DOMAIN_SPECS)
)
def test_only_cannot_add_a_domain_absent_from_the_specification(domain, tmp_path):
    """`--only` restricts; it never adds a domain the spec does not ask for.

    And it says so: asking for an absent domain is a named error, not an empty
    generation. Silence would let the user believe the domain was produced.
    """
    others = [name for name in DOMAINS if name != domain]
    with pytest.raises(SpecValidationError) as raised:
        _generate(SINGLE_DOMAIN_SPECS[domain], tmp_path, only=others)

    message = str(raised.value)
    for absent in others:
        assert absent in message
    assert domain in message, "the message must recall what the spec declares"
    assert _produced_domains(tmp_path) == set()


# ---------------------------------------------------------------------------
# 3. The interview asks which ones to produce
# ---------------------------------------------------------------------------


#: Answers to the common trunk of `forge new`, shared by every interview.
COMMON_SERVICE: list = [
    "boutique",              # service name
    "Boutique en ligne",     # description
    "Equipe Plateforme",     # owner
    "",                      # contact
    "prod",                  # environments
    True,                    # is one of them production?
    "prod",                  # which one
    "",                      # DNS domain of prod
]


def test_the_interview_allows_keeping_helm_alone(tmp_path):
    """The user ticks `helm` alone: no other domain must come out."""
    manager = _manager()
    prompter = ScriptedPrompter(
        COMMON_SERVICE
        + [
            ["helm"],                # <- THE CHOICE: helm alone
            "1.36", "0.1.0", "1.0.0",
            "docker.io", "boutique", "appVersion",
            "per_env",
            "api", "deployment", ["service"], "8080",
            False,                   # add another component?
            True, True,              # makefile, helm tests
        ]
    )
    result = run_new(tmp_path, manager, prompter, spec_out=tmp_path / "forge.yml")

    assert prompter.exhausted, f"answers not consumed: {prompter.answers}"
    assert result.domains == ["helm"]
    assert _produced_domains(tmp_path) == {"helm"}
    written = load_spec_data(tmp_path / "forge.yml")
    assert set(written) & set(DOMAINS) == {"helm"}


def test_the_interview_allows_keeping_terraform_alone(tmp_path):
    """The same promise, on a domain with no legacy ancestor at all."""
    manager = _manager()
    prompter = ScriptedPrompter(
        COMMON_SERVICE
        + [
            ["terraform"],           # <- THE CHOICE: terraform alone
            ["namespace", "quota"],  # resource families
            "~> 1.9",                # version constraint
            "per_env",               # namespace strategy
            "local",                 # state backend
            "kubeconfig",            # authentication
            "~/.kube/config",        # kubeconfig path
            True,                    # one context per environment
            True,                    # makefile
            True,                    # .tflint.hcl
        ]
    )
    result = run_new(tmp_path, manager, prompter, spec_out=tmp_path / "forge.yml")

    assert prompter.exhausted, f"answers not consumed: {prompter.answers}"
    assert result.domains == ["terraform"]
    assert _produced_domains(tmp_path) == {"terraform"}
    written = load_spec_data(tmp_path / "forge.yml")
    assert set(written) & set(DOMAINS) == {"terraform"}


# ---------------------------------------------------------------------------
# The CLI must say what it does
# ---------------------------------------------------------------------------


def test_generate_announces_what_it_is_going_to_produce(tmp_path):
    result = runner.invoke(
        app,
        ["generate", "-s", str(SPEC_BOTH), "-o", str(tmp_path), "--only", "helm", "--dry-run"],
    )
    assert result.exit_code == 0, result.stdout
    assert "helm/" in result.stdout
    assert "ansible/" not in result.stdout


@pytest.mark.parametrize(
    "domain", sorted(SINGLE_DOMAIN_SPECS), ids=sorted(SINGLE_DOMAIN_SPECS)
)
def test_plugins_tells_the_requested_domains_from_the_others(domain):
    """The count is read from the registry: it cannot go stale."""
    result = runner.invoke(app, ["plugins", "-s", str(SINGLE_DOMAIN_SPECS[domain])])
    assert result.exit_code == 0, result.stdout
    lines = result.stdout.splitlines()

    requested_line = next(line for line in lines if line.startswith(domain))
    assert "requested by the specification" in requested_line

    for other in DOMAINS:
        if other == domain:
            continue
        line = next(line for line in lines if line.startswith(other))
        assert "not requested" in line, f"{other}: {line}"

    assert f"1 domain(s) requested out of {len(DOMAINS)}" in result.stdout


@pytest.mark.parametrize(
    "spec",
    sorted(SINGLE_DOMAIN_SPECS.values()) + [SPEC_BOTH],
    ids=sorted(SINGLE_DOMAIN_SPECS) + ["both"],
)
def test_validate_accepts_a_single_domain_project_as_well_as_a_multi_domain_one(spec, tmp_path):
    """No cross-domain check must penalise a project with a single domain."""
    _generate(spec, tmp_path)
    result = runner.invoke(app, ["validate", "-o", str(tmp_path), "--skip-missing"])
    assert result.exit_code == 0, result.stdout
    assert "no difference" in result.stdout


@pytest.mark.parametrize(
    "domain", sorted(SINGLE_DOMAIN_SPECS), ids=sorted(SINGLE_DOMAIN_SPECS)
)
def test_diff_sees_no_difference_on_a_single_domain_project(domain, tmp_path):
    """A freshly generated single-domain project is up to date, by definition."""
    _generate(SINGLE_DOMAIN_SPECS[domain], tmp_path)
    result = runner.invoke(
        app, ["diff", "-o", str(tmp_path), "-s", str(SINGLE_DOMAIN_SPECS[domain])]
    )
    assert result.exit_code == 0, result.stdout
    assert "up to date" in result.stdout


# ---------------------------------------------------------------------------
# The shipped examples are valid specifications
# ---------------------------------------------------------------------------

EXAMPLES_DIR = REPO_ROOT / "examples"


def _examples() -> list[Path]:
    return sorted(EXAMPLES_DIR.glob("*.yml"))


def test_single_domain_examples_are_shipped():
    """A user must find, in the repository, one case per domain."""
    covered = {
        name
        for path in _examples()
        for name in set(load_spec_data(path)) & set(DOMAINS)
        if len(set(load_spec_data(path)) & set(DOMAINS)) == 1
    }
    assert covered == set(DOMAINS), (
        f"missing single-domain examples for: {sorted(set(DOMAINS) - covered)}"
    )


@pytest.mark.parametrize(
    "example", _examples(), ids=[path.stem for path in _examples()]
)
def test_every_example_is_valid_and_generates(example, tmp_path):
    """An example that does not generate is worse than no example at all."""
    result = _generate(example, tmp_path)
    requested = sorted(set(load_spec_data(example)) & set(DOMAINS))
    assert result.domains == requested
    assert _produced_domains(tmp_path) == set(requested)
