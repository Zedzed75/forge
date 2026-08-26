"""Enumerations du domaine monitoring."""

from __future__ import annotations

from enum import Enum


class Severity(str, Enum):
    """Gravite portee par le label `severity` d'une alerte.

    Deux niveaux, pas cinq : une echelle fine ne survit pas au premier mois
    d'astreinte. La question est binaire — est-ce que quelqu'un doit se lever
    maintenant ?
    """

    #: Le service est degrade ou indisponible : reveiller quelqu'un.
    CRITICAL = "critical"

    #: Le service fonctionne mais quelque chose va mal finir : regarder demain.
    WARNING = "warning"


class RuleFamily(str, Enum):
    """Familles de regles d'alerte que le domaine peut engendrer.

    L'ordre de declaration est l'ordre canonique : il fixe l'ordre des fichiers
    de regles, celui des lignes du README et celui des cles de
    `domain.rule_slots`.

    Il suit la progression d'un diagnostic : le service repond-il ? repond-il
    correctement ? repond-il vite ? a-t-il de quoi tenir ? tient-il debout ?
    est-il joignable de l'exterieur ?
    """

    #: La cible ne repond plus du tout (`up == 0`).
    AVAILABILITY = "availability"

    #: Trop de reponses en erreur.
    ERROR_RATE = "error_rate"

    #: Reponses trop lentes (quantile 95 du temps de reponse).
    LATENCY = "latency"

    #: Consommation proche des limites (CPU, memoire).
    SATURATION = "saturation"

    #: Redemarrages en boucle des conteneurs.
    RESTARTS = "restarts"

    #: Sonde externe : le service est-il joignable, son certificat tient-il ?
    PROBE = "probe"
