"""Rule families: a rule file, its alerts, and its traps.

One family = one `rules/<family>.yml` file per environment, the unit test file
that goes with it, and what has to be known in order not to be caught out.

The canonical order follows that of a diagnosis: does the service answer? does it
answer correctly? does it answer quickly? does it have enough to keep going? is
it holding up? is it reachable from the outside?
"""

from __future__ import annotations

from dataclasses import dataclass

from forge.plugins.monitoring.catalog import alerts as alert_defs
from forge.plugins.monitoring.catalog.alerts import Alert
from forge.plugins.monitoring.enums import RuleFamily


@dataclass(frozen=True)
class Family:
    """A rule family, retained by the specification or not."""

    #: Identifier used in `monitoring.rules` of forge.yml.
    name: str

    #: One-line summary.
    summary: str

    #: Long description, displayed by `forge catalog monitoring <family>`.
    details: str

    #: Alerts of the file, in writing order.
    alerts: tuple[Alert, ...]

    #: Exporters whose metrics are necessary.
    exporters: tuple[str, ...] = ()

    #: Measured traps, displayed and taken up as comments in the generated file.
    traps: tuple[str, ...] = ()

    @property
    def needs_namespace(self) -> bool:
        """True if an alert of the family targets a Kubernetes namespace."""
        return any(alert.needs_namespace for alert in self.alerts)

    @property
    def needs_probe(self) -> bool:
        """True if an alert of the family relies on a blackbox probe."""
        return any(alert.needs_probe for alert in self.alerts)

    def option_descriptions(self) -> dict[str, str]:
        """Adjustable thresholds of the family, in the format `CatalogEntry` expects."""
        return {
            alert.threshold_field: (
                f"{alert.summary} — threshold in {alert.threshold_unit}, "
                f"default {alert.threshold_default}"
            )
            for alert in self.alerts
            if alert.threshold_field
        }


