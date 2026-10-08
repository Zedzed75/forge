"""The `monitoring:` section of forge.yml.

**A self-contained domain.** It reads no other section: what it watches, it
declares. That is a design decision, not a limit — a service can be watched
without being deployed by forge, and a domain that read `helm.components` would
stop working the day the chart comes from elsewhere.

Coherence with the other domains goes through the **facet vocabulary**
(`namespaces`, `ingress_hosts`), compared by `forge validate`: if the chart
exposes `boutique.example.net` and the probe looks at `api.example.net`, forge
says so — without any "if helm then monitoring" rule existing anywhere.

What this model refuses, and why: a malformed metric name is refused by promtool
anyway; a name that is **well formed but wrong** produces a valid and permanently
mute rule. The model cannot check that a metric exists, but it can require that
the ones whose source it knows are not redefined at random.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, Field, field_validator, model_validator

from forge.plugins.monitoring.catalog.registry import family_names
from forge.plugins.monitoring.constants import (
    DURATION_RE,
    LABEL_NAME_RE,
    METRIC_NAME_RE,
    PROBE_URL_RE,
    TARGET_RE,
)
from forge.plugins.monitoring.enums import RuleFamily
from forge.spec.names import check_pattern, require_unique
from forge.spec.types import DnsLabel, ForgeModel


def _duration(value: str) -> str:
    return check_pattern(value, DURATION_RE, "a Prometheus duration (30s, 5m, 1h)")


def _metric_name(value: str) -> str:
    return check_pattern(value, METRIC_NAME_RE, "a Prometheus metric name")


def _label_name(value: str) -> str:
    return check_pattern(value, LABEL_NAME_RE, "a Prometheus label name")


def _target(value: str) -> str:
    return check_pattern(value, TARGET_RE, "a scrape target 'host:port'")


def _probe_url(value: str) -> str:
    return check_pattern(value, PROBE_URL_RE, "an http:// or https:// URL")


Duration = Annotated[str, AfterValidator(_duration)]
MetricName = Annotated[str, AfterValidator(_metric_name)]
LabelName = Annotated[str, AfterValidator(_label_name)]
Target = Annotated[str, AfterValidator(_target)]
ProbeUrl = Annotated[str, AfterValidator(_probe_url)]


class ScrapeSpec(ForgeModel):
    """How the collector queries the service."""

    #: Period between two scrapes. It bounds the granularity of everything that
    #: follows: a `rate()` window has to cover at least two scrapes.
    interval: Duration = "30s"

    #: Delay beyond which a scrape is given up. Always below the interval,
    #: otherwise the scrapes overlap.
    timeout: Duration = "10s"

    #: Path exposing the metrics.
    metrics_path: str = "/metrics"

    @model_validator(mode="after")
    def _timeout_under_interval(self) -> ScrapeSpec:
        if _seconds(self.timeout) > _seconds(self.interval):
            raise ValueError(
                f"scrape.timeout ({self.timeout}) exceeds scrape.interval "
                f"({self.interval}): the scrapes would overlap."
            )
        return self


def _seconds(duration: str) -> float:
    """Convert a Prometheus duration into seconds."""
    units = {"ms": 0.001, "s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800, "y": 31536000}
    for suffix in ("ms", "s", "m", "h", "d", "w", "y"):
        if duration.endswith(suffix):
            return float(duration[: -len(suffix)]) * units[suffix]
    raise ValueError(duration)  # pragma: no cover - the format is already valid


class MetricNamesSpec(ForgeModel):
    """Names of the metrics the application itself exposes.

    They are not standardised: their name depends on the client library. The
    infrastructure metrics (`up`, `container_*`, `probe_*`) do not appear here —
    those have a fixed name, and letting it be configured would be an invitation
    to change it for a name that does not exist.
    """

    #: Counter of served requests, with a status code label.
    requests_total: MetricName = "http_requests_total"

    #: Histogram of the response time. **Without** the `_bucket` suffix: the
    #: rules add it. A summary will not do — it exposes no buckets.
    request_duration_seconds: MetricName = "http_request_duration_seconds"

    #: Label carrying the HTTP status code. `status`, `code` or `status_code`
    #: depending on the library: getting it wrong gives a valid and permanently
    #: mute rule.
    status_label: LabelName = "status"


class ThresholdsSpec(ForgeModel):
    """Firing thresholds. Any omitted key keeps the catalogue value."""

    #: Proportion of responses in server error (0.05 = 5 %).
    error_rate: float | None = Field(default=None, gt=0, lt=1)

    #: 95th percentile of the response time, in seconds.
    latency_p95_seconds: float | None = Field(default=None, gt=0)

    #: Proportion of the memory limit (0.9 = 90 %).
    memory_ratio: float | None = Field(default=None, gt=0, le=1)

    #: CPU consumption of a pod, in cores.
    cpu_cores: float | None = Field(default=None, gt=0)

    #: Number of restarts in one hour beyond which an alert fires.
    restarts_per_hour: int | None = Field(default=None, gt=0)

    #: Days left before the certificate expires.
    certificate_days: int | None = Field(default=None, gt=0)

    def declared(self) -> dict[str, float | int]:
        """Thresholds actually filled in, indexed by field name."""
        return {
            name: value
            for name, value in self.model_dump().items()
            if value is not None
        }


class MonitoringEnvironmentSpec(ForgeModel):
    """What is watched in an environment, and under which thresholds."""

    #: Kubernetes namespace observed. Necessary to the `saturation` and
    #: `restarts` families, which filter the container metrics on it.
    namespace: DnsLabel | None = None

    #: Scraped targets, in the `host:port` form. Written in the configuration
    #: rather than discovered: a target never declared produces no series, hence
    #: no alert — silence is not health.
    targets: list[Target] = Field(default_factory=list)

    #: URLs probed from the outside by the blackbox exporter. Only `https://`
    #: URLs make it possible to watch the certificate expiry.
    probe_urls: list[ProbeUrl] = Field(default_factory=list)

    #: Thresholds specific to this environment. Production often deserves tighter
    #: thresholds than development.
    thresholds: ThresholdsSpec | None = None

    #: Labels added to every series of this environment.
    labels: dict[str, str] = Field(default_factory=dict)

    @field_validator("targets")
    @classmethod
    def _unique_targets(cls, value: list[str]) -> list[str]:
        require_unique(value, "scrape targets")
        return value

    @field_validator("probe_urls")
    @classmethod
    def _unique_probes(cls, value: list[str]) -> list[str]:
        require_unique(value, "probed URLs")
        return value


class MonitoringExtras(ForgeModel):
    """Extra files of the generated project."""

    #: Makefile of shortcuts (`make check`, `make test`).
    makefile: bool = True

    #: Grafana dashboard. Its panels reuse the expressions of the retained
    #: families: what is alerted on is what is looked at.
    dashboard: bool = True

    # The alert unit tests are **not** an option, and that is deliberate: an
    # untested alerting rule is a rule nobody knows fires or not, and that is only
    # learnt the day it should have. Making them optional would have been an
    # invitation to the wrong choice.


class MonitoringSpec(ForgeModel):
    """The `monitoring:` section: probes, alerting rules and their tests."""

    #: How the collector queries the service.
    scrape: ScrapeSpec = Field(default_factory=ScrapeSpec)

    #: Names of the metrics the application exposes.
    metrics: MetricNamesSpec = Field(default_factory=MetricNamesSpec)

    #: Retained rule families. The order they are written in does not matter: the
    #: catalogue puts them back into canonical order.
    rules: list[RuleFamily] = Field(
        default_factory=lambda: [RuleFamily.AVAILABILITY], min_length=1
    )

    #: Address of the blackbox exporter, as the collector sees it.
    blackbox_address: str = "blackbox-exporter:9115"

    #: What is watched, environment by environment.
    environments: dict[str, MonitoringEnvironmentSpec] = Field(default_factory=dict)

    #: Extra files.
    extras: MonitoringExtras = Field(default_factory=MonitoringExtras)

    @field_validator("rules")
    @classmethod
    def _unique_families(cls, value: list[RuleFamily]) -> list[RuleFamily]:
        require_unique((family.value for family in value), "rule families")
        return value

    @model_validator(mode="after")
    def _known_families(self) -> MonitoringSpec:
        """Guard rail: the catalogue and the enumeration must stay in agreement."""
        known = set(family_names())
        unknown = sorted(f.value for f in self.rules if f.value not in known)
        if unknown:  # pragma: no cover - a programming defect of the plugin
            raise ValueError(f"families absent from the catalogue: {', '.join(unknown)}.")
        return self

    # -- lookups ------------------------------------------------------------

    def overrides(self, environment: str) -> MonitoringEnvironmentSpec:
        """What is watched in `environment`, empty when it is not described."""
        return self.environments.get(environment) or MonitoringEnvironmentSpec()

    def uses(self, family: RuleFamily) -> bool:
        """Tell whether the family is retained."""
        return family in self.rules

    def family_names(self) -> tuple[str, ...]:
        """Names of the retained families, as written in the specification."""
        return tuple(family.value for family in self.rules)

    def needs_blackbox(self) -> bool:
        """True when a retained family relies on an external probe."""
        from forge.plugins.monitoring.catalog.registry import selected

        return any(family.needs_probe for family in selected(self.family_names()))
