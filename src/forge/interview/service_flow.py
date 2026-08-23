"""Entretien du bloc `service:` — la seule partie conduite par le coeur.

Les questions propres a un domaine appartiennent a son plugin, via le hook
`forge_interview` (DESIGN.md §7). Ici, uniquement l'identite du service et ses
environnements : ce que tous les domaines doivent voir de la meme facon.
"""

from __future__ import annotations

from typing import Any

from forge.interview.prompter import Prompter
from forge.spec.names import DNS_LABEL_RE, SUBDOMAIN_RE

#: Environnements proposes par defaut, dans l'ordre de promotion.
DEFAULT_ENVIRONMENTS = "dev,staging,prod"

#: Environnement considere comme la production si l'utilisateur ne dit rien.
DEFAULT_PRODUCTION = "prod"


def _validate_dns_label(value: str) -> str | None:
    if not DNS_LABEL_RE.match(value.strip()):
        return "attendu un label DNS : minuscules, chiffres et tirets internes"
    return None


def _validate_non_empty(value: str) -> str | None:
    return None if value.strip() else "valeur obligatoire"


def _validate_environments(value: str) -> str | None:
    names = [part.strip() for part in value.split(",") if part.strip()]
    if not names:
        return "au moins un environnement est requis"
    if len(set(names)) != len(names):
        return "noms d'environnement en double"
    for name in names:
        if not DNS_LABEL_RE.match(name):
            return f"{name!r} n'est pas un label DNS valide"
    return None


def _validate_optional_domain(value: str) -> str | None:
    value = value.strip()
    if not value:
        return None
    return None if SUBDOMAIN_RE.match(value) else "nom de domaine DNS invalide"


def ask_service(prompter: Prompter) -> dict[str, Any]:
    """Conduit l'entretien du bloc `service:` et retourne sa section de spec."""
    prompter.note("Identite du service")
    name = prompter.text(
        "Nom du service (label DNS, sert de prefixe partout)",
        default="mon-service",
        validate=_validate_dns_label,
    ).strip()
    description = prompter.text(
        "Description en une ligne",
        default=f"Service {name}",
        validate=_validate_non_empty,
    ).strip()
    owner = prompter.text(
        "Equipe ou personne responsable",
        default="Equipe Plateforme",
        validate=_validate_non_empty,
    ).strip()
    owner_email = prompter.text(
        "Adresse de contact (vide pour aucune)",
        default="",
    ).strip()

    prompter.note("Environnements (ordre de promotion : dev -> staging -> prod)")
    raw_envs = prompter.text(
        "Environnements, separes par des virgules",
        default=DEFAULT_ENVIRONMENTS,
        validate=_validate_environments,
    )
    env_names = [part.strip() for part in raw_envs.split(",") if part.strip()]

    production = ""
    if prompter.confirm("Un de ces environnements est-il la production ?", default=True):
        default_prod = DEFAULT_PRODUCTION if DEFAULT_PRODUCTION in env_names else env_names[-1]
        production = prompter.select(
            "Environnement de production",
            choices=[(name, name) for name in env_names],
            default=default_prod,
        )

    environments: list[dict[str, Any]] = []
    for env_name in env_names:
        domain = prompter.text(
            f"Domaine DNS de {env_name} (vide pour aucun)",
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
    """Demande quels domaines generer parmi ceux enregistres."""
    if not available:
        return []
    if len(available) == 1:
        name, label = available[0]
        return [name] if prompter.confirm(f"Generer le domaine {label} ?", default=True) else []
    return prompter.checkbox(
        "Domaines a generer",
        choices=available,
        default=[name for name, _ in available],
    )
