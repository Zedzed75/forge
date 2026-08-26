"""Projection de la specification vers ce que les gabarits consomment.

La partie interessante est `environments()` : **les regles sont projetees par
environnement**, parce que leurs seuils et leur namespace le sont. Une regle
partagee entre le developpement et la production devrait porter des filtres
larges et des seuils moyens, c'est-a-dire ne bien servir aucun des deux.
"""

from __future__ import annotations

from typing import Any

from forge.plugins.monitoring import render
from forge.plugins.monitoring.catalog.alerts import PANEL_EXPRESSIONS
from forge.plugins.monitoring.catalog.registry import all_alerts, selected
from forge.plugins.monitoring.constants import (
    BLACKBOX_JOB,
    BLACKBOX_MODULE,
    TEST_CONTAINER,
    TEST_INSTANCE,
    TEST_POD,
    TEST_PROBE_URL,
)


def scrape(spec: Any) -> dict[str, Any]:
    """Reglages de collecte."""
    collecte = spec.monitoring.scrape
    return {
        "interval": collecte.interval,
        "timeout": collecte.timeout,
        "metrics_path": collecte.metrics_path,
    }


def metrics(spec: Any) -> dict[str, str]:
    """Noms des metriques exposees par l'application."""
    noms = spec.monitoring.metrics
    return {
        "requests_total": noms.requests_total,
        "request_duration_seconds": noms.request_duration_seconds,
        "status_label": noms.status_label,
    }


def blackbox(spec: Any) -> dict[str, Any]:
    """Sonde externe : job, module et adresse de l'exporter."""
    return {
        "needed": spec.monitoring.needs_blackbox(),
        "job": BLACKBOX_JOB,
        "module": BLACKBOX_MODULE,
        "address": spec.monitoring.blackbox_address,
    }


def extras(spec: Any) -> dict[str, bool]:
    """Fichiers annexes demandes."""
    annexes = spec.monitoring.extras
    return {
        "makefile": annexes.makefile,
        "dashboard": annexes.dashboard,
    }


def families(spec: Any) -> list[dict[str, Any]]:
    """Familles retenues, avec ce que le README et les fichiers doivent en dire."""
    return [
        {
            "name": famille.name,
            "summary": famille.summary,
            "details": famille.details,
            "exporters": list(famille.exporters),
            "traps": list(famille.traps),
            "alert_names": [alerte.name for alerte in famille.alerts],
            "needs_namespace": famille.needs_namespace,
            "needs_probe": famille.needs_probe,
        }
        for famille in selected(spec.monitoring.family_names())
    ]


def default_thresholds() -> dict[str, Any]:
    """Seuils par defaut, lus dans le catalogue et non recopies ici."""
    return {
        alerte.threshold_field: alerte.threshold_default
        for alerte in all_alerts()
        if alerte.threshold_field
    }


def environments(spec: Any) -> list[dict[str, Any]]:
    """Une entree par environnement de `service.environments`, dans l'ordre."""
    return [_environment(spec, env) for env in spec.service.environments]


def _environment(spec: Any, env: Any) -> dict[str, Any]:
    """Projection d'un environnement : ce qu'on y surveille, et sous quels seuils."""
    monitoring = spec.monitoring
    surcharge = monitoring.overrides(env.name)
    namespace = surcharge.namespace or spec.service.name
    seuils = {**default_thresholds(), **_declared(surcharge)}

    valeurs: dict[str, Any] = {
        "job": spec.service.name,
        "service": spec.service.name,
        "env": env.name,
        "namespace": namespace,
        "requests": monitoring.metrics.requests_total,
        "duration": monitoring.metrics.request_duration_seconds,
        "status": monitoring.metrics.status_label,
        "blackbox_job": BLACKBOX_JOB,
        # Valeurs de test : elles n'ont besoin d'exister nulle part, promtool
        # fabrique les series lui-meme.
        "instance": TEST_INSTANCE,
        "pod": TEST_POD,
        "container": TEST_CONTAINER,
        "probe_url": TEST_PROBE_URL,
        **seuils,
        **_test_tokens(seuils),
    }

    prefixe = render.alert_prefix(spec.service.name)
    regles: dict[str, Any] = {}
    for famille in selected(monitoring.family_names()):
        alertes = []
        for alerte in famille.alerts:
            libelles = {
                "severity": alerte.severity.value,
                "service": spec.service.name,
                "env": env.name,
                **surcharge.labels,
            }
            projetee = render.project(
                alerte, valeurs, alert_prefix=prefixe, rule_labels=libelles
            )
            projetee["panel_expr"] = render.substitute(
                PANEL_EXPRESSIONS.get(alerte.name, alerte.expr),
                {**valeurs, "threshold": valeurs.get(alerte.threshold_field or "", "")},
            )
            alertes.append(projetee)
        regles[famille.name] = {
            "group": f"{spec.service.name}-{env.name}-{famille.name}",
            "summary": famille.summary,
            "traps": list(famille.traps),
            "alerts": alertes,
        }

    return {
        "name": env.name,
        "production": env.production,
        "domain": env.domain or "",
        "namespace": namespace,
        "targets": list(surcharge.targets),
        "probe_urls": list(surcharge.probe_urls),
        "labels": {**spec.service.labels, **surcharge.labels},
        "thresholds": {nom: render.format_number(valeur) for nom, valeur in seuils.items()},
        "rules": regles,
        # Ordre canonique des familles, pour que les gabarits n'aient pas a le
        # redecouvrir en parcourant un dict.
        "family_names": [famille.name for famille in selected(monitoring.family_names())],
    }


