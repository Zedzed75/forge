"""Projection into copier's `domain` dict, and cross-checks.

The same contract as the three other domains: JSON-serialisable output, frozen
order, no pydantic object. The computation lives in :mod:`derive` and
:mod:`tree`.

The cross-checks of this domain have a particular colour: almost all of them are
**warnings**, and almost all of them say the same thing in different forms — "this
rule will never fire". That is the failure mode specific to monitoring: nothing
fails, nothing breaks, and nobody is warned the day they should have been.
"""

from __future__ import annotations

from typing import Any

from forge.plugins.monitoring import derive, render, tree
from forge.plugins.monitoring.catalog.registry import selected
from forge.plugins.monitoring.enums import RuleFamily
from forge.plugins_api import checks
from forge.plugins_api.types import Issue

DOMAIN_NAME = "monitoring"


def build(spec: Any) -> dict[str, Any]:
    """Build the `domain` dict passed to copier for the monitoring domain."""
    service = spec.service
    monitoring = spec.monitoring
    families = derive.families(spec)

    return {
        # -- scraping ------------------------------------------------------------
        "scrape": derive.scrape(spec),
        "metrics": derive.metrics(spec),
        "blackbox": derive.blackbox(spec),
        "job_name": service.name,
        "alert_prefix": render.alert_prefix(service.name),
        # -- retained families ----------------------------------------------------
        "families": families,
        "family_names": [family["name"] for family in families],
        # -- environments --------------------------------------------------------
        "environments": derive.environments(spec),
        "env_names": [env.name for env in service.environments],
        "default_env": service.environments[0].name,
        # -- short keys, read ONLY by the template paths -------------------------
        # Windows caps a path at 260 characters, and copier clones the template
        # repository into a temporary directory before rendering: a file name
        # carrying `[% yield env from domain.environments %]` twice went over the
        # limit. These lists carry a name only; the templates read the complete
        # entry back through `selectattr`.
        "envs": [{"name": env["name"]} for env in derive.environments(spec)],
        "fams": [{"name": family["name"]} for family in families],
        "dash": tree.dashboard_slot(spec),
        # -- dashboard --------------------------------------------------------
        "dashboard_file": tree.dashboard_file(service.name),
        "dashboard_panels": (
            derive.dashboard_panels(spec) if monitoring.extras.dashboard else []
        ),
        # -- extras and documentation -------------------------------------------------
        "extras": derive.extras(spec),
        "root_files": tree.root_files(spec),
        "expected_paths": tree.expected_paths(spec),
    }


# ---------------------------------------------------------------------------
# Cross-checks
# ---------------------------------------------------------------------------


def cross_check(spec: Any) -> list[Issue]:
    """Checks `MonitoringSpec` cannot do: it does not see `service:`."""
    monitoring = getattr(spec, "monitoring", None)
    if monitoring is None:
        return []

    issues: list[Issue] = []
    issues.extend(
        checks.unknown_environments(
            spec, "monitoring", {"monitoring.environments": monitoring.environments}
        )
    )
    issues.extend(_check_targets(spec, monitoring))
    issues.extend(_check_probes(spec, monitoring))
    issues.extend(_check_namespaces(spec, monitoring))
    issues.extend(_check_orphan_thresholds(monitoring))
    return issues


def _check_targets(spec: Any, monitoring: Any) -> list[Issue]:
    """Report an environment none of whose targets is scraped.

    It is the most serious defect this domain can produce, and the most silent:
    without a target, no series exists, so `up == 0` cannot fire. The dashboard is
    empty and everything looks calm.
    """
    return [
        Issue(
            level="warning",
            message=(
                f"no scrape target is declared for the environment '{env.name}': "
                "nothing will be watched there, and no alert will be able to fire."
            ),
            hint=(
                f"Set monitoring.environments.{env.name}.targets "
                "(for instance ['api.example.net:9090'])."
            ),
            domains=(DOMAIN_NAME,),
        )
        for env in spec.service.environments
        if not monitoring.overrides(env.name).targets
    ]


