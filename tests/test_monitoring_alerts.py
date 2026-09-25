"""Consistency of the alert catalogue, and of each alert with its test.

Kept apart from `test_plugin_monitoring.py` to stay under the 600-line limit,
and because these checks are about something else: not about what the domain
produces, but about the **internal soundness of the catalogue** — that no alert
names a threshold the model does not declare, that none ships without a test,
and that no test checks a wording the rule no longer uses.

That last point is the one that matters most: `promtool test rules` compares the
annotations character by character. A test checking an old wording would go green
without proving anything any more.
"""

from __future__ import annotations

import re

import pytest

from forge.plugins.monitoring import derive, render
from forge.plugins.monitoring.catalog.families import FAMILIES
from forge.plugins.monitoring.catalog.registry import all_alerts, family_names
from forge.plugins.monitoring.enums import RuleFamily
from forge.plugins.monitoring.spec import ThresholdsSpec, _seconds
from tests.test_plugin_monitoring import _spec


# ---------------------------------------------------------------------------
# Internal consistency of the catalogue
# ---------------------------------------------------------------------------


def test_every_family_of_the_enumeration_is_in_the_catalogue():
    assert set(family_names()) == {family.value for family in RuleFamily}


def test_every_family_documents_its_traps():
    silent = [family.name for family in FAMILIES if not family.traps]
    assert silent == [], f"families with no documented trap: {silent}"


def test_every_threshold_of_the_catalogue_exists_in_the_model():
    """A threshold `ThresholdsSpec` does not declare would be unreachable."""
    fields = set(ThresholdsSpec.model_fields)
    named = {alert.threshold_field for alert in all_alerts() if alert.threshold_field}
    assert named <= fields, f"thresholds with no model field: {sorted(named - fields)}"


def test_every_threshold_of_the_model_is_used_by_an_alert():
    """A field nobody uses is a setting with no effect."""
    fields = set(ThresholdsSpec.model_fields)
    named = {alert.threshold_field for alert in all_alerts() if alert.threshold_field}
    assert fields <= named, f"unused thresholds: {sorted(fields - named)}"


def test_every_alert_carries_a_unit_test():
    bare = [alert.name for alert in all_alerts() if not alert.test_series]
    assert bare == [], f"alerts with no test series: {bare}"


def test_the_evaluation_instant_is_past_the_for_clause():
    """Otherwise the alert would still be pending and the test would check nothing."""
    too_early = [
        alert.name
        for alert in all_alerts()
        if _seconds(alert.test_eval_time) <= _seconds(alert.for_duration)
    ]
    assert too_early == [], f"evaluation instants too early: {too_early}"


def test_the_alerts_have_distinct_names():
    names = [alert.name for alert in all_alerts()]
    assert len(set(names)) == len(names)


# ---------------------------------------------------------------------------
# Consistency between a rule and its test
# ---------------------------------------------------------------------------


def test_the_expected_annotation_is_the_one_of_the_resolved_rule():
    """They are computed together: they cannot diverge.

    This is the lock against the only dangerous duplication in the domain — a
    test checking an old wording would no longer check anything.
    """
    _, spec, _ = _spec()
    for env in derive.environments(spec):
        for group in env["rules"].values():
            for alert in group["alerts"]:
                expected = alert["test"]["exp_annotations"]["description"]
                rendered = render.render_description(
                    alert["description"], alert["test"]["exp_labels"]
                )
                assert expected == rendered, alert["name"]


def test_no_label_reference_is_left_unresolved():
    """An unresolved reference reports an alert naming a label that is absent."""
    _, spec, _ = _spec()
    for env in derive.environments(spec):
        for group in env["rules"].values():
            for alert in group["alerts"]:
                assert "$labels" not in alert["test"]["exp_annotations"]["description"], (
                    alert["name"]
                )


def test_no_catalogue_token_survives_the_projection():
    """A forgotten `@token@` produces a file promtool refuses — very far from here."""
    _, spec, _ = _spec()
    leftover = re.compile(r"@[a-z_]+@")
    for env in derive.environments(spec):
        for group in env["rules"].values():
            for alert in group["alerts"]:
                for key in ("expr", "summary", "description", "panel_expr"):
                    assert not leftover.search(alert[key]), f"{alert['name']} / {key}"
                for series in alert["test"]["series"]:
                    assert not leftover.search(series["series"]), alert["name"]
                    assert not leftover.search(series["points"]), alert["name"]


def test_the_test_series_follow_the_thresholds():
    """A frozen series would only prove the rule for a single threshold.

    That is the defect `promtool test rules` found: a test quantile at 1.9 s
    validated a 1 s threshold and failed on a 2 s one.
    """
    loose = derive._test_tokens({"cpu_cores": 1.0, "latency_p95_seconds": 1.0})
    tight = derive._test_tokens({"cpu_cores": 4.0, "latency_p95_seconds": 3.0})
    assert tight["cpu_step"] > loose["cpu_step"]
    assert tight["latency_high_le"] > loose["latency_high_le"]


def test_the_default_thresholds_come_from_the_catalogue():
    """Copying them somewhere else would make them diverge at the first change."""
    defaults = derive.default_thresholds()
    expected = {
        alert.threshold_field: alert.threshold_default
        for alert in all_alerts()
        if alert.threshold_field
    }
    assert defaults == expected


def test_a_number_renders_the_same_in_the_expression_and_in_the_text():
    """`> 1.0` in the rule and "exceeds 1 second" in the text would be enough to
    make the unit test wrong."""
    assert render.format_number(1.0) == "1"
    assert render.format_number(0.05) == "0.05"
    assert render.percent(0.05) == "5"
    assert render.percent(0.855) == "85.5"


@pytest.mark.parametrize(
    ("service", "expected"),
    [("boutique", "Boutique"), ("db-proxy", "DbProxy"), ("mon_service", "MonService")],
)
def test_the_alert_prefix_is_a_camel_identifier(service, expected):
    assert render.alert_prefix(service) == expected
