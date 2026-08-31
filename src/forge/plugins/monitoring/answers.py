"""Projection vers le dict `domain` de copier, et controles croises.

Meme contrat que les trois autres domaines : sortie JSON-serialisable, ordre
fige, aucun objet pydantic. Le calcul vit dans :mod:`derive` et :mod:`tree`.

Les controles croises de ce domaine ont une couleur particuliere : presque tous
sont des **avertissements**, et presque tous disent la meme chose sous des
formes differentes — « cette regle ne se declenchera jamais ». C'est le mode de
defaillance propre a la supervision : rien n'echoue, rien ne casse, et personne
n'est prevenu le jour ou il aurait fallu l'etre.
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
    """Construit le dict `domain` passe a copier pour le domaine monitoring."""
    service = spec.service
    monitoring = spec.monitoring
    familles = derive.families(spec)

    return {
        # -- collecte ------------------------------------------------------------
        "scrape": derive.scrape(spec),
        "metrics": derive.metrics(spec),
        "blackbox": derive.blackbox(spec),
        "job_name": service.name,
        "alert_prefix": render.alert_prefix(service.name),
        # -- familles retenues ----------------------------------------------------
        "families": familles,
        "family_names": [famille["name"] for famille in familles],
        # -- environnements --------------------------------------------------------
        "environments": derive.environments(spec),
        "env_names": [env.name for env in service.environments],
        "default_env": service.environments[0].name,
        # -- cles courtes, lues UNIQUEMENT par les chemins de gabarit -------------
        # Windows plafonne un chemin a 260 caracteres, et copier clone le depot
        # de gabarit dans un repertoire temporaire avant de rendre : un nom de
        # fichier portant `[% yield env from domain.environments %]` deux fois
        # depassait la limite. Ces listes ne portent qu'un nom ; les gabarits
        # relisent l'entree complete par `selectattr`.
        "envs": [{"name": env["name"]} for env in derive.environments(spec)],
        "fams": [{"name": famille["name"]} for famille in familles],
        "dash": tree.dashboard_slot(spec),
        # -- tableau de bord --------------------------------------------------------
        "dashboard_file": tree.dashboard_file(service.name),
        "dashboard_panels": (
            derive.dashboard_panels(spec) if monitoring.extras.dashboard else []
        ),
        # -- annexes et documentation -------------------------------------------------
        "extras": derive.extras(spec),
        "root_files": tree.root_files(spec),
        "expected_paths": tree.expected_paths(spec),
    }


# ---------------------------------------------------------------------------
# Controles croises
# ---------------------------------------------------------------------------


def cross_check(spec: Any) -> list[Issue]:
    """Controles que `MonitoringSpec` ne peut pas faire : elle ne voit pas `service:`."""
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
    """Signale un environnement dont aucune cible n'est collectee.

    C'est le defaut le plus grave que ce domaine puisse produire, et le plus
    silencieux : sans cible, aucune serie n'existe, donc `up == 0` ne peut pas
    se declencher. Le tableau de bord est vide et tout parait calme.
    """
    return [
        Issue(
            level="warning",
            message=(
                f"aucune cible de collecte n'est declaree pour l'environnement "
                f"'{env.name}' : rien n'y sera surveille, et aucune alerte ne "
                "pourra se declencher."
            ),
            hint=(
                f"Renseignez monitoring.environments.{env.name}.targets "
                "(par exemple ['api.example.net:9090'])."
            ),
            domains=(DOMAIN_NAME,),
        )
        for env in spec.service.environments
        if not monitoring.overrides(env.name).targets
    ]


def _check_probes(spec: Any, monitoring: Any) -> list[Issue]:
    """Controles propres a la famille de sondes externes."""
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
                        f"la famille 'probe' est retenue mais aucune URL n'est "
                        f"sondee pour l'environnement '{env.name}' : ses alertes "
                        "ne se declencheront jamais."
                    ),
                    hint=(
                        f"Renseignez monitoring.environments.{env.name}.probe_urls, "
                        "ou retirez 'probe' de monitoring.rules."
                    ),
                    domains=(DOMAIN_NAME,),
                )
            )
            continue
        en_clair = sorted(url for url in urls if url.startswith("http://"))
        if en_clair:
            issues.append(
                Issue(
                    level="warning",
                    message=(
                        f"environnement '{env.name}' : les URL sondees en http:// "
                        f"({', '.join(en_clair)}) n'exposent pas "
                        "probe_ssl_earliest_cert_expiry ; l'alerte d'expiration "
                        "de certificat restera muette pour elles."
                    ),
                    hint="Sondez l'URL en https:// si le service en expose une.",
                    domains=(DOMAIN_NAME,),
                )
            )
    return issues


def _check_namespaces(spec: Any, monitoring: Any) -> list[Issue]:
    """Signale un namespace non declare la ou une famille en depend.

    Le repli sur le nom du service est raisonnable, mais il est faux des que le
    namespace suit une autre convention — et une regle qui filtre sur un
    namespace inexistant ne rend aucune serie, donc ne se declenche jamais.
    """
    concernees = [
        famille.name
        for famille in selected(monitoring.family_names())
        if famille.needs_namespace
    ]
    if not concernees:
        return []
    return [
        Issue(
            level="warning",
            message=(
                f"environnement '{env.name}' : les familles "
                f"{', '.join(concernees)} filtrent sur un namespace, et aucun "
                f"n'est declare ; forge emploie '{spec.service.name}'."
            ),
            hint=(
                f"Renseignez monitoring.environments.{env.name}.namespace pour "
                "lever le doute."
            ),
            domains=(DOMAIN_NAME,),
        )
        for env in spec.service.environments
        if monitoring.overrides(env.name).namespace is None
    ]


def _check_orphan_thresholds(monitoring: Any) -> list[Issue]:
    """Signale un seuil regle pour une famille absente de `monitoring.rules`.

    Une valeur soigneusement choisie et silencieusement ignoree est pire qu'une
    erreur : rien ne la distingue d'une valeur appliquee.
    """
    from forge.plugins.monitoring.catalog.registry import all_families

    retenues = set(monitoring.family_names())
    proprietaire = {
        alerte.threshold_field: famille.name
        for famille in all_families()
        for alerte in famille.alerts
        if alerte.threshold_field
    }

    issues: list[Issue] = []
    for nom_env in sorted(monitoring.environments):
        seuils = monitoring.environments[nom_env].thresholds
        if seuils is None:
            continue
        for champ in sorted(seuils.declared()):
            famille = proprietaire.get(champ, "")
            if not famille or famille in retenues:
                continue
            issues.append(
                Issue(
                    level="warning",
                    message=(
                        f"monitoring.environments.{nom_env}.thresholds.{champ} "
                        f"regle un seuil de la famille '{famille}', absente de "
                        "monitoring.rules : cette valeur ne sera pas appliquee."
                    ),
                    hint=(
                        f"Ajoutez '{famille}' a monitoring.rules, ou retirez "
                        f"le seuil {champ}."
                    ),
                    domains=(DOMAIN_NAME,),
                )
            )
    return issues


def probe_hosts(spec: Any) -> tuple[str, ...]:
    """Noms d'hote sondes, tous environnements confondus, tries.

    Alimente la facette `ingress_hosts` du vocabulaire partage : c'est par elle
    que forge peut dire « le chart expose boutique.example.net, la sonde regarde
    api.example.net » sans qu'aucun domaine ne connaisse l'autre.
    """
    hotes: set[str] = set()
    for surcharge in spec.monitoring.environments.values():
        for url in surcharge.probe_urls:
            sans_schema = url.split("://", 1)[-1]
            hote = sans_schema.split("/", 1)[0].split(":", 1)[0]
            if hote:
                hotes.add(hote)
    return tuple(sorted(hotes))
