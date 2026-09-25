"""Interview for the monitoring domain.

The order of the questions follows the order of the decision: first **what is
watched** (the rule families), then **where** (the targets, per environment),
then the extras. Questions without an object are not asked — a URL to probe is
only asked for when the `probe` family is retained.

Per arbitration R7 (PLAN.md), returning `None` means "there is nothing to
generate", not "the user declines the domain": here, no rule family retained.
"""

from __future__ import annotations

from typing import Any

from forge.interview.prompter import Prompter
from forge.plugins.monitoring.catalog.registry import all_families
from forge.plugins.monitoring.constants import PROBE_URL_RE, TARGET_RE
from forge.plugins.monitoring.enums import RuleFamily
from forge.spec.service import ServiceSpec


def run(prompter: Prompter, service: ServiceSpec) -> dict[str, Any] | None:
    """Conduct the interview and return the `monitoring:` section of forge.yml."""
    prompter.note(
        "Monitoring describes itself: it reads no other section. What it "
        "watches, you declare here."
    )

    families = _ask_families(prompter)
    if not families:
        prompter.note("No family retained: the monitoring domain is not generated.")
        return None

    section: dict[str, Any] = {"rules": families}

    metrics = _ask_metrics(prompter, families)
    if metrics:
        section["metrics"] = metrics

    environments = _ask_environments(prompter, service, families)
    if environments:
        section["environments"] = environments

    prompter.note(
        "The alert unit tests are generated in every case: an untested rule is a "
        "rule nobody knows will fire."
    )
    section["extras"] = {
        "dashboard": prompter.confirm("Generate a Grafana dashboard?", default=True),
        "makefile": prompter.confirm("Add a Makefile of shortcuts?", default=True),
    }
    return section


def _ask_families(prompter: Prompter) -> list[str]:
    """Rule families retained."""
    choices = [(family.name, f"{family.name} — {family.summary}") for family in all_families()]
    return prompter.checkbox(
        "What should be watched?", choices, [RuleFamily.AVAILABILITY.value]
    )


def _ask_metrics(prompter: Prompter, families: list[str]) -> dict[str, Any]:
    """Names of the application metrics, only when a family depends on them.

    The infrastructure metrics (`up`, `container_*`, `probe_*`) are not asked
    for: their names are fixed, and having them typed in would invite changing
    one for a name that does not exist.
    """
    needed = {RuleFamily.ERROR_RATE.value, RuleFamily.LATENCY.value} & set(families)
    if not needed:
        return {}

    prompter.note(
        "These names depend on the application's client library. Getting one "
        "wrong produces a valid and permanently silent rule."
    )
    metrics: dict[str, Any] = {}
    if RuleFamily.ERROR_RATE.value in families:
        counter = prompter.text("Request counter", default="http_requests_total")
        if counter != "http_requests_total":
            metrics["requests_total"] = counter
        label = prompter.text("Label carrying the status code", default="status")
        if label != "status":
            metrics["status_label"] = label
    if RuleFamily.LATENCY.value in families:
        histogram = prompter.text(
            "Response time histogram (without the _bucket suffix)",
            default="http_request_duration_seconds",
        )
        if histogram != "http_request_duration_seconds":
            metrics["request_duration_seconds"] = histogram
    return metrics


def _ask_environments(
    prompter: Prompter, service: ServiceSpec, families: list[str]
) -> dict[str, Any]:
    """What is watched in each environment."""
    needs_namespace = bool(
        {RuleFamily.SATURATION.value, RuleFamily.RESTARTS.value} & set(families)
    )
    needs_probe = RuleFamily.PROBE.value in families

    environments: dict[str, Any] = {}
    for env in service.environments:
        prompter.note(f"Environment '{env.name}':")
        entry: dict[str, Any] = {}

        targets = prompter.text(
            "  Scraped targets, comma-separated (host:port)",
            default="",
            validate=_validate_targets,
        )
        if targets.strip():
            entry["targets"] = [part.strip() for part in targets.split(",") if part.strip()]

        if needs_namespace:
            namespace = prompter.text("  Kubernetes namespace watched", default=service.name)
            if namespace != service.name:
                entry["namespace"] = namespace

        if needs_probe:
            default_url = f"https://{service.name}.{env.domain}" if env.domain else ""
            urls = prompter.text(
                "  URLs probed from the outside, comma-separated",
                default=default_url,
                validate=_validate_urls,
            )
            if urls.strip():
                entry["probe_urls"] = [
                    part.strip() for part in urls.split(",") if part.strip()
                ]

        if entry:
            environments[env.name] = entry
    return environments


def _validate_targets(value: str) -> str | None:
    """Validate a comma-separated list of `host:port` targets."""
    for part in (item.strip() for item in value.split(",")):
        if part and not TARGET_RE.match(part):
            return f"'{part}' is not a 'host:port' target."
    return None


def _validate_urls(value: str) -> str | None:
    """Validate a comma-separated list of URLs."""
    for part in (item.strip() for item in value.split(",")):
        if part and not PROBE_URL_RE.match(part):
            return f"'{part}' is not an http:// or https:// URL."
    return None
