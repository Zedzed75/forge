"""The monitoring domain — the domain whose defects are silent.

An alerting rule can be syntactically flawless and never fire: a metric name
that does not exist, a misspelt label, a comparison on the wrong side of the
threshold. Nothing fails, nothing breaks, and nobody is told on the day they
should have been.

Hence the shape of this module: beyond the usual checks, it verifies the
**consistency between a rule and its unit test**, and lets `promtool test rules`
settle it for good under the `integration` marker.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from forge import pipeline
from forge.plugins.monitoring import answers, derive, render, tree, validators
from forge.plugins.monitoring.catalog.families import FAMILIES
from forge.plugins.monitoring.catalog.registry import all_alerts, family_names
from forge.plugins.monitoring.enums import RuleFamily
from forge.plugins.monitoring.spec import MonitoringSpec, ThresholdsSpec
from forge.plugins_api.manager import ForgeManager
from forge.spec.assembly import validate_spec
from forge.spec.io import load_spec_data
from tests.conftest import SPECS_DIR

PLUGIN = "forge.plugins.monitoring.plugin"
COMPLETE_SPEC = SPECS_DIR / "monitoring-full.yml"


def _manager() -> ForgeManager:
    instance = ForgeManager()
    instance.register_module(PLUGIN)
    return instance


def _spec(given: dict | None = None):
    manager = _manager()
    data = given if given is not None else load_spec_data(COMPLETE_SPEC)
    return data, validate_spec(data, manager), manager


def _base(**monitoring) -> dict:
    """Minimal specification, with the monitoring section supplied."""
    return {
        "forge_version": 1,
        "service": {
            "name": "boutique",
            "description": "Boutique en ligne",
            "owner": "Equipe",
            "environments": [{"name": "dev"}, {"name": "prod", "production": True}],
        },
        "monitoring": monitoring or {"rules": ["availability"]},
    }


def _generate(tmp_path: Path, given: dict | None = None):
    data, spec, manager = _spec(given)
    pipeline.generate(data, spec, manager, tmp_path)
    return spec, manager


def _issues(given: dict, level: str) -> list[str]:
    spec = validate_spec(given, _manager())
    return [issue.message for issue in answers.cross_check(spec) if issue.level == level]


# ---------------------------------------------------------------------------
# What the sub-model refuses
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("duration", ["30", "5 m", "abc", ""])
def test_a_malformed_duration_is_refused(duration):
    with pytest.raises(ValueError):
        MonitoringSpec(scrape={"interval": duration})


def test_a_timeout_greater_than_the_interval_is_refused():
    """Otherwise the scrapes overlap, and the collector falls behind."""
    with pytest.raises(ValueError, match="scrapes would overlap"):
        MonitoringSpec(scrape={"interval": "10s", "timeout": "30s"})


@pytest.mark.parametrize("name", ["1metrique", "metrique-tiret", "métrique"])
def test_an_invalid_metric_name_is_refused(name):
    with pytest.raises(ValueError):
        MonitoringSpec(metrics={"requests_total": name})


@pytest.mark.parametrize("target", ["api.example.net", "api.example.net:", ":9090", "http://x:1"])
def test_a_malformed_target_is_refused(target):
    with pytest.raises(ValueError):
        MonitoringSpec(environments={"dev": {"targets": [target]}})


def test_a_probe_url_without_a_scheme_is_refused():
    with pytest.raises(ValueError):
        MonitoringSpec(environments={"dev": {"probe_urls": ["boutique.example.net"]}})


def test_a_repeated_family_is_refused():
    with pytest.raises(ValueError, match="rule families"):
        MonitoringSpec(rules=["availability", "availability"])


def test_a_threshold_out_of_bounds_is_refused():
    """An error rate of 1 would alert on a perfectly healthy service."""
    with pytest.raises(ValueError):
        ThresholdsSpec(error_rate=1.0)


def test_an_unknown_key_is_refused():
    with pytest.raises(ValueError):
        MonitoringSpec(blackbox_adress="x:9115")


# ---------------------------------------------------------------------------
# What the cross-check reports
# ---------------------------------------------------------------------------


def test_an_unknown_environment_is_an_error():
    given = _base(rules=["availability"], environments={"recette": {"targets": ["a:1"]}})
    assert any("recette" in message for message in _issues(given, "error"))


def test_an_environment_without_a_target_is_reported():
    """The gravest defect of the domain, and the most silent."""
    given = _base(rules=["availability"])
    warnings = _issues(given, "warning")
    assert any("no scrape target" in message and "'dev'" in message for message in warnings)
    assert any("no alert will be able to fire" in message for message in warnings)


def test_the_probe_family_without_a_probed_url_is_reported():
    given = _base(
        rules=["probe"],
        environments={"dev": {"targets": ["a:1"]}, "prod": {"targets": ["b:1"]}},
    )
    warnings = _issues(given, "warning")
    assert any("will never fire" in message for message in warnings)


def test_a_probed_url_in_clear_text_is_reported():
    """`probe_ssl_earliest_cert_expiry` does not exist for an http:// probe."""
    given = _base(
        rules=["probe"],
        environments={
            "dev": {"targets": ["a:1"], "probe_urls": ["http://boutique.example.net"]},
            "prod": {"targets": ["b:1"], "probe_urls": ["https://boutique.example.net"]},
        },
    )
    warnings = _issues(given, "warning")
    assert any("probe_ssl_earliest_cert_expiry" in message for message in warnings)


