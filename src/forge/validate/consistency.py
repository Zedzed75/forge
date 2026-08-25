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

#: **Vocabulaire partage des facettes.**
#:
#: Le coeur compare les facettes **par leur nom** : ce nom est donc un espace de
#: noms partage entre tous les plugins, et deux domaines qui emploient le meme
#: nom affirment parler de la meme chose. Sans regle explicite, la collision est
#: silencieuse et produit un faux positif — mesure en phase 5 : Ansible
#: declarait `hosts` pour ses machines d'inventaire, Helm pour ses hotes
#: d'Ingress, et `forge validate` echouait sur un projet parfaitement coherent.
#:
#: Un plugin qui declare une facette hors de ce vocabulaire n'est compare a
#: personne : c'est sans danger, mais sans effet non plus. Pour qu'une facette
#: serve, il faut l'ajouter ici **et** s'accorder sur son sens.
FACET_VOCABULARY: dict[str, str] = {
    "ingress_hosts": "noms de domaine par lesquels le service est joignable de l'exterieur",
    "inventory_hosts": "machines nommees dans un inventaire de configuration",
    "namespaces": "cloisons logiques dans lesquelles le service est deploye",
    "groups": "regroupements de machines partageant un role",
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
    """Compare ce que **chaque domaine materialise reellement**.

    `Projection.environments` ne recopie pas `service.environments` : un domaine
    y declare les environnements pour lesquels il produit quelque chose. Un
    environnement qu'Ansible ignore alors que Helm y deploie est donc visible
    ici, et nulle part ailleurs — c'est precisement ce que la comparaison de
    projections apporte, et qu'aucun domaine ne peut voir seul.
    """
    issues: list[Issue] = []
    domains = _sorted_domains(projections)
    tous = sorted({env for domain in domains for env in projections[domain].environments})

    for env in tous:
        absents = [d for d in domains if env not in projections[d].environments]
        if not absents:
            continue
        presents = [d for d in domains if env in projections[d].environments]
        issues.append(
            Issue(
                level="warning",
                message=(
                    f"l'environnement '{env}' est materialise par "
                    f"{', '.join(presents)} mais pas par {', '.join(absents)}"
                ),
                hint=(
                    f"si c'est voulu, rien a faire ; sinon, completez la section "
                    f"de {absents[0]} pour '{env}', ou retirez-le de "
                    "service.environments"
                ),
                domains=tuple(domains),
            )
        )

    # L'ordre reste porteur de sens : il decrit la promotion dev -> prod.
    reference_domain = domains[0]
    reference = [e for e in projections[reference_domain].environments]
    for domain in domains[1:]:
        current = [e for e in projections[domain].environments]
        communs_ref = [e for e in reference if e in current]
        communs_cur = [e for e in current if e in reference]
        if communs_ref != communs_cur:
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
