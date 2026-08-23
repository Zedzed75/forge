"""Controles inter-domaines, sans aucune connaissance de domaine (decision Q4).

Chaque plugin declare une `Projection` : ce qu'il affirme produire, exprime en
vocabulaire neutre. Le coeur ne fait que **comparer ces declarations** — deux
domaines qui declarent la meme facette doivent declarer la meme valeur. Un
troisieme plugin herite donc de ces controles sans que le coeur change
(DESIGN.md §6.4).
"""

from __future__ import annotations

from forge.plugins_api.types import Issue, Projection

#: Une facette n'est comparee que si au moins ce nombre de domaines la declare.
MIN_DECLARERS = 2


def _sorted_domains(projections: dict[str, Projection]) -> list[str]:
    return sorted(projections)


def _check_service_name(projections: dict[str, Projection]) -> list[Issue]:
    values: dict[str, list[str]] = {}
    for domain in _sorted_domains(projections):
        values.setdefault(projections[domain].service_name, []).append(domain)
    if len(values) <= 1:
        return []
    detail = "; ".join(
        f"{name!r} pour {', '.join(domains)}" for name, domains in sorted(values.items())
    )
    return [
        Issue(
            level="error",
            message=f"les domaines n'emploient pas le meme nom de service : {detail}",
            hint="service.name doit etre repris tel quel par chaque domaine",
            domains=tuple(_sorted_domains(projections)),
        )
    ]


def _check_environments(projections: dict[str, Projection]) -> list[Issue]:
    issues: list[Issue] = []
    domains = _sorted_domains(projections)
    reference_domain = domains[0]
    reference = projections[reference_domain].environments
    for domain in domains[1:]:
        current = projections[domain].environments
        if set(current) != set(reference):
            missing = sorted(set(reference) - set(current))
            extra = sorted(set(current) - set(reference))
            parts = []
            if missing:
                parts.append(f"absents de {domain} : {', '.join(missing)}")
            if extra:
                parts.append(f"absents de {reference_domain} : {', '.join(extra)}")
            issues.append(
                Issue(
                    level="error",
                    message=(
                        f"environnements incoherents entre {reference_domain} et "
                        f"{domain} ({' ; '.join(parts)})"
                    ),
                    hint="tous les domaines partent de service.environments",
                    domains=(reference_domain, domain),
                )
            )
        elif current != reference:
            issues.append(
                Issue(
                    level="warning",
                    message=(
                        f"{domain} ordonne les environnements autrement que "
                        f"{reference_domain} ({', '.join(current)} vs "
                        f"{', '.join(reference)})"
                    ),
                    hint="l'ordre de service.environments est celui de la promotion",
                    domains=(reference_domain, domain),
                )
            )
    return issues


def _check_labels(projections: dict[str, Projection]) -> list[Issue]:
    issues: list[Issue] = []
    seen: dict[str, tuple[str, str]] = {}  # cle -> (valeur, domaine)
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
                            f"label {key!r} contradictoire : {known_value!r} dans "
                            f"{known_domain}, {value!r} dans {domain}"
                        ),
                        hint="les labels partages viennent de service.labels",
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
        if len(domains) < MIN_DECLARERS:
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
                parts.append(f"absent(s) de {domain} : {', '.join(missing)}")
            if extra:
                parts.append(f"absent(s) de {reference_domain} : {', '.join(extra)}")
            issues.append(
                Issue(
                    level="error",
                    message=(
                        f"facette « {facet} » divergente entre {reference_domain} et "
                        f"{domain} ({' ; '.join(parts)})"
                    ),
                    hint=(
                        "les deux domaines decrivent la meme realite : alignez la "
                        "specification, ou cessez de la declarer des deux cotes"
                    ),
                    domains=(reference_domain, domain),
                )
            )
    return issues


def compare_projections(projections: dict[str, Projection]) -> list[Issue]:
    """Compare les projections de tous les domaines et retourne les constats.

    Aucune regle « si ansible alors… » : uniquement des egalites entre ce que
    les domaines declarent.
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
    """Met en forme les constats, erreurs d'abord."""
    if not issues:
        return "coherence inter-domaines : aucun ecart"
    lines: list[str] = []
    for issue in sorted(issues, key=lambda i: (i.level != "error", i.message)):
        mark = "ERREUR " if issue.level == "error" else "AVERTIR"
        scope = f" [{', '.join(issue.domains)}]" if issue.domains else ""
        lines.append(f"[{mark}]{scope} {issue.message}")
        if issue.hint:
            lines.append(f"          -> {issue.hint}")
    return "\n".join(lines)


def has_errors(issues: list[Issue]) -> bool:
    """Vrai si au moins un constat est de niveau erreur."""
    return any(issue.level == "error" for issue in issues)