def test_a_missing_namespace_is_reported_when_a_family_depends_on_it():
    given = _base(
        rules=["saturation"],
        environments={"dev": {"targets": ["a:1"]}, "prod": {"targets": ["b:1"]}},
    )
    assert any("namespace" in message for message in _issues(given, "warning"))


def test_a_missing_namespace_says_nothing_when_no_family_depends_on_it():
    given = _base(
        rules=["availability"],
        environments={"dev": {"targets": ["a:1"]}, "prod": {"targets": ["b:1"]}},
    )
    assert not any("namespace" in message for message in _issues(given, "warning"))


def test_a_threshold_without_its_family_is_reported():
    """A carefully chosen value silently ignored is worse than an error."""
    given = _base(
        rules=["availability"],
        environments={
            "dev": {"targets": ["a:1"]},
            "prod": {"targets": ["b:1"], "thresholds": {"error_rate": 0.1}},
        },
    )
    warnings = _issues(given, "warning")
    assert any("thresholds.error_rate" in message for message in warnings)
    assert any("will not be applied" in message for message in warnings)


def test_the_reference_specification_raises_no_error():
    _, spec, _ = _spec()
    assert [issue for issue in answers.cross_check(spec) if issue.level == "error"] == []


def test_the_cross_check_is_silent_without_a_monitoring_section():
    class Without:
        pass

    assert answers.cross_check(Without()) == []


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------


def test_the_projection_is_serialisable_and_deterministic():
    _, spec, _ = _spec()
    assert json.dumps(answers.build(spec), sort_keys=True) == json.dumps(
        answers.build(spec), sort_keys=True
    )


#: Names a projection key cannot carry: in Jinja, `object.values` resolves the
#: dict method before the key, and the template then writes
#: `<built-in method values...>` into the generated file. promtool complains
#: about it, but very far from the cause. That happened once; this test forbids
#: it.
RESERVED_NAMES = frozenset(name for name in dir(dict) if not name.startswith("_"))


def _keys(value, path=""):
    if isinstance(value, dict):
        for key, sub in value.items():
            yield path, key
            yield from _keys(sub, f"{path}.{key}")
    elif isinstance(value, list):
        for element in value:
            yield from _keys(element, path)


def test_no_projection_key_shadows_a_dict_method():
    _, spec, _ = _spec()
    offenders = [
        f"{path}.{key}" for path, key in _keys(answers.build(spec)) if key in RESERVED_NAMES
    ]
    assert offenders == [], f"keys shadowing a dict method: {sorted(set(offenders))}"