FAMILIES: tuple[Family, ...] = (
    Family(
        name=RuleFamily.AVAILABILITY.value,
        summary="The target no longer answers the collector",
        details=(
            "The simplest alert, and the one most often forgotten: `up == 0`. "
            "Prometheus builds the `up` metric itself on every collection, "
            "without any exporter having to expose it.\n\n"
            "It is the only family that depends on no naming convention: it works "
            "from the very first collection."
        ),
        alerts=alert_defs.AVAILABILITY_ALERTS,
        traps=(
            "`up == 0` only fires if the target is **known** to the collector. A "
            "target never declared produces no series, and therefore no alert: "
            "silence is not health. That is why the targets are written in the "
            "configuration rather than discovered.",
            "Without a `for` clause, a two-minute restart wakes somebody up. With "
            "a `for` that is too long, a real outage waits. Five minutes is the "
            "usual compromise, not a truth.",
            "An alert that fires for **every** instance at once almost always "
            "points at the collector or the network, not at the service. A "
            "receiver that does not tell the difference drowns the on-call rota.",
        ),
    ),
    Family(
        name=RuleFamily.ERROR_RATE.value,
        summary="Too many responses in server error",
        details=(
            "A ratio, never a count: a hundred errors out of a million requests "
            "is not the same thing as a hundred errors out of two hundred.\n\n"
            "The name of the counter and that of the status code label are "
            "**configurable**: they depend on the client library used, and "
            "guessing one would produce an alert that never fires."
        ),
        alerts=alert_defs.ERROR_RATE_ALERTS,
        exporters=("the application itself (Prometheus client)",),
        traps=(
            "A ratio over a null denominator gives `NaN`, and a comparison with "
            "`NaN` is false: the alert does not fire. A service that no longer "
            "receives **any** request is therefore invisible here -- it is the "
            "`availability` family that sees it.",
            "`rate()` over a window shorter than two collection intervals returns "
            "`NaN`. With a collection every 30 s, a 5-minute window leaves room; "
            "a one-minute window leaves none.",
            "The status label is not standardised: `status`, `code`, "
            "`status_code` depending on the library. Getting the name wrong gives "
            "a valid rule, accepted by promtool, and permanently mute.",
            "Counting only the 5xx lets through the client-side timeouts and the "
            "refused connections, which produce no response and therefore no line "
            "in the counter.",
        ),
    ),
    Family(
        name=RuleFamily.LATENCY.value,
        summary="The service answers too slowly",
        details=(
            "95th percentile computed on a histogram, not an average: an average "
            "response time hides exactly what is being looked for.\n\n"
            "Requires a histogram, not a summary: `histogram_quantile` works on "
            "the `_bucket` buckets, which a summary does not expose."
        ),
        alerts=alert_defs.LATENCY_ALERTS,
        exporters=("the application itself (Prometheus client)",),
        traps=(
            "`histogram_quantile` **interpolates linearly** in the bucket the "
            "percentile falls into. The precision of the result therefore never "
            "exceeds that of the bucket layout: with 0.5 s / 2 s buckets, no "
            "percentile can be worth 1.2 s other than by interpolation.",
            "If the percentile falls into the last bucket (`+Inf`), the function "
            "returns the upper bound of the previous bucket -- never infinity. A "
            "catastrophic latency can therefore show up as equal to the bound of "
            "the largest finite bucket, and not cross a threshold placed above "
            "it.",
            "The `sum by (le)` aggregation is mandatory before "
            "`histogram_quantile`: applying the function to non-aggregated "
            "buckets computes one percentile per instance, which makes no sense "
            "when the one of the service is wanted.",
            "The buckets of a histogram are **cumulative**: `le=\"2\"` also counts "
            "the observations below 0.5 s. Writing a test series with decreasing "
            "buckets produces an invalid histogram that Prometheus accepts and "
            "interprets wrongly.",
        ),
    ),
    Family(
        name=RuleFamily.SATURATION.value,
        summary="Consumption close to the limits (memory, CPU)",
        details=(
            "Two alerts of a different nature, and the distinction matters: "
            "exceeding its memory limit gets the container **killed** (OOMKill), "
            "exceeding its CPU limit only makes it slow down (throttling).\n\n"
            "Memory is therefore watched as a proportion of its limit; CPU in "
            "absolute value, because a pod with no CPU limit is frequent and "
            "legitimate."
        ),
        alerts=alert_defs.SATURATION_ALERTS,
        exporters=("cAdvisor, exposed by the kubelet",),
        traps=(
            "A container **with no memory limit** does not expose "
            "`container_spec_memory_limit_bytes`, or exposes it at zero: the "
            "division gives no result, and the alert stays mute. The absence of an "
            "alert therefore says nothing about the health of the pod.",
            "`container_memory_working_set_bytes` is the metric the kubelet "
            "compares to the limit in order to decide on an OOMKill -- not "
            "`container_memory_usage_bytes`, which includes the reclaimable file "
            "cache and largely overestimates the real pressure.",
            "The `container!=\"\"` filter is not cosmetic: cAdvisor also exposes "
            "series aggregated at the pod level, with an empty `container` label. "
            "Counting them twice doubles the apparent consumption.",
            "CPU throttling is not visible in "
            "`container_cpu_usage_seconds_total`: a throttled pod consumes less, "
            "and therefore looks healthy. It is "
            "`container_cpu_cfs_throttled_seconds_total` that shows it.",
        ),
    ),
    Family(
        name=RuleFamily.RESTARTS.value,
        summary="A container is restarting in a loop",
        details=(
            "A service can answer correctly and restart every ten minutes. None "
            "of the other families sees it: availability is good between two "
            "restarts, and so is the error rate.\n\n"
            "It is often the first visible sign of a memory leak or of a badly "
            "tuned liveness probe."
        ),
        alerts=alert_defs.RESTART_ALERTS,
        exporters=("kube-state-metrics",),
        traps=(
            "`kube_pod_container_status_restarts_total` is reset to zero when the "
            "pod is recreated -- it is not a monotonic counter from the point of "
            "view of the service. `increase()` handles the reset of a series, but "
            "not the disappearance of a series in favour of another: a replaced "
            "pod loses the history.",
            "A liveness probe that is too strict produces exactly this alert, "
            "while the application is fine. Checking the tuning of the probe "
            "before looking in the code saves hours.",
            "kube-state-metrics has to be running **and** be collected. Its "
            "absence makes this family silent without any error appearing "
            "anywhere.",
        ),
    ),
    Family(
        name=RuleFamily.PROBE.value,
        summary="External probe: reachability and certificate expiry",
        details=(
            "The only family that looks at the service **from the outside**, like "
            "a user. A service can be running perfectly and stay unreachable: "
            "broken DNS, badly configured ingress, expired certificate. No "
            "internal metric shows it.\n\n"
            "Requires a blackbox exporter reachable by the collector, and URLs to "
            "probe declared per environment."
        ),
        alerts=alert_defs.PROBE_ALERTS,
        exporters=("blackbox exporter",),
        traps=(
            "The probe configuration of the blackbox exporter is a ballet of "
            "`relabel_configs`: the address to probe goes through "
            "`__param_target`, then becomes `instance`, and `__address__` is "
            "finally replaced by the address of the exporter. Skipping a step "
            "makes it probe the exporter itself, which always answers.",
            "`probe_ssl_earliest_cert_expiry` only exists for **HTTPS** probes. A "
            "URL in `http://` does not produce this series, and the certificate "
            "alert stays mute without anything reporting it.",
            "The probe sees what a client sees from the network of the collector. "
            "If that one is inside the cluster, it tests neither the public DNS, "
            "nor the load balancer, nor the firewall -- that is to say, most of "
            "what breaks.",
            "A certificate renewed automatically still triggers the alert if the "
            "renewal fails silently. That is the point; it is not a false "
            "positive.",
        ),
    ),
)

#: Families indexed by name.
BY_NAME: dict[str, Family] = {family.name: family for family in FAMILIES}
