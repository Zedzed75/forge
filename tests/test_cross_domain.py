"""What forge brings when two domains describe the same service.

That is the promise of the project: one single description, two infrastructure
projects consistent with each other. This module checks that the consistency is
really observed — and above all that it is observed **without the core knowing**
what an Ansible role or a Helm chart is.

None of these findings is reachable by a single domain: that is the whole reason
for comparing projections (decision Q4).
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
from typer.testing import CliRunner

from forge import pipeline
from forge.cli import app
from forge.plugins_api.manager import BUILTIN_PLUGINS, ForgeManager
from forge.spec.assembly import validate_spec
from forge.spec.io import load_spec_data, save_spec
from forge.validate.consistency import FACET_VOCABULARY, compare_projections
from tests.conftest import REPO_ROOT

runner = CliRunner()

#: Specification asking for both domains.
SPEC_BOTH = REPO_ROOT / "tests" / "specs" / "two-domains.yml"


def _manager() -> ForgeManager:
    instance = ForgeManager()
    for module in BUILTIN_PLUGINS:
        instance.register_module(module)
    return instance


def _projections(data: dict) -> dict:
    manager = _manager()
    spec = validate_spec(data, manager)
    return {
        name: manager.domain(name).projection(spec)
        for name in spec.domain_names()
        if manager.domain(name).projection(spec) is not None
    }


@pytest.fixture
def data() -> dict:
    return load_spec_data(SPEC_BOTH)


# ---------------------------------------------------------------------------
# What the two domains declare
# ---------------------------------------------------------------------------


def test_both_domains_are_generated_from_a_single_specification(tmp_path, data):
    manager = _manager()
    result = pipeline.generate(data, validate_spec(data, manager), manager, tmp_path)

    assert result.domains == ["ansible", "helm"]
    assert (tmp_path / "ansible" / "playbooks" / "site.yml").is_file()
    assert (tmp_path / "helm" / "charts" / "boutique" / "Chart.yaml").is_file()
    # One forge.yml, one index README, at the root.
    assert (tmp_path / "forge.yml").is_file()
    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "`ansible/`" in readme and "`helm/`" in readme


def test_a_consistent_specification_produces_no_finding(data):
    assert compare_projections(_projections(data)) == []


def test_the_facets_of_both_domains_belong_to_the_vocabulary(data):
    """A facet name is a shared namespace: outside the vocabulary it is compared
    with nobody."""
    declared = {
        facet
        for projection in _projections(data).values()
        for facet in projection.facets
    }
    assert declared <= set(FACET_VOCABULARY), (
        f"facets outside the vocabulary: {sorted(declared - set(FACET_VOCABULARY))}"
    )


def test_the_two_kinds_of_hosts_are_not_confused(data):
    """Inventory machines and Ingress hosts do not designate the same thing.

    Having named both of them `hosts` made `forge validate` fail on a perfectly
    consistent specification: it is the first defect the meeting of two real
    domains revealed.
    """
    projections = _projections(data)
    machines = projections["ansible"].facets["inventory_hosts"]
    domains = projections["helm"].facets["ingress_hosts"]

    assert machines and domains
    assert not set(machines) & set(domains)
    assert all(name.startswith("db-") for name in machines)
    assert all("." in name for name in domains)


# ---------------------------------------------------------------------------
# What only the comparison can see
# ---------------------------------------------------------------------------


def test_an_environment_deployed_but_not_administered_is_reported(data):
    """Helm deploys to production, Ansible declares no machine there.

    Neither domain can say so on its own: Ansible does not know Helm exists, and
    Helm does not read the inventory.
    """
    data = copy.deepcopy(data)
    del data["ansible"]["hosts"]["prod"]

    findings = compare_projections(_projections(data))
    assert [finding.level for finding in findings] == ["warning"]
    assert "prod" in findings[0].message
    assert "helm" in findings[0].message and "ansible" in findings[0].message
    assert findings[0].hint


def test_a_divergent_service_name_would_be_an_error(data):
    """Guard: both domains must name the same service."""
    projections = _projections(data)
    projections["helm"] = type(projections["helm"])(
        service_name="another-service",
        environments=projections["helm"].environments,
        labels=projections["helm"].labels,
        facets=projections["helm"].facets,
    )
    findings = compare_projections(projections)
    assert any(finding.level == "error" for finding in findings)
    assert any("service name" in finding.message for finding in findings)


# ---------------------------------------------------------------------------
# The CLI, end to end
# ---------------------------------------------------------------------------


def _write_spec(data: dict, target: Path) -> Path:
    path = target / "forge.yml"
    save_spec(data, path, sections=["ansible", "helm"])
    return path


def test_validate_exits_zero_on_a_two_domain_project(tmp_path, data):
    """The nominal case: two domains, no inconsistency."""
    manager = _manager()
    pipeline.generate(data, validate_spec(data, manager), manager, tmp_path)

    result = runner.invoke(
        app, ["validate", "-o", str(tmp_path), "--skip-missing"]
    )
    assert result.exit_code == 0, result.stdout
    assert "no difference" in result.stdout


def test_diff_covers_both_domains_and_the_root(tmp_path, data):
    manager = _manager()
    pipeline.generate(data, validate_spec(data, manager), manager, tmp_path)

    result = runner.invoke(app, ["diff", "-o", str(tmp_path)])
    assert result.exit_code == 0, result.stdout
    for section in ("(root)", "ansible", "helm"):
        assert section in result.stdout


def test_only_regenerates_one_domain_and_leaves_the_other_intact(tmp_path, data):
    """`--only` must protect the excluded domain, including from its own traces."""
    manager = _manager()
    pipeline.generate(data, validate_spec(data, manager), manager, tmp_path)

    witness = tmp_path / "helm" / "charts" / "boutique" / "Chart.yaml"
    marked = witness.read_text(encoding="utf-8") + "\n# no-regeneration mark\n"
    witness.write_text(marked, encoding="utf-8", newline="\n")

    result = pipeline.generate(
        data,
        validate_spec(data, manager),
        manager,
        tmp_path,
        only=["ansible"],
        force=True,
        spec_path=tmp_path / "forge.yml",
    )
    assert result.domains == ["ansible"]
    assert witness.read_text(encoding="utf-8") == marked, "helm/ was regenerated"


def test_update_only_touches_the_requested_domain(tmp_path, data):
    """`forge update --only`: the excluded domain must not be called."""
    manager = _manager()
    pipeline.generate(data, validate_spec(data, manager), manager, tmp_path)

    called: list[str] = []

    def spy(**kwargs):
        called.append(Path(kwargs["dst"]).name)
        return kwargs["dst"]

    import pytest as _pytest

    with _pytest.MonkeyPatch.context() as patch:
        patch.setattr(pipeline.copier_runner, "run_update", spy)
        updated = pipeline.update(manager, tmp_path, only=["helm"])

    assert updated == ["helm"]
    assert called == ["helm"], "ansible/ should not have been called"


# ---------------------------------------------------------------------------
# The proof: both real toolchains, on a single specification
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_both_projects_pass_their_real_validators(tmp_path, data):
    """The promise of the project, checked end to end.

    A single description of the service produces two infrastructure projects,
    and both pass their own tools: `ansible-playbook --syntax-check` per
    environment and `ansible-lint` on one side, `helm lint`, `helm template` and
    `kubeconform -strict` per environment on the other. Nine external commands,
    and no domain knowledge in the core.
    """
    from tests.conftest import require_tools

    require_tools(
        "ansible+helm", "ansible-playbook", "ansible-lint", "helm", "kubeconform"
    )

    manager = _manager()
    spec = validate_spec(data, manager)
    pipeline.generate(data, spec, manager, tmp_path)

    result = pipeline.validate(spec, manager, tmp_path)
    failures = [check for report in result.reports for check in report.failures()]
    assert not failures, (
        f"failing validators: {', '.join(c.label for c in failures)}\n"
        + "\n".join(c.detail for c in failures)[:2000]
    )

    launched = [c.label for report in result.reports for c in report.checks]
    assert len(launched) == 9, f"9 commands expected, {len(launched)} launched: {launched}"
    assert not [issue for issue in result.issues if issue.level == "error"]