#: Limite memoire employee par les series de test, en octets. Une valeur ronde
#: et large : ce qui compte est le rapport a la consommation, pas l'echelle.
TEST_MEMORY_LIMIT = 1_000_000_000

#: Instant, en secondes, ou le test de certificat est evalue (20 minutes). Il
#: doit correspondre au `test_eval_time` de l'alerte : `time()` vaut cela dans
#: l'horloge synthetique de promtool, qui demarre a zero.
CERT_EVAL_SECONDS = 1200


def _test_tokens(seuils: dict[str, Any]) -> dict[str, Any]:
    """Valeurs des series de test, **derivees des seuils**.

    Une serie de test figee ne prouve la regle que pour le seuil qui avait cours
    le jour ou on l'a ecrite. C'est exactement ce que promtool a montre : un
    quantile de test a 1.9 s validait un seuil a 1 s et echouait sur un seuil a
    2 s, et une consommation CPU de 2 cœurs validait un seuil a 1.5 et echouait
    sur un seuil a 3.

    Chaque valeur ci-dessous est donc calculee pour depasser son seuil **quel
    qu'il soit**, avec une marge franche.
    """
    tokens: dict[str, Any] = {"memory_limit": TEST_MEMORY_LIMIT}

    taux = float(seuils.get("error_rate", 0.05))
    # Ratio vise : (1 + taux) / 2, donc strictement entre le taux et 1.
    tokens["error_other_step"] = max(1, round(1000 * (1 - taux) / (1 + taux)))

    latence = float(seuils.get("latency_p95_seconds", 1.0))
    # Borne haute du second seau. Le quantile 95 y tombe et vaut, par
    # interpolation lineaire, environ 1.94 fois le seuil.
    tokens["latency_high_le"] = latence * 2

    ratio = float(seuils.get("memory_ratio", 0.9))
    tokens["memory_used"] = int(TEST_MEMORY_LIMIT * (1 + ratio) / 2)

    cpu = float(seuils.get("cpu_cores", 1.5))
    # Pas du compteur : la derivee vaut (seuil + 1) cœurs.
    tokens["cpu_step"] = int(round((cpu + 1) * 60))

    redemarrages = int(seuils.get("restarts_per_hour", 3))
    # L'augmentation sur une heure vaut environ 60 fois le pas : on vise le
    # double du seuil, avec un pas d'au moins 1.
    tokens["restart_step"] = max(1, -(-redemarrages * 2 // 60))

    jours = int(seuils.get("certificate_days", 21))
    # Expiration placee a la moitie du seuil, dans l'horloge du test.
    tokens["cert_value"] = int(CERT_EVAL_SECONDS + jours * 86400 / 2)

    return tokens


def _declared(surcharge: Any) -> dict[str, Any]:
    """Seuils reellement renseignes pour cet environnement."""
    return surcharge.thresholds.declared() if surcharge.thresholds else {}


def dashboard_panels(spec: Any) -> list[dict[str, Any]]:
    """Panneaux du tableau de bord, un par alerte des familles retenues.

    Ils tracent la grandeur surveillee, pas la condition d'alerte : une courbe a
    deux valeurs — vrai ou faux — ne dit pas si on s'approche du seuil.

    Le tableau de bord est engendre pour le **premier** environnement declare,
    par convention : un tableau qui melangerait les environnements confondrait
    des grandeurs qui n'ont pas les memes seuils.
    """
    premier = environments(spec)[0]
    panneaux: list[dict[str, Any]] = []
    for nom_famille in premier["family_names"]:
        for alerte in premier["rules"][nom_famille]["alerts"]:
            panneaux.append(
                {
                    "title": alerte["summary"],
                    "family": nom_famille,
                    "expr": alerte["panel_expr"],
                    "alert": alerte["name"],
                    "threshold": alerte["threshold"],
                }
            )
    return panneaux
