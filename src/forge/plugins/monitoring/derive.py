"""Projection of the specification into what the templates consume.

The interesting part is `environments()`: **the rules are projected per
environment**, because their thresholds and their namespace are. A rule shared
between development and production would have to carry wide filters and average
thresholds, that is to say serve neither of the two well.
"""

from __future__ import annotations

from typing import Any

from forge.plugins.monitoring import render
from forge.plugins.monitoring.catalog.alerts import PANEL_EXPRESSIONS
from forge.plugins.monitoring.catalog.registry import all_alerts, selected
from forge.plugins.monitoring.constants import (
    BLACKBOX_JOB,
    BLACKBOX_MODULE,
    TEST_CONTAINER,
    TEST_INSTANCE,
    TEST_POD,
    TEST_PROBE_URL,
)


def scrape(spec: Any) -> dict[str, Any]:
    """Scrape settings."""
    settings = spec.monitoring.scrape
    return {
        "interval": settings.interval,
        "timeout": settings.timeout,
        "metrics_path": settings.metrics_path,
    }


def metrics(spec: Any) -> dict[str, str]:
    """Names of the metrics the application exposes."""
    names = spec.monitoring.metrics
    return {
        "requests_total": names.requests_total,
        "request_duration_seconds": names.request_duration_seconds,
        "status_label": names.status_label,
    }


def blackbox(spec: Any) -> dict[str, Any]:
    """External probe: job, module and address of the exporter."""
    return {
        "needed": spec.monitoring.needs_blackbox(),
        "job": BLACKBOX_JOB,
        "module": BLACKBOX_MODULE,
        "address": spec.monitoring.blackbox_address,
    }


def extras(spec: Any) -> dict[str, bool]:
    """Extra files requested."""
    requested = spec.monitoring.extras
    return {
        "makefile": requested.makefile,
        "dashboard": requested.dashboard,
    }


def families(spec: Any) -> list[dict[str, Any]]:
    """Retained families, with what the README and the files must say about them."""
    return [
        {
            "name": family.name,
            "summary": family.summary,
            "details": family.details,
            "exporters": list(family.exporters),
            "traps": list(family.traps),
            "alert_names": [alert.name for alert in family.alerts],
            "needs_namespace": family.needs_namespace,
            "needs_probe": family.needs_probe,
        }
        for family in selected(spec.monitoring.family_names())
    ]


def default_thresholds() -> dict[str, Any]:
    """Default thresholds, read from the catalogue rather than copied here."""
    return {
        alert.threshold_field: alert.threshold_default
        for alert in all_alerts()
        if alert.threshold_field
    }


def environments(spec: Any) -> list[dict[str, Any]]:
    """One entry per `service.environments` environment, in order."""
    return [_environment(spec, env) for env in spec.service.environments]


def _environment(spec: Any, env: Any) -> dict[str, Any]:
    """Projection of an environment: what is watched there, under which thresholds."""
    monitoring = spec.monitoring
    override = monitoring.overrides(env.name)
    namespace = override.namespace or spec.service.name
    thresholds = {**default_thresholds(), **_declared(override)}

    values: dict[str, Any] = {
        "job": spec.service.name,
        "service": spec.service.name,
        "env": env.name,
        "namespace": namespace,
        "requests": monitoring.metrics.requests_total,
        "duration": monitoring.metrics.request_duration_seconds,
        "status": monitoring.metrics.status_label,
        "blackbox_job": BLACKBOX_JOB,
        # Test values: they need to exist nowhere, promtool builds the series
        # itself.
        "instance": TEST_INSTANCE,
        "pod": TEST_POD,
        "container": TEST_CONTAINER,
        "probe_url": TEST_PROBE_URL,
        **thresholds,
        **_test_tokens(thresholds),
    }

    rules: dict[str, Any] = {}
    for family in selected(monitoring.family_names()):
        alerts = []
        for alert in family.alerts:
            # `service` and `env` are what tell this alert apart from the same
            # alert of another service: the name itself is generic.
            labels = {
                "severity": alert.severity.value,
                "service": spec.service.name,
                "env": env.name,
                **override.labels,
            }
            projected = render.project(alert, values, rule_labels=labels)
            projected["panel_expr"] = render.substitute(
                PANEL_EXPRESSIONS.get(alert.name, alert.expr),
                {**values, "threshold": values.get(alert.threshold_field or "", "")},
            )
            alerts.append(projected)
        rules[family.name] = {
            "group": f"{spec.service.name}-{env.name}-{family.name}",
            "summary": family.summary,
            "traps": list(family.traps),
            "alerts": alerts,
        }

    return {
        "name": env.name,
        "production": env.production,
        "domain": env.domain or "",
        "namespace": namespace,
        "targets": list(override.targets),
        "probe_urls": list(override.probe_urls),
        "labels": {**spec.service.labels, **override.labels},
        "thresholds": {name: render.format_number(value) for name, value in thresholds.items()},
        "rules": rules,
        # Canonical order of the families, so that the templates do not have to
        # rediscover it by walking a dict.
        "family_names": [family.name for family in selected(monitoring.family_names())],
    }