def _check_probes(spec: Any, monitoring: Any) -> list[Issue]:
    """Checks specific to the external probe family."""
    if not monitoring.uses(RuleFamily.PROBE):
        return []

    issues: list[Issue] = []
    for env in spec.service.environments:
        urls = monitoring.overrides(env.name).probe_urls
        if not urls:
            issues.append(
                Issue(
                    level="warning",
                    message=(
                        f"the 'probe' family is retained but no URL is probed for "
                        f"the environment '{env.name}': its alerts will never fire."
                    ),
                    hint=(
                        f"Set monitoring.environments.{env.name}.probe_urls, or "
                        "remove 'probe' from monitoring.rules."
                    ),
                    domains=(DOMAIN_NAME,),
                )
            )
            continue
        plaintext = sorted(url for url in urls if url.startswith("http://"))
        if plaintext:
            issues.append(
                Issue(
                    level="warning",
                    message=(
                        f"environment '{env.name}': the URLs probed over http:// "
                        f"({', '.join(plaintext)}) do not expose "
                        "probe_ssl_earliest_cert_expiry; the certificate expiry "
                        "alert will stay mute for them."
                    ),
                    hint="Probe the https:// URL when the service exposes one.",
                    domains=(DOMAIN_NAME,),
                )
            )
    return issues


def _check_namespaces(spec: Any, monitoring: Any) -> list[Issue]:
    """Report an undeclared namespace where a family depends on one.

    Falling back on the service name is reasonable, but it is wrong as soon as the
    namespace follows another convention — and a rule filtering on a namespace
    that does not exist returns no series, so it never fires.
    """
    concerned = [
        family.name
        for family in selected(monitoring.family_names())
        if family.needs_namespace
    ]
    if not concerned:
        return []
    return [
        Issue(
            level="warning",
            message=(
                f"environment '{env.name}': the {', '.join(concerned)} families "
                f"filter on a namespace, and none is declared; forge uses "
                f"'{spec.service.name}'."
            ),
            hint=(
                f"Set monitoring.environments.{env.name}.namespace to lift the "
                "doubt."
            ),
            domains=(DOMAIN_NAME,),
        )
        for env in spec.service.environments
        if monitoring.overrides(env.name).namespace is None
    ]


def _check_orphan_thresholds(monitoring: Any) -> list[Issue]:
    """Report a threshold set for a family absent from `monitoring.rules`.

    A carefully chosen and silently ignored value is worse than an error: nothing
    distinguishes it from a value that is applied.
    """
    from forge.plugins.monitoring.catalog.registry import all_families

    retained = set(monitoring.family_names())
    owner = {
        alert.threshold_field: family.name
        for family in all_families()
        for alert in family.alerts
        if alert.threshold_field
    }

    issues: list[Issue] = []
    for env_name in sorted(monitoring.environments):
        thresholds = monitoring.environments[env_name].thresholds
        if thresholds is None:
            continue
        for field in sorted(thresholds.declared()):
            family = owner.get(field, "")
            if not family or family in retained:
                continue
            issues.append(
                Issue(
                    level="warning",
                    message=(
                        f"monitoring.environments.{env_name}.thresholds.{field} "
                        f"sets a threshold of the '{family}' family, which is "
                        "absent from monitoring.rules: that value will not be "
                        "applied."
                    ),
                    hint=(
                        f"Add '{family}' to monitoring.rules, or remove the "
                        f"{field} threshold."
                    ),
                    domains=(DOMAIN_NAME,),
                )
            )
    return issues


def probe_hosts(spec: Any) -> tuple[str, ...]:
    """Probed host names, all environments taken together, sorted.

    Feeds the `ingress_hosts` facet of the shared vocabulary: it is through it
    that forge can say "the chart exposes boutique.example.net, the probe looks at
    api.example.net" without either domain knowing the other.
    """
    hosts: set[str] = set()
    for override in spec.monitoring.environments.values():
        for url in override.probe_urls:
            without_scheme = url.split("://", 1)[-1]
            host = without_scheme.split("/", 1)[0].split(":", 1)[0]
            if host:
                hosts.add(host)
    return tuple(sorted(hosts))
