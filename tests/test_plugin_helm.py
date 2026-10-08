"""Tests of the Helm plugin: model, cross-checks, validators, catalogue.

Parity with the original generator served throughout the port, then was removed
in phase 10 along with `_legacy/`. It had already stopped covering the essential:
the nine resource families created in phase 4 did not exist in the original tool,
and it is `tests/golden/helm-complet/` and the real validators that hold them.

This module covers what neither of them says: the refusals, the normalisations
forced upon the model, and the guards only the model or the cross-check can
carry.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from forge import pipeline
from forge.errors import SpecValidationError
from forge.plugins.helm import answers as answers_module
from forge.plugins.helm import validators
from forge.plugins.helm.catalog.registry import all_families, family_names, get_family
from forge.plugins.helm.components import ComponentSpec
from forge.plugins_api.manager import ForgeManager
from forge.spec.assembly import validate_spec
from forge.spec.io import load_spec_data
from tests.conftest import REPO_ROOT

HELM_PLUGIN = "forge.plugins.helm.plugin"

#: Golden specification exercising the thirteen families.
COMPLETE_SPEC = REPO_ROOT / "tests" / "specs" / "helm-complet.yml"


def _manager() -> ForgeManager:
    instance = ForgeManager()
    instance.register_module(HELM_PLUGIN)
    return instance


def _spec_data(**overrides) -> dict:
    """Minimal valid Helm specification."""
    data = {
        "forge_version": 1,
        "service": {
            "name": "boutique",
            "description": "Boutique en ligne",
            "owner": "Equipe Plateforme",
            "environments": [{"name": "prod", "production": True}],
        },
        "helm": {"components": [{"name": "api", "addons": ["service"]}]},
    }
    for path, value in overrides.items():
        target = data
        *parents, leaf = path.split(".")
        for parent in parents:
            target = target[parent]
        target[leaf] = value
    return data


# ---------------------------------------------------------------------------
# Normalisations forced by Kubernetes
# ---------------------------------------------------------------------------


def test_a_statefulset_always_gets_its_headless_service():
    """Without the addon, `serviceName` would designate a resource that does not exist.

    Forcing `headless` is not enough: the Service would not be generated at all,
    and the StatefulSet would lose the stable network identity that is its whole
    point. No validator can see it, the manifest remaining valid.
    """
    component = ComponentSpec(name="store", kind="statefulset", addons=["configmap"])
    assert [addon.value for addon in component.addons] == ["service", "configmap"]
    assert component.service.headless is True
    assert component.persistence.enabled is True


def test_a_deployment_does_not_get_a_forced_service():
    component = ComponentSpec(name="api", kind="deployment", addons=["configmap"])
    assert [addon.value for addon in component.addons] == ["configmap"]


def test_a_port_name_that_is_too_long_is_refused():
    """Kubernetes imposes the IANA_SVC_NAME format: at most 15 characters.

    No external validator catches it — a 29-character name passes `helm lint`,
    `helm template` and `kubeconform -strict`, and is only refused on apply.
    """
    with pytest.raises(Exception, match="IANA_SVC_NAME|Invalid port name"):
        ComponentSpec(name="api", port_name="un-nom-de-port-beaucoup-trop-long")


@pytest.mark.parametrize("name", ["-http", "http-", "http--2", "80"])
def test_malformed_port_names_are_refused(name):
    with pytest.raises(Exception):
        ComponentSpec(name="api", port_name=name)


def test_the_addons_are_put_back_in_canonical_order():
    """The file plan becomes independent of the order they were typed in."""
    component = ComponentSpec(name="api", addons=["hpa", "service", "configmap"])
    assert [addon.value for addon in component.addons] == ["service", "configmap", "hpa"]


def test_an_ingress_without_a_service_is_refused():
    with pytest.raises(Exception, match="service"):
        ComponentSpec(name="api", addons=["ingress"])


# ---------------------------------------------------------------------------
# RBAC: declarable from forge.yml, not only in values.yaml
# ---------------------------------------------------------------------------


def test_the_rbac_rules_come_from_the_specification():
    """Without this they would be hardcoded into values.yaml and lost at every
    regeneration."""
    component = ComponentSpec(
        name="api",
        addons=["service", "serviceaccount"],
        rbac={
            "create": True,
            "rules": [
                {"apiGroups": [""], "resources": ["configmaps"], "verbs": ["get", "list"]}
            ],
        },
    )
    assert component.rbac.create is True
    assert component.rbac.rules[0]["resources"] == ["configmaps"]


def test_an_incomplete_rbac_rule_is_refused():
    """The API refuses a rule without verbs; kubeconform lets it through."""
    with pytest.raises(Exception, match="incomplete|verbs"):
        ComponentSpec(
            name="api",
            rbac={"create": True, "rules": [{"apiGroups": [""], "resources": ["pods"]}]},
        )


# ---------------------------------------------------------------------------
# Cross-checks — what the sub-model cannot see
# ---------------------------------------------------------------------------


def test_an_unknown_environment_in_helm_environments_is_reported():
    data = _spec_data()
    data["helm"]["environments"] = {"recette": {"log_level": "debug"}}
    spec = validate_spec(data, _manager())
    issues = answers_module.cross_check(spec)
    assert any("recette" in issue.message for issue in issues)
    assert all(issue.hint for issue in issues if issue.level == "error")


def test_a_sound_specification_produces_no_error():
    spec = validate_spec(_spec_data(), _manager())
    assert [i for i in answers_module.cross_check(spec) if i.level == "error"] == []


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def test_three_commands_per_environment_and_the_render_chaining():
    """`kubeconform` reads the output of `helm template`: that is a `stdin_from`."""
    data = _spec_data()
    data["service"]["environments"] = [{"name": "dev"}, {"name": "prod", "production": True}]
    spec = validate_spec(data, _manager())
    commands = validators.commands(spec, Path("helm"))

    assert [c.label for c in commands] == [
        "helm lint (dev)",
        "helm template (dev)",
        "kubeconform -strict (dev)",
        "helm lint (prod)",
        "helm template (prod)",
        "kubeconform -strict (prod)",
    ]
    conform = commands[2]
    assert conform.stdin_from == "helm template (dev)"
    assert "-strict" in conform.argv
    assert all(c.requires_linux for c in commands)


def test_the_render_is_asked_for_in_the_derived_namespace():
    spec = validate_spec(_spec_data(), _manager())
    template = validators.commands(spec, Path("helm"))[1]
    index = template.argv.index("--namespace")
    assert template.argv[index + 1] == "boutique-prod"


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------


def test_the_catalogue_covers_the_requested_families():
    """PLAN.md sets the list expected at the end of phase 4."""
    expected = {
        "deployment", "service", "ingress", "configmap", "statefulset",
        "cronjob", "secret", "hpa", "pdb", "serviceaccount", "rbac",
        "networkpolicy",
    }
    assert expected <= set(family_names())


def test_every_family_documents_its_traps():
    """The traps explain chart choices that would otherwise look arbitrary."""
    without_traps = [f.name for f in all_families() if not f.traps]
    assert not without_traps, f"families with no point of vigilance: {without_traps}"


def test_no_removed_api_version_is_used():
    """A removed apiVersion makes the chart uninstallable on a recent cluster."""
    removed = (
        "extensions/v1beta1",
        "networking.k8s.io/v1beta1",
        "autoscaling/v2beta1",
        "autoscaling/v2beta2",
        "policy/v1beta1",
        "batch/v1beta1",
    )
    for family in all_families():
        assert family.api_version not in removed, (
            f"{family.name} uses {family.api_version}, removed from Kubernetes"
        )


def test_the_catalogue_is_exposed_by_the_hook():
    entries = _manager().domain("helm").catalog()
    assert [e.name for e in entries] == family_names()
    ingress = next(e for e in entries if e.name == "ingress")
    assert "pathType" in ingress.details
    assert "ingress.className" in ingress.options


# ---------------------------------------------------------------------------
# Full render
# ---------------------------------------------------------------------------


def test_the_thirteen_families_produce_their_resources(tmp_path):
    """Render of the golden case: every enabled family must emit a file."""
    manager = _manager()
    data = load_spec_data(COMPLETE_SPEC)
    pipeline.generate(data, validate_spec(data, manager), manager, tmp_path)

    templates = tmp_path / "helm" / "charts" / "boutique" / "templates"
    produced = {path.name for path in templates.glob("*.yaml")}
    for expected in (
        "deployment-api.yaml",
        "statefulset-db-proxy.yaml",
        "cronjob-cleanup.yaml",
        "service-api.yaml",
        "service-db-proxy.yaml",
        "ingress-api.yaml",
        "configmap-api.yaml",
        "secret-api.yaml",
        "hpa-api.yaml",
        "pdb-api.yaml",
        "serviceaccount-api.yaml",
        "rbac-api.yaml",
        "networkpolicy-api.yaml",
    ):
        assert expected in produced, f"{expected} was not generated"


def test_a_component_name_with_a_hyphen_goes_through_values_ref(tmp_path):
    """`.Values.db-proxy` would break the chart; `(index .Values "db-proxy")` does not."""
    manager = _manager()
    data = load_spec_data(COMPLETE_SPEC)
    pipeline.generate(data, validate_spec(data, manager), manager, tmp_path)

    rendered = (
        tmp_path / "helm" / "charts" / "boutique" / "templates" / "statefulset-db-proxy.yaml"
    ).read_text(encoding="utf-8")
    assert '(index .Values "db-proxy")' in rendered
    assert ".Values.db-proxy" not in rendered


def test_the_free_environment_values_are_rendered(tmp_path):
    """The original generator silently lost them."""
    manager = _manager()
    data = load_spec_data(COMPLETE_SPEC)
    pipeline.generate(data, validate_spec(data, manager), manager, tmp_path)

    values = (
        tmp_path / "helm" / "charts" / "boutique" / "values-prod.yaml"
    ).read_text(encoding="utf-8")
    assert "monitoring" in values


# ---------------------------------------------------------------------------
# Real validation of the generated chart
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_the_generated_chart_passes_its_own_validators(tmp_path):
    """Hard rule from CLAUDE.md, on the case enabling the thirteen families.

    `helm lint`, `helm template` on each environment, then `kubeconform -strict`
    on the output — natively, or through the WSL bridge.
    """
    from tests.conftest import require_tools

    require_tools("helm", "helm", "kubeconform")

    manager = _manager()
    data = load_spec_data(COMPLETE_SPEC)
    spec = validate_spec(data, manager)
    pipeline.generate(data, spec, manager, tmp_path)

    result = pipeline.validate(spec, manager, tmp_path)
    failures = [check for report in result.reports for check in report.failures()]
    assert not failures, (
        f"failing validators: {', '.join(c.label for c in failures)}\n"
        + "\n".join(c.detail for c in failures)[:2000]
    )
    # The chaining must really have run, not have been skipped.
    launched = [c.label for report in result.reports for c in report.checks]
    assert any("kubeconform" in label for label in launched)


def test_the_announced_tree_matches_the_generated_files(tmp_path):
    """Arbitration R3: `tree.py` stays with the plugin, but a test keeps it current.

    copier cannot say in advance what it will write, and the chart README
    displays it. A template added, removed or renamed without updating `tree.py`
    would therefore make the README wrong — silently, without this test.
    """
    from forge.plugins.helm import tree

    manager = _manager()
    data = load_spec_data(COMPLETE_SPEC)
    spec = validate_spec(data, manager)
    pipeline.generate(data, spec, manager, tmp_path)

    base = tmp_path / "helm"
    produced = {
        path.relative_to(base).as_posix()
        for path in base.rglob("*")
        if path.is_file()
    }
    announced = set(tree.expected_paths(spec))
    # Accepted differences: copier's plumbing is not announced, and forge.yml now
    # lives at the root of the target repository (parity difference 3).
    assert produced - announced <= {".copier-answers.yml"}
    assert announced - produced <= {"forge.yml"}


def test_helm_is_always_called_with_the_targeted_kubernetes_version(tmp_path):
    """Without `--kube-version`, helm evaluates the chart against its binary's default.

    That default changes with every helm version: a chart declaring
    `kubeVersion: >=1.34.0-0` passed on a machine whose helm was recent and
    failed in CI, where it was pinned. Worse than the failure itself:
    `.Capabilities.KubeVersion` was filled with a version that is not the one the
    specification targets.

    Found by the very first real CI run.
    """
    from forge.plugins.helm import validators

    manager = _manager()
    data = load_spec_data(COMPLETE_SPEC)
    spec = validate_spec(data, manager)
    expected = spec.helm.kubernetes.full_version

    concerned = [
        command
        for command in validators.commands(spec, tmp_path)
        if command.tool == "helm"
    ]
    assert concerned, "the domain must declare helm commands"
    for command in concerned:
        assert "--kube-version" in command.argv, command.label
        position = command.argv.index("--kube-version")
        assert command.argv[position + 1] == expected, command.label