#: Memory limit used by the test series, in bytes. A round and wide value: what
#: matters is the ratio to the consumption, not the scale.
TEST_MEMORY_LIMIT = 1_000_000_000

#: Instant, in seconds, at which the certificate test is evaluated (20 minutes).
#: It has to match the `test_eval_time` of the alert: `time()` is worth that in
#: promtool's synthetic clock, which starts at zero.
CERT_EVAL_SECONDS = 1200


def _test_tokens(thresholds: dict[str, Any]) -> dict[str, Any]:
    """Values of the test series, **derived from the thresholds**.

    A frozen test series only proves the rule for the threshold that was in force
    the day it was written. That is exactly what promtool showed: a test quantile
    at 1.9 s validated a threshold at 1 s and failed on a threshold at 2 s, and a
    CPU consumption of 2 cores validated a threshold at 1.5 and failed on a
    threshold at 3.

    Every value below is therefore computed so as to exceed its threshold
    **whatever it is**, with a clear margin.
    """
    tokens: dict[str, Any] = {"memory_limit": TEST_MEMORY_LIMIT}

    rate = float(thresholds.get("error_rate", 0.05))
    # Targeted ratio: (1 + rate) / 2, therefore strictly between the rate and 1.
    tokens["error_other_step"] = max(1, round(1000 * (1 - rate) / (1 + rate)))

    latency = float(thresholds.get("latency_p95_seconds", 1.0))
    # Upper bound of the second bucket. The 95th percentile falls into it and is
    # worth, by linear interpolation, about 1.94 times the threshold.
    tokens["latency_high_le"] = latency * 2

    ratio = float(thresholds.get("memory_ratio", 0.9))
    tokens["memory_used"] = int(TEST_MEMORY_LIMIT * (1 + ratio) / 2)

    cpu = float(thresholds.get("cpu_cores", 1.5))
    # Step of the counter: the derivative is worth (threshold + 1) cores.
    tokens["cpu_step"] = int(round((cpu + 1) * 60))

    restarts = int(thresholds.get("restarts_per_hour", 3))
    # The increase over one hour is worth about 60 times the step: we target twice
    # the threshold, with a step of at least 1.
    tokens["restart_step"] = max(1, -(-restarts * 2 // 60))

    days = int(thresholds.get("certificate_days", 21))
    # Expiry placed at half the threshold, in the clock of the test.
    tokens["cert_value"] = int(CERT_EVAL_SECONDS + days * 86400 / 2)

    return tokens


def _declared(override: Any) -> dict[str, Any]:
    """Thresholds actually filled in for this environment."""
    return override.thresholds.declared() if override.thresholds else {}


def dashboard_panels(spec: Any) -> list[dict[str, Any]]:
    """Panels of the dashboard, one per alert of the retained families.

    They plot the quantity being watched, not the alerting condition: a curve with
    two values — true or false — does not say whether the threshold is being
    approached.

    The dashboard is generated for the **first** declared environment, by
    convention: a dashboard mixing the environments would conflate quantities
    that do not have the same thresholds.
    """
    first = environments(spec)[0]
    panels: list[dict[str, Any]] = []
    for family_name in first["family_names"]:
        for alert in first["rules"][family_name]["alerts"]:
            panels.append(
                {
                    "title": alert["summary"],
                    "family": family_name,
                    "expr": alert["panel_expr"],
                    "alert": alert["name"],
                    "threshold": alert["threshold"],
                }
            )
    return panels
