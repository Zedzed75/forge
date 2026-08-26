"""Entretien du domaine monitoring.

L'ordre des questions suit celui de la decision : d'abord **ce qu'on surveille**
(les familles de regles), puis **ou** (les cibles, par environnement), puis les
annexes. Les questions sans objet ne sont pas posees — on ne demande d'URL a
sonder que si la famille `probe` est retenue.

Conformement a l'arbitrage R7 (PLAN.md), retourner `None` signifie « il n'y a
rien a generer », pas « l'utilisateur refuse le domaine » : ici, aucune famille
de regles retenue.
"""

from __future__ import annotations

from typing import Any

from forge.interview.prompter import Prompter
from forge.plugins.monitoring.catalog.registry import all_families
from forge.plugins.monitoring.constants import PROBE_URL_RE, TARGET_RE
from forge.plugins.monitoring.enums import RuleFamily
from forge.spec.service import ServiceSpec


def run(prompter: Prompter, service: ServiceSpec) -> dict[str, Any] | None:
    """Conduit l'entretien et retourne la section `monitoring:` de forge.yml."""
    prompter.note(
        "La supervision se decrit elle-meme : elle ne lit aucune autre section. "
        "Ce qu'elle surveille, vous le declarez ici."
    )

    familles = _ask_families(prompter)
    if not familles:
        prompter.note("Aucune famille retenue : le domaine monitoring n'est pas genere.")
        return None

    section: dict[str, Any] = {"rules": familles}

    metriques = _ask_metrics(prompter, familles)
    if metriques:
        section["metrics"] = metriques

    environnements = _ask_environments(prompter, service, familles)
    if environnements:
        section["environments"] = environnements

    prompter.note(
        "Les tests unitaires des alertes sont engendres dans tous les cas : une "
        "regle non testee est une regle dont personne ne sait si elle se declenche."
    )
    section["extras"] = {
        "dashboard": prompter.confirm("Engendrer un tableau de bord Grafana ?", default=True),
        "makefile": prompter.confirm("Ajouter un Makefile de raccourcis ?", default=True),
    }
    return section


def _ask_families(prompter: Prompter) -> list[str]:
    """Familles de regles retenues."""
    choix = [(famille.name, f"{famille.name} — {famille.summary}") for famille in all_families()]
    return prompter.checkbox(
        "Que faut-il surveiller ?", choix, [RuleFamily.AVAILABILITY.value]
    )


def _ask_metrics(prompter: Prompter, familles: list[str]) -> dict[str, Any]:
    """Noms des metriques applicatives, seulement si une famille en depend.

    Les metriques d'infrastructure (`up`, `container_*`, `probe_*`) ne sont pas
    demandees : leur nom est fixe, et le faire saisir inviterait a le changer
    pour un nom qui n'existe pas.
    """
    besoin = {RuleFamily.ERROR_RATE.value, RuleFamily.LATENCY.value} & set(familles)
    if not besoin:
        return {}

    prompter.note(
        "Ces noms dependent de la bibliotheque cliente de l'application. Se "
        "tromper produit une regle valide et definitivement muette."
    )
    metriques: dict[str, Any] = {}
    if RuleFamily.ERROR_RATE.value in familles:
        compteur = prompter.text("Compteur de requetes", default="http_requests_total")
        if compteur != "http_requests_total":
            metriques["requests_total"] = compteur
        libelle = prompter.text("Libelle portant le code de statut", default="status")
        if libelle != "status":
            metriques["status_label"] = libelle
    if RuleFamily.LATENCY.value in familles:
        histogramme = prompter.text(
            "Histogramme du temps de reponse (sans le suffixe _bucket)",
            default="http_request_duration_seconds",
        )
        if histogramme != "http_request_duration_seconds":
            metriques["request_duration_seconds"] = histogramme
    return metriques


def _ask_environments(
    prompter: Prompter, service: ServiceSpec, familles: list[str]
) -> dict[str, Any]:
    """Ce qui est surveille dans chaque environnement."""
    besoin_namespace = bool(
        {RuleFamily.SATURATION.value, RuleFamily.RESTARTS.value} & set(familles)
    )
    besoin_sonde = RuleFamily.PROBE.value in familles

    environnements: dict[str, Any] = {}
    for env in service.environments:
        prompter.note(f"Environnement « {env.name} » :")
        entree: dict[str, Any] = {}

        cibles = prompter.text(
            "  Cibles collectees, separees par des virgules (hote:port)",
            default="",
            validate=_cibles,
        )
        if cibles.strip():
            entree["targets"] = [morceau.strip() for morceau in cibles.split(",") if morceau.strip()]

        if besoin_namespace:
            namespace = prompter.text("  Namespace Kubernetes observe", default=service.name)
            if namespace != service.name:
                entree["namespace"] = namespace

        if besoin_sonde:
            defaut = f"https://{service.name}.{env.domain}" if env.domain else ""
            urls = prompter.text(
                "  URL sondees de l'exterieur, separees par des virgules",
                default=defaut,
                validate=_urls,
            )
            if urls.strip():
                entree["probe_urls"] = [
                    morceau.strip() for morceau in urls.split(",") if morceau.strip()
                ]

        if entree:
            environnements[env.name] = entree
    return environnements


def _cibles(valeur: str) -> str | None:
    """Valide une liste de cibles `hote:port` separees par des virgules."""
    for morceau in (part.strip() for part in valeur.split(",")):
        if morceau and not TARGET_RE.match(morceau):
            return f"'{morceau}' n'est pas une cible 'hote:port'."
    return None


def _urls(valeur: str) -> str | None:
    """Valide une liste d'URL separees par des virgules."""
    for morceau in (part.strip() for part in valeur.split(",")):
        if morceau and not PROBE_URL_RE.match(morceau):
            return f"'{morceau}' n'est pas une URL http:// ou https://."
    return None
