"""The alerts themselves: PromQL expression, and what it takes to test them.

Every alert carries **its own unit test**: a synthetic time series, the
evaluation instant, and the expected labels. `promtool test rules` runs one
against the other. An untested alerting rule is a rule nobody knows fires or
not, and that is only learnt the day it should have.

The `@…@` tokens are replaced at projection time (`derive.py`). Neither
`str.format` nor `string.Template` fits here: PromQL is full of braces
(`{job="x"}`) and the annotations are full of `$` (`{{ $labels.pod }}`). A marker
that exists in neither language avoids any escaping rule.

**No invented metric.** `up` comes from Prometheus; `container_*` from cAdvisor;
`kube_pod_container_status_restarts_total` from kube-state-metrics; `probe_*`
from the blackbox exporter. The names specific to the application -- request
counter, duration histogram -- are **configurable**, because they depend on the
client library used and because guessing one would mean generating an alert that
will never fire.

NOTE ON THE ALERT NAMES. The `name` values below are French, and they are
deliberately left as they are: they become the alert names of the generated rules,
which Alertmanager routes, silences and runbooks match on by string. Renaming
them is a breaking change for any existing installation, not a translation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from forge.plugins.monitoring.enums import Severity


@dataclass(frozen=True)
class Alert:
    """An alerting rule, and the unit test that puts it to the test."""

    #: Suffix of the alert name. The full name is `<Service><Suffix>`. Kept in
    #: French on purpose: it is an identifier of the generated output.
    name: str

    #: PromQL expression, `@…@` tokens included.
    expr: str

    #: Duration the condition has to hold for before firing. Without it, any
    #: oscillation becomes an alert.
    for_duration: str

    #: Severity carried by the `severity` label.
    severity: Severity

    #: Short sentence: what is wrong.
    summary: str

    #: Long sentence: where, since when, and under which threshold. May use
    #: `{{ $labels.<name> }}`, which the test resolves mechanically.
    description: str

    #: Field of `ThresholdsSpec` that feeds `@threshold@`, or None.
    threshold_field: str | None = None

    #: Default value of the threshold.
    threshold_default: float | int | None = None

    #: Unit of the threshold, for the texts and the README.
    threshold_unit: str = ""

    #: Input series of the unit test: (series, values), tokens included.
    test_series: tuple[tuple[str, str], ...] = ()

    #: Evaluation instant of the test. Must exceed `for_duration`.
    test_eval_time: str = "10m"

    #: Labels the expression lets survive, as the test expects them. A `sum(...)`
    #: aggregation with no `by` leaves none.
    test_result_labels: dict[str, str] = field(default_factory=dict)

    #: True if the alert needs a Kubernetes namespace.
    needs_namespace: bool = False

    #: True if the alert needs a blackbox probe.
    needs_probe: bool = False


AVAILABILITY_ALERTS: tuple[Alert, ...] = (
    Alert(
        name="TargetDown",
        expr='up{job="@job@"} == 0',
        for_duration="5m",
        severity=Severity.CRITICAL,
        summary="The target no longer answers the collector",
        description=(
            "Instance {{ $labels.instance }} of job {{ $labels.job }} has not "
            "answered for 5 minutes."
        ),
        test_series=(('up{job="@job@", instance="@instance@"}', "0+0x10"),),
        test_eval_time="6m",
        test_result_labels={"job": "@job@", "instance": "@instance@"},
    ),
)

ERROR_RATE_ALERTS: tuple[Alert, ...] = (
    Alert(
        name="HighErrorRate",
        expr=(
            'sum(rate(@requests@{job="@job@", @status@=~"5.."}[5m]))\n'
            "  /\n"
            'sum(rate(@requests@{job="@job@"}[5m]))\n'
            "  > @threshold@"
        ),
        for_duration="10m",
        severity=Severity.CRITICAL,
        summary="Too many responses in error",
        description=(
            "More than @threshold_pct@ % of the responses of the service have "
            "been server errors for 10 minutes."
        ),
        threshold_field="error_rate",
        threshold_default=0.05,
        threshold_unit="proportion (0.05 = 5 %)",
        # The steps are computed from the threshold: a frozen series would only
        # prove the rule for the threshold that was in force the day it was
        # written. The ratio targets (1 + threshold) / 2, therefore strictly
        # between the threshold and 1, for any admissible threshold.
        test_series=(
            ('@requests@{job="@job@", @status@="500"}', "0+1000x20"),
            ('@requests@{job="@job@", @status@="200"}', "0+@error_other_step@x20"),
        ),
        test_eval_time="15m",
        # `sum(...)` with no `by` lets no label survive: the alert only carries
        # the ones the rule adds.
        test_result_labels={},
    ),
)

LATENCY_ALERTS: tuple[Alert, ...] = (
    Alert(
        name="HighLatency",
        expr=(
            "histogram_quantile(0.95,\n"
            '  sum by (le) (rate(@duration@_bucket{job="@job@"}[5m]))\n'
            ") > @threshold@"
        ),
        for_duration="10m",
        severity=Severity.WARNING,
        summary="The service answers too slowly",
        description=(
            "The 95th percentile of the response time has exceeded @threshold@ "
            "second(s) for 10 minutes."
        ),
        threshold_field="latency_p95_seconds",
        threshold_default=1.0,
        threshold_unit="seconds",
        # Three cumulative buckets, whose bounds follow the threshold: 10
        # observations below the threshold, 90 between the threshold and its
        # double, none beyond. The 95th percentile falls in the second bucket and
        # is worth, by interpolation, about 1.94 times the threshold -- therefore
        # above it, whatever the threshold.
        test_series=(
            ('@duration@_bucket{job="@job@", le="@threshold@"}', "0+10x20"),
            ('@duration@_bucket{job="@job@", le="@latency_high_le@"}', "0+100x20"),
            ('@duration@_bucket{job="@job@", le="+Inf"}', "0+100x20"),
        ),
        test_eval_time="15m",
        test_result_labels={},
    ),
)

SATURATION_ALERTS: tuple[Alert, ...] = (
    Alert(
        name="MemoryNearLimit",
        expr=(
            'container_memory_working_set_bytes{namespace="@namespace@", container!=""}\n'
            "  /\n"
            'container_spec_memory_limit_bytes{namespace="@namespace@", container!=""}\n'
            "  > @threshold@"
        ),
        for_duration="10m",
        severity=Severity.WARNING,
        summary="A container is approaching its memory limit",
        description=(
            "Container {{ $labels.container }} of pod {{ $labels.pod }} has "
            "exceeded @threshold_pct@ % of its memory limit for 10 minutes. An "
            "actual overrun causes an OOMKill, not a slowdown."
        ),
        threshold_field="memory_ratio",
        threshold_default=0.9,
        threshold_unit="proportion of the limit (0.9 = 90 %)",
        # The targeted consumption is (1 + threshold) / 2 of the limit: strictly
        # above the threshold, whatever it is.
        test_series=(
            (
                "container_memory_working_set_bytes"
                '{namespace="@namespace@", pod="@pod@", container="@container@"}',
                "@memory_used@+0x20",
            ),
            (
                "container_spec_memory_limit_bytes"
                '{namespace="@namespace@", pod="@pod@", container="@container@"}',
                "@memory_limit@+0x20",
            ),
        ),
        test_eval_time="15m",
        test_result_labels={
            "namespace": "@namespace@",
            "pod": "@pod@",
            "container": "@container@",
        },
        needs_namespace=True,
    ),
    Alert(
        name="HighCpuUsage",
        expr=(
            "sum by (pod) (\n"
            "  rate(container_cpu_usage_seconds_total"
            '{namespace="@namespace@", container!=""}[5m])\n'
            ") > @threshold@"
        ),
        for_duration="10m",
        severity=Severity.WARNING,
        summary="A pod is durably consuming a lot of CPU",
        description=(
            "Pod {{ $labels.pod }} has been consuming more than @threshold@ "
            "core(s) for 10 minutes."
        ),
        threshold_field="cpu_cores",
        threshold_default=1.5,
        threshold_unit="cores",
        # The step of the counter is (threshold + 1) x 60: the derivative
        # therefore exceeds the threshold by a whole core, whatever the
        # threshold.
        test_series=(
            (
                "container_cpu_usage_seconds_total"
                '{namespace="@namespace@", pod="@pod@", container="@container@"}',
                "0+@cpu_step@x20",
            ),
        ),
        test_eval_time="15m",
        # `sum by (pod)` only lets `pod` survive.
        test_result_labels={"pod": "@pod@"},
        needs_namespace=True,
    ),
)

RESTART_ALERTS: tuple[Alert, ...] = (
    Alert(
        name="ContainerRestartLoop",
        expr=(
            "increase(\n"
            "  kube_pod_container_status_restarts_total"
            '{namespace="@namespace@"}[1h]\n'
            ") > @threshold@"
        ),
        for_duration="5m",
        severity=Severity.WARNING,
        summary="A container is restarting in a loop",
        description=(
            "Container {{ $labels.container }} of pod {{ $labels.pod }} has "
            "restarted more than @threshold@ times in one hour."
        ),
        threshold_field="restarts_per_hour",
        threshold_default=3,
        threshold_unit="restarts per hour",
        # The step is chosen so that the increase over one hour is worth at least
        # twice the threshold.
        test_series=(
            (
                "kube_pod_container_status_restarts_total"
                '{namespace="@namespace@", pod="@pod@", container="@container@"}',
                "0+@restart_step@x70",
            ),
        ),
        test_eval_time="70m",
        test_result_labels={
            "namespace": "@namespace@",
            "pod": "@pod@",
            "container": "@container@",
        },
        needs_namespace=True,
    ),
)

PROBE_ALERTS: tuple[Alert, ...] = (
    Alert(
        name="ExternalProbeFailed",
        expr='probe_success{job="@blackbox_job@"} == 0',
        for_duration="5m",
        severity=Severity.CRITICAL,
        summary="The service is no longer reachable from the outside",
        description=(
            "The external probe on {{ $labels.instance }} has been failing for 5 "
            "minutes. The service can be running and stay unreachable: that is "
            "precisely what this probe sees and the others do not."
        ),
        test_series=(
            (
                'probe_success{job="@blackbox_job@", instance="@probe_url@"}',
                "0+0x10",
            ),
        ),
        test_eval_time="6m",
        test_result_labels={"job": "@blackbox_job@", "instance": "@probe_url@"},
        needs_probe=True,
    ),
    Alert(
        name="CertificateExpiringSoon",
        expr=(
            "(\n"
            '  probe_ssl_earliest_cert_expiry{job="@blackbox_job@"} - time()\n'
            ") / 86400 < @threshold@"
        ),
        for_duration="15m",
        severity=Severity.WARNING,
        summary="A TLS certificate is approaching its expiry",
        description=(
            "The certificate served on {{ $labels.instance }} expires in less "
            "than @threshold@ days. An expired certificate gives no warning: it "
            "breaks every connection at once."
        ),
        threshold_field="certificate_days",
        threshold_default=21,
        threshold_unit="days before expiry",
        # The expiry date is placed at half the threshold: the alert must
        # therefore fire, whatever the number of days requested.
        test_series=(
            (
                "probe_ssl_earliest_cert_expiry"
                '{job="@blackbox_job@", instance="@probe_url@"}',
                "@cert_value@+0x25",
            ),
        ),
        test_eval_time="20m",
        test_result_labels={"job": "@blackbox_job@", "instance": "@probe_url@"},
        needs_probe=True,
    ),
)


#: Expression to **display** for each alert, without its comparison to the
#: threshold.
#:
#: A dashboard that plots the alerting condition only shows a curve with two
#: values: true or false. What one wants to see is the quantity itself and its
#: distance to the threshold -- hence this second expression, which is the first
#: one deprived of its last comparison.
#:
#: Indexed by alert name: an alert absent from this table is plotted by its full
#: expression, which stays correct, only less readable. The keys are the French
#: alert names, and must stay exactly in step with the `name` values above.
PANEL_EXPRESSIONS: dict[str, str] = {
    "TargetDown": 'up{job="@job@"}',
    "HighErrorRate": (
        'sum(rate(@requests@{job="@job@", @status@=~"5.."}[5m]))\n'
        "  /\n"
        'sum(rate(@requests@{job="@job@"}[5m]))'
    ),
    "HighLatency": (
        "histogram_quantile(0.95,\n"
        '  sum by (le) (rate(@duration@_bucket{job="@job@"}[5m]))\n'
        ")"
    ),
    "MemoryNearLimit": (
        'container_memory_working_set_bytes{namespace="@namespace@", container!=""}\n'
        "  /\n"
        'container_spec_memory_limit_bytes{namespace="@namespace@", container!=""}'
    ),
    "HighCpuUsage": (
        "sum by (pod) (\n"
        "  rate(container_cpu_usage_seconds_total"
        '{namespace="@namespace@", container!=""}[5m])\n'
        ")"
    ),
    "ContainerRestartLoop": (
        "increase(\n"
        "  kube_pod_container_status_restarts_total"
        '{namespace="@namespace@"}[1h]\n'
        ")"
    ),
    "ExternalProbeFailed": 'probe_success{job="@blackbox_job@"}',
    "CertificateExpiringSoon": (
        "(\n"
        '  probe_ssl_earliest_cert_expiry{job="@blackbox_job@"} - time()\n'
        ") / 86400"
    ),
}
