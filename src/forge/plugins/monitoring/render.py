"""Resolution of the catalogue tokens, and projection of an alert.

Two substitutions, and the second one is the interesting part:

1. the `@…@` tokens of the catalogue become the values of the specification;
2. the `{{ $labels.<name> }}` references of an annotation are resolved with the
   labels of the unit test, so as to produce the annotation **as promtool will
   see it**.

The second one avoids the only dangerous duplication of this domain. `promtool
test rules` compares the rendered annotations character by character: writing by
hand, in the test file, what the annotation is supposed to give would make the
rule and its test diverge at the first change of wording — and a test that checks
an old wording no longer checks anything.
"""

from __future__ import annotations

from typing import Any

from forge.plugins.monitoring.catalog.alerts import Alert


def substitute(text: str, values: dict[str, Any]) -> str:
    """Replace the `@key@` tokens of `text` with the supplied values.

    Neither `str.format` nor `string.Template` fits: PromQL is full of braces
    (`{job="x"}`) and the annotations are full of `$` (`{{ $labels.pod }}`).
    """
    for key, value in values.items():
        text = text.replace(f"@{key}@", format_number(value))
    return text


def format_number(value: Any) -> str:
    """Render a number **identically** in the expression and in the text.

    `1.0` is written `1`, `0.05` is written `0.05`. Without this normalisation, a
    PromQL expression would say `> 1.0` and the annotation "exceeds 1 second",
    which is enough to make the unit test wrong.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return str(value)
    if float(value).is_integer():
        return str(int(value))
    return repr(round(float(value), 10))


def percent(value: float) -> str:
    """Render a proportion as a percentage, without floating-point artefacts."""
    return format_number(round(value * 100, 6))


def render_description(description: str, labels: dict[str, str]) -> str:
    """Resolve `{{ $labels.<name> }}` with the given labels.

    A missing label is left as it is: the unit test will then fail while showing
    the unresolved reference, which is exactly the diagnosis wanted — the alert
    quotes a label its expression does not produce.
    """
    rendered = description
    for name, value in labels.items():
        rendered = rendered.replace("{{ $labels." + name + " }}", value)
    return rendered


def project(
    alert: Alert,
    values: dict[str, Any],
    *,
    rule_labels: dict[str, str],
) -> dict[str, Any]:
    """Project a catalogue alert into a JSON-serialisable dict.

    The dict carries the rule **and** its unit test: both are built from the same
    values, in the same function, which stops them from diverging.
    """
    resolved = dict(values)
    if alert.threshold_field:
        threshold = resolved.get(alert.threshold_field, alert.threshold_default)
        resolved["threshold"] = threshold
        resolved["threshold_pct"] = percent(float(threshold))

    summary = substitute(alert.summary, resolved)
    description = substitute(alert.description, resolved)
    result_labels = {
        name: substitute(value, resolved)
        for name, value in alert.test_result_labels.items()
    }

    return {
        # The catalogue name, as-is. The service is not prefixed onto it: it is
        # carried by the `service` label that `derive` puts on every rule, and
        # that label is the one Alertmanager is built to filter on. A generic
        # alert name is also what lets a community runbook or dashboard, indexed
        # on `TargetDown`, apply to this service.
        "name": alert.name,
        "expr": substitute(alert.expr, resolved),
        "for": alert.for_duration,
        "severity": alert.severity.value,
        "summary": summary,
        "description": description,
        "labels": dict(rule_labels),
        "threshold_field": alert.threshold_field or "",
        "threshold": format_number(resolved.get("threshold", "")) if alert.threshold_field else "",
        "threshold_unit": alert.threshold_unit,
        "test": {
            "series": [
                {
                    "series": substitute(series, resolved),
                    # Definitely not `values`: in Jinja, `series.values` would
                    # resolve the dict method before the key, and the template
                    # would write `<built-in method values...>` into the test
                    # file. promtool complains about it, but a very long way from
                    # the cause.
                    # The points carry tokens too: the step of a counter is
                    # computed from the threshold.
                    "points": substitute(points, resolved),
                }
                for series, points in alert.test_series
            ],
            "eval_time": alert.test_eval_time,
            # What promtool must find again: the labels the rule adds, plus the
            # ones the expression lets survive.
            "exp_labels": {**rule_labels, **result_labels},
            "exp_annotations": {
                "summary": summary,
                "description": render_description(description, result_labels),
            },
        },
    }