def test_the_thresholds_really_differ_from_one_environment_to_the_next():
    """Without this, a per-environment configuration would be pointless."""
    _, spec, _ = _spec()
    environments = {env["name"]: env for env in derive.environments(spec)}
    assert (
        environments["dev"]["thresholds"]["error_rate"]
        != environments["prod"]["thresholds"]["error_rate"]
    )


def test_the_declared_facet_belongs_to_the_shared_vocabulary():
    from forge.plugins.monitoring import plugin as monitoring_plugin
    from forge.validate.consistency import FACET_VOCABULARY

    _, spec, _ = _spec()
    projection = monitoring_plugin.forge_projection(spec)
    assert set(projection.facets) <= set(FACET_VOCABULARY)
    assert projection.facets["ingress_hosts"] == (
        "boutique.dev.example.net",
        "boutique.example.net",
    )


def test_an_environment_without_a_target_is_not_declared_materialised():
    """Claiming to watch what is not collected would be worse than saying nothing."""
    from forge.plugins.monitoring import plugin as monitoring_plugin

    given = _base(rules=["availability"], environments={"prod": {"targets": ["a:1"]}})
    spec = validate_spec(given, _manager())
    assert monitoring_plugin.forge_projection(spec).environments == ("prod",)


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


def test_the_announced_tree_matches_the_generated_files(tmp_path):
    """Arbitration R3: `tree.py` stays with the plugin, but a test keeps it current."""
    spec, _ = _generate(tmp_path)
    base = tmp_path / "monitoring"
    produced = {
        path.relative_to(base).as_posix() for path in base.rglob("*") if path.is_file()
    }
    assert produced == set(tree.expected_paths(spec))


def test_every_selected_family_produces_its_rules_per_environment(tmp_path):
    spec, _ = _generate(tmp_path)
    base = tmp_path / "monitoring"
    for env in ("dev", "prod"):
        for family in FAMILIES:
            path = base / tree.rule_file(env, family.name)
            assert path.is_file(), path
            content = path.read_bytes().decode("utf-8")
            assert f"boutique-{env}-{family.name}" in content


def test_a_family_that_was_not_selected_produces_nothing(tmp_path):
    """The choice also applies inside a domain."""
    given = _base(
        rules=["availability"],
        environments={"dev": {"targets": ["a:1"]}, "prod": {"targets": ["b:1"]}},
    )
    _generate(tmp_path, given)
    rules = sorted(path.name for path in (tmp_path / "monitoring" / "rules" / "dev").iterdir())
    assert rules == ["availability.yml"]


def test_the_unit_tests_are_not_optional():
    """Design decision: making them optional invited the wrong choice.

    An untested alerting rule is a rule nobody knows fires. `extras` therefore
    carries no flag to do without them.
    """
    from forge.plugins.monitoring.spec import MonitoringExtras

    assert "rule_tests" not in MonitoringExtras.model_fields


def test_every_selected_family_produces_its_unit_test(tmp_path):
    spec, _ = _generate(tmp_path)
    base = tmp_path / "monitoring"
    for env in ("dev", "prod"):
        for family in FAMILIES:
            assert (base / tree.test_file(env, family.name)).is_file()


def test_the_dashboard_is_valid_json(tmp_path):
    """No offline Grafana linter exists: this guarantee is ours."""
    _generate(tmp_path)
    path = tmp_path / "monitoring" / "grafana" / "dashboards" / "boutique.json"
    dashboard = json.loads(path.read_bytes().decode("utf-8"))

    assert dashboard["title"].startswith("boutique")
    assert dashboard["uid"]
    assert dashboard["schemaVersion"] >= 36
    panels = dashboard["panels"]
    assert len(panels) == len(list(all_alerts()))
    identifiers = [panel["id"] for panel in panels]
    assert len(set(identifiers)) == len(identifiers)
    for panel in panels:
        assert panel["targets"][0]["expr"].strip()
        assert panel["gridPos"]["w"] > 0


def test_the_collector_configuration_names_the_rules_of_its_environment(tmp_path):
    _generate(tmp_path)
    for env in ("dev", "prod"):
        content = (
            (tmp_path / "monitoring" / tree.config_file(env)).read_bytes().decode("utf-8")
        )
        assert f"../../rules/{env}/*.yml" in content


