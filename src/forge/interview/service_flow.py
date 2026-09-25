"""Interview for the `service:` block — the only part the core conducts itself.

Domain-specific questions belong to the domain's plugin, through the
`forge_interview` hook (DESIGN.md §7). Here, only the identity of the service and
its environments: what every domain must see the same way.
"""

from __future__ import annotations

from typing import Any

from forge.interview.prompter import Prompter
from forge.spec.names import DNS_LABEL_RE, SUBDOMAIN_RE

#: Environments offered by default, in promotion order.
DEFAULT_ENVIRONMENTS = "dev,staging,prod"

#: Environment treated as production when the user says nothing.
DEFAULT_PRODUCTION = "prod"


def _validate_dns_label(value: str) -> str | None:
    if not DNS_LABEL_RE.match(value.strip()):
        return "expected a DNS label: lowercase letters, digits and internal hyphens"
    return None


def _validate_non_empty(value: str) -> str | None:
    return None if value.strip() else "value required"


def _validate_environments(value: str) -> str | None:
    names = [part.strip() for part in value.split(",") if part.strip()]
    if not names:
        return "at least one environment is required"
    if len(set(names)) != len(names):
        return "duplicate environment names"
    for name in names:
        if not DNS_LABEL_RE.match(name):
            return f"{name!r} is not a valid DNS label"
    return None


def _validate_optional_domain(value: str) -> str | None:
    value = value.strip()
    if not value:
        return None
    return None if SUBDOMAIN_RE.match(value) else "invalid DNS domain name"


def ask_service(prompter: Prompter) -> dict[str, Any]:
    """Conduct the `service:` block interview and return its spec section."""
    prompter.note("Service identity")
    name = prompter.text(
        "Service name (DNS label, used as a prefix everywhere)",
        default="my-service",
        validate=_validate_dns_label,
    ).strip()
    description = prompter.text(
        "One-line description",
        default=f"Service {name}",
        validate=_validate_non_empty,
    ).strip()
    owner = prompter.text(
        "Team or person in charge",
        default="Platform Team",
        validate=_validate_non_empty,
    ).strip()
    owner_email = prompter.text(
        "Contact address (empty for none)",
        default="",
    ).strip()

    prompter.note("Environments (promotion order: dev -> staging -> prod)")
    raw_envs = prompter.text(
        "Environments, comma-separated",
        default=DEFAULT_ENVIRONMENTS,
        validate=_validate_environments,
    )
    env_names = [part.strip() for part in raw_envs.split(",") if part.strip()]

    production = ""
    if prompter.confirm("Is one of these environments production?", default=True):
        default_prod = DEFAULT_PRODUCTION if DEFAULT_PRODUCTION in env_names else env_names[-1]
        production = prompter.select(
            "Production environment",
            choices=[(name, name) for name in env_names],
            default=default_prod,
        )

    environments: list[dict[str, Any]] = []
    for env_name in env_names:
        domain = prompter.text(
            f"DNS domain of {env_name} (empty for none)",
            default="",
            validate=_validate_optional_domain,
        ).strip()
        entry: dict[str, Any] = {"name": env_name}
        if domain:
            entry["domain"] = domain
        if env_name == production:
            entry["production"] = True
        environments.append(entry)

    service: dict[str, Any] = {
        "name": name,
        "description": description,
        "owner": owner,
    }
    if owner_email:
        service["owner_email"] = owner_email
    service["environments"] = environments
    return service


def ask_domains(prompter: Prompter, available: list[tuple[str, str]]) -> list[str]:
    """Ask which domains to generate among those registered."""
    if not available:
        return []
    if len(available) == 1:
        name, label = available[0]
        return [name] if prompter.confirm(f"Generate the {label} domain?", default=True) else []
    return prompter.checkbox(
        "Domains to generate",
        choices=available,
        default=[name for name, _ in available],
    )
