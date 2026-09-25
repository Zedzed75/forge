"""Cross-domain checks, with no domain knowledge at all (decision Q4).

Every plugin declares a `Projection`: what it claims to produce, expressed in
neutral vocabulary. The core does nothing but **compare those declarations** —
two domains declaring the same facet must declare the same value. A third plugin
therefore inherits these checks without the core changing (DESIGN.md §6.4).
"""

from __future__ import annotations

from forge.plugins_api.types import Issue, Projection

#: A facet is only compared when at least this many domains declare it.
MIN_DECLARERS = 2

#: **Shared facet vocabulary.**
#:
#: The core compares facets **by name**: that name is therefore a namespace
#: shared by every plugin, and two domains using the same name are asserting they
#: talk about the same thing. Without an explicit rule the collision is silent
#: and produces a false positive — measured in phase 5: Ansible declared `hosts`
#: for its inventory machines, Helm for its Ingress hosts, and `forge validate`
#: failed on a perfectly consistent project.
#:
#: A plugin declaring a facet outside this vocabulary is compared with nobody:
#: harmless, but pointless too. For a facet to be of any use it must be added
#: here **and** agreed upon.
FACET_VOCABULARY: dict[str, str] = {
    "ingress_hosts": "domain names through which the service is reachable from outside",
    "inventory_hosts": "machines named in a configuration inventory",
    "namespaces": "logical partitions the service is deployed into",
    "groups": "groupings of machines sharing a role",
}


def _sorted_domains(projections: dict[str, Projection]) -> list[str]:
    return sorted(projections)


def _check_service_name(projections: dict[str, Projection]) -> list[Issue]:
    values: dict[str, list[str]] = {}
    for domain in _sorted_domains(projections):
        values.setdefault(projections[domain].service_name, []).append(domain)
    if len(values) <= 1:
        return []
    detail = "; ".join(
        f"{name!r} for {', '.join(domains)}" for name, domains in sorted(values.items())
    )
    return [
        Issue(
            level="error",
            message=f"the domains do not use the same service name: {detail}",
            hint="service.name must be carried over as-is by every domain",
            domains=tuple(_sorted_domains(projections)),
        )
    ]


def _check_environments(projections: dict[str, Projection]) -> list[Issue]:
    """Compare what **each domain actually materialises**.

    `Projection.environments` does not copy `service.environments`: a domain
    declares there the environments it produces something for. An environment
    Ansible ignores while Helm deploys into it is therefore visible here, and
    nowhere else — which is precisely what comparing projections brings, and what
    no single domain can see on its own.
    """
    issues: list[Issue] = []
    domains = _sorted_domains(projections)
    everything = sorted({env for domain in domains for env in projections[domain].environments})

    for env in everything:
        absent = [d for d in domains if env not in projections[d].environments]
        if not absent:
            continue
        present = [d for d in domains if env in projections[d].environments]
        issues.append(
            Issue(
                level="warning",
                message=(
                    f"environment '{env}' is materialised by "
                    f"{', '.join(present)} but not by {', '.join(absent)}"
                ),
                hint=(
                    f"if that is intended, nothing to do; otherwise complete the "
                    f"{absent[0]} section for '{env}', or remove it from "
                    "service.environments"
                ),
                domains=tuple(domains),
            )
        )

    # The order still carries meaning: it describes the dev -> prod promotion.
    reference_domain = domains[0]
    reference = [e for e in projections[reference_domain].environments]
    for domain in domains[1:]:
        current = [e for e in projections[domain].environments]
        common_ref = [e for e in reference if e in current]
        common_cur = [e for e in current if e in reference]
        if common_ref != common_cur:
            issues.append(
                Issue(
                    level="warning",
                    message=(
                        f"{domain} orders the environments differently from "
                        f"{reference_domain} ({', '.join(current)} vs "
                        f"{', '.join(reference)})"
                    ),
                    hint="the order of service.environments is the promotion order",
                    domains=(reference_domain, domain),
                )
            )
    return issues


def _check_labels(projections: dict[str, Projection]) -> list[Issue]:
    issues: list[Issue] = []
    seen: dict[str, tuple[str, str]] = {}  # key -> (value, domain)
    for domain in _sorted_domains(projections):
        for key, value in sorted(projections[domain].labels.items()):
            if key not in seen:
                seen[key] = (value, domain)
                continue
            known_value, known_domain = seen[key]
            if known_value != value:
                issues.append(
                    Issue(
                        level="error",
                        message=(
                            f"contradictory label {key!r}: {known_value!r} in "
                            f"{known_domain}, {value!r} in {domain}"
                        ),
                        hint="shared labels come from service.labels",
                        domains=(known_domain, domain),
                    )
                )
    return issues


def _check_facets(projections: dict[str, Projection]) -> list[Issue]:
    issues: list[Issue] = []
    declarers: dict[str, list[str]] = {}
    for domain in _sorted_domains(projections):
        for facet in projections[domain].facets:
            declarers.setdefault(facet, []).append(domain)

    for facet, domains in sorted(declarers.items()):
        if len(domains) < MIN_DECLARERS or facet not in FACET_VOCABULARY:
            continue
        reference_domain = domains[0]
        reference = set(projections[reference_domain].facets[facet])
        for domain in domains[1:]:
            current = set(projections[domain].facets[facet])
            if current == reference:
                continue
            missing = sorted(reference - current)
            extra = sorted(current - reference)
            parts = []
            if missing:
                parts.append(f"absent from {domain}: {', '.join(missing)}")
            if extra:
                parts.append(f"absent from {reference_domain}: {', '.join(extra)}")
            issues.append(
                Issue(
                    level="error",
                    message=(
                        f"facet \"{facet}\" diverges between {reference_domain} and "
                        f"{domain} ({'; '.join(parts)})"
                    ),
                    hint=(
                        "both domains describe the same reality: align the "
                        "specification, or stop declaring it on both sides"
                    ),
                    domains=(reference_domain, domain),
                )
            )
    return issues


def compare_projections(projections: dict[str, Projection]) -> list[Issue]:
    """Compare every domain's projection and return the findings.

    No rule of the form "if ansible then…": nothing but equalities between what
    the domains declare.
    """
    if len(projections) < MIN_DECLARERS:
        return []
    issues: list[Issue] = []
    issues.extend(_check_service_name(projections))
    issues.extend(_check_environments(projections))
    issues.extend(_check_labels(projections))
    issues.extend(_check_facets(projections))
    return issues


def format_issues(issues: list[Issue]) -> str:
    """Format the findings, errors first."""
    if not issues:
        return "cross-domain consistency: no difference"
    lines: list[str] = []
    for issue in sorted(issues, key=lambda i: (i.level != "error", i.message)):
        mark = "ERROR  " if issue.level == "error" else "WARNING"
        scope = f" [{', '.join(issue.domains)}]" if issue.domains else ""
        lines.append(f"[{mark}]{scope} {issue.message}")
        if issue.hint:
            lines.append(f"          -> {issue.hint}")
    return "\n".join(lines)


def has_errors(issues: list[Issue]) -> bool:
    """True if at least one finding is of level error."""
    return any(issue.level == "error" for issue in issues)