def test_the_blackbox_probe_is_only_configured_when_a_family_requires_it(tmp_path):
    given = _base(
        rules=["availability"],
        environments={"dev": {"targets": ["a:1"]}, "prod": {"targets": ["b:1"]}},
    )
    _generate(tmp_path, given)
    content = (
        (tmp_path / "monitoring" / tree.config_file("dev")).read_bytes().decode("utf-8")
    )
    assert "blackbox" not in content


# ---------------------------------------------------------------------------
# Declared validators
# ---------------------------------------------------------------------------


def test_the_validators_cover_every_environment(tmp_path):
    _, spec, _ = _spec()
    labels = [command.label for command in validators.commands(spec, tmp_path)]
    for env in ("dev", "prod"):
        assert f"promtool check config ({env})" in labels
        assert f"promtool check rules ({env})" in labels
        assert f"promtool test rules ({env})" in labels


def test_the_rule_paths_are_enumerated_and_not_slipped_in_as_a_glob(tmp_path):
    """The commands are run without a shell: a `*` would not be expanded."""
    _, spec, _ = _spec()
    for command in validators.commands(spec, tmp_path):
        assert not any("*" in argument for argument in command.argv)


def test_the_number_of_commands_follows_the_environments(tmp_path):
    """Three commands per environment: config, rules, tests."""
    _, spec, _ = _spec()
    assert len(validators.commands(spec, tmp_path)) == 3 * 2


# ---------------------------------------------------------------------------
# Catalogue and interview
# ---------------------------------------------------------------------------


def test_the_catalogue_exposes_every_family_with_its_thresholds():
    from forge.plugins.monitoring import plugin as monitoring_plugin

    entries = monitoring_plugin.forge_catalog()
    assert [entry.name for entry in entries] == list(family_names())
    latency = next(entry for entry in entries if entry.name == "latency")
    assert "latency_p95_seconds" in latency.options
    assert "histogram_quantile" in latency.details


def test_the_interview_produces_a_valid_section():
    from forge.plugins.monitoring import interview
    from tests.scripted_prompter import ScriptedPrompter

    service = validate_spec(_base(rules=["availability"]), _manager()).service
    prompter = ScriptedPrompter(
        [
            ["availability", "error_rate"],   # families
            "http_requests_total",            # request counter
            "status",                         # status label
            "api-dev.example.net:9090",       # dev targets
            "api.example.net:9090",           # prod targets
            True,                             # dashboard
            True,                             # makefile
        ]
    )
    section = interview.run(prompter, service)
    assert prompter.exhausted, f"answers not consumed: {prompter.answers}"
    model = MonitoringSpec.model_validate(section)
    assert model.family_names() == ("availability", "error_rate")
    assert model.overrides("prod").targets == ["api.example.net:9090"]


def test_the_interview_declines_when_no_family_is_selected():
    """Arbitration R7: `None` means "nothing to generate"."""
    from forge.plugins.monitoring import interview
    from tests.scripted_prompter import ScriptedPrompter

    service = validate_spec(_base(rules=["availability"]), _manager()).service
    assert interview.run(ScriptedPrompter([[]]), service) is None


# ---------------------------------------------------------------------------
# Real validation of the generated project
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_the_generated_project_passes_its_own_validators(tmp_path):
    """Hard rule from CLAUDE.md, on the case enabling the six families.

    `promtool test rules` is the only validator of the project that checks
    something **semantic**: that the alerts really fire.
    """
    from tests.conftest import require_tools

    require_tools("monitoring", "promtool")

    spec, manager = _generate(tmp_path)
    result = pipeline.validate(spec, manager, tmp_path)
    failures = [check for report in result.reports for check in report.failures()]
    assert not failures, (
        f"failing validators: {', '.join(c.label for c in failures)}\n"
        + "\n".join(c.detail for c in failures)[:2000]
    )
    launched = [c.label for report in result.reports for c in report.checks]
    assert any("test rules" in label for label in launched)
