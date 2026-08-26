"""Familles de regles : un fichier de regles, ses alertes, et ses pieges.

Une famille = un fichier `rules/<famille>.yml` par environnement, le fichier de
test unitaire qui va avec, et ce qu'il faut savoir pour ne pas se faire pieger.

L'ordre canonique suit celui d'un diagnostic : le service repond-il ? repond-il
correctement ? repond-il vite ? a-t-il de quoi tenir ? tient-il debout ? est-il
joignable de l'exterieur ?
"""

from __future__ import annotations

from dataclasses import dataclass

from forge.plugins.monitoring.catalog import alerts as alert_defs
from forge.plugins.monitoring.catalog.alerts import Alert
from forge.plugins.monitoring.enums import RuleFamily


@dataclass(frozen=True)
class Family:
    """Une famille de regles retenue ou non par la specification."""

    #: Identifiant employe dans `monitoring.rules` de forge.yml.
    name: str

    #: Resume d'une ligne.
    summary: str

    #: Description longue, affichee par `forge catalog monitoring <famille>`.
    details: str

    #: Alertes du fichier, dans l'ordre d'ecriture.
    alerts: tuple[Alert, ...]

    #: Exporters dont les metriques sont necessaires.
    exporters: tuple[str, ...] = ()

    #: Pieges mesures, affiches et repris en commentaire dans le fichier genere.
    traps: tuple[str, ...] = ()

    @property
    def needs_namespace(self) -> bool:
        """Vrai si une alerte de la famille cible un namespace Kubernetes."""
        return any(alerte.needs_namespace for alerte in self.alerts)

    @property
    def needs_probe(self) -> bool:
        """Vrai si une alerte de la famille repose sur une sonde blackbox."""
        return any(alerte.needs_probe for alerte in self.alerts)

    def option_descriptions(self) -> dict[str, str]:
        """Seuils reglables de la famille, au format attendu par `CatalogEntry`."""
        return {
            alerte.threshold_field: (
                f"{alerte.summary} — seuil en {alerte.threshold_unit}, "
                f"defaut {alerte.threshold_default}"
            )
            for alerte in self.alerts
            if alerte.threshold_field
        }


FAMILIES: tuple[Family, ...] = (
    Family(
        name=RuleFamily.AVAILABILITY.value,
        summary="La cible ne repond plus au collecteur",
        details=(
            "L'alerte la plus simple, et celle qu'on oublie le plus souvent : "
            "`up == 0`. Prometheus fabrique lui-meme la metrique `up` a chaque "
            "collecte, sans qu'aucun exporter n'ait a l'exposer.\n\n"
            "C'est la seule famille qui ne depend d'aucune convention de "
            "nommage : elle fonctionne des la premiere collecte."
        ),
        alerts=alert_defs.AVAILABILITY_ALERTS,
        traps=(
            "`up == 0` ne se declenche que si la cible est **connue** du "
            "collecteur. Une cible jamais declaree ne produit aucune serie, "
            "donc aucune alerte : le silence n'est pas la sante. C'est pourquoi "
            "les cibles sont ecrites dans la configuration plutot que "
            "decouvertes.",
            "Sans clause `for`, un redemarrage de deux minutes reveille "
            "quelqu'un. Avec un `for` trop long, une panne reelle attend. Cinq "
            "minutes est le compromis usuel, pas une verite.",
            "Une alerte qui se declenche pour **toutes** les instances a la "
            "fois designe presque toujours le collecteur ou le reseau, pas le "
            "service. Un recepteur qui ne fait pas la difference noie "
            "l'astreinte.",
        ),
    ),
    Family(
        name=RuleFamily.ERROR_RATE.value,
        summary="Trop de reponses en erreur serveur",
        details=(
            "Un ratio, jamais un compte : cent erreurs sur un million de "
            "requetes n'est pas la meme chose que cent erreurs sur deux cents.\n\n"
            "Le nom du compteur et celui du libelle de code de statut sont "
            "**configurables** : ils dependent de la bibliotheque cliente "
            "employee, et en deviner un produirait une alerte qui ne se "
            "declenche jamais."
        ),
        alerts=alert_defs.ERROR_RATE_ALERTS,
        exporters=("l'application elle-meme (client Prometheus)",),
        traps=(
            "Un ratio sur un denominateur nul donne `NaN`, et une comparaison "
            "avec `NaN` est fausse : l'alerte ne se declenche pas. Un service "
            "qui ne recoit plus **aucune** requete est donc invisible ici — "
            "c'est la famille `availability` qui le voit.",
            "`rate()` sur une fenetre plus courte que deux intervalles de "
            "collecte rend `NaN`. Avec une collecte toutes les 30 s, une "
            "fenetre de 5 minutes laisse de la marge ; une fenetre d'une "
            "minute n'en laisse aucune.",
            "Le libelle de statut n'est pas normalise : `status`, `code`, "
            "`status_code` selon la bibliotheque. Se tromper de nom donne une "
            "regle valide, acceptee par promtool, et definitivement muette.",
            "Compter les 5xx seulement laisse passer les timeouts cote client "
            "et les connexions refusees, qui ne produisent aucune reponse et "
            "donc aucune ligne dans le compteur.",
        ),
    ),
    Family(
        name=RuleFamily.LATENCY.value,
        summary="Le service repond trop lentement",
        details=(
            "Quantile 95 calcule sur un histogramme, pas une moyenne : une "
            "moyenne de temps de reponse cache exactement ce qu'on cherche.\n\n"
            "Exige un histogramme, pas un summary : `histogram_quantile` "
            "travaille sur les seaux `_bucket`, qu'un summary n'expose pas."
        ),
        alerts=alert_defs.LATENCY_ALERTS,
        exporters=("l'application elle-meme (client Prometheus)",),
        traps=(
            "`histogram_quantile` **interpole lineairement** dans le seau ou "
            "tombe le quantile. La precision du resultat ne depasse donc jamais "
            "celle du decoupage en seaux : avec des seaux 0.5 s / 2 s, aucun "
            "quantile ne peut valoir 1.2 s autrement que par interpolation.",
            "Si le quantile tombe dans le dernier seau (`+Inf`), la fonction "
            "rend la borne haute du seau precedent — jamais l'infini. Une "
            "latence catastrophique peut donc s'afficher comme egale a la borne "
            "du plus grand seau fini, et ne pas franchir un seuil place "
            "au-dessus.",
            "L'agregation `sum by (le)` est obligatoire avant "
            "`histogram_quantile` : appliquer la fonction a des seaux non "
            "agreges calcule un quantile par instance, ce qui n'a pas de sens "
            "quand on veut celui du service.",
            "Les seaux d'un histogramme sont **cumulatifs** : `le=\"2\"` compte "
            "aussi les observations sous 0.5 s. Ecrire une serie de test avec "
            "des seaux decroissants produit un histogramme invalide que "
            "Prometheus accepte et interprete de travers.",
        ),
    ),
    Family(
        name=RuleFamily.SATURATION.value,
        summary="Consommation proche des limites (memoire, CPU)",
        details=(
            "Deux alertes de nature differente, et la distinction compte : "
            "depasser sa limite memoire fait **tuer** le conteneur (OOMKill), "
            "depasser sa limite CPU le fait seulement ralentir (throttling).\n\n"
            "La memoire est donc surveillee en proportion de sa limite ; le CPU "
            "en valeur absolue, parce qu'un pod sans limite CPU est frequent et "
            "legitime."
        ),
        alerts=alert_defs.SATURATION_ALERTS,
        exporters=("cAdvisor, expose par le kubelet",),
        traps=(
            "Un conteneur **sans limite memoire** n'expose pas "
            "`container_spec_memory_limit_bytes`, ou l'expose a zero : la "
            "division ne donne aucun resultat, et l'alerte reste muette. "
            "L'absence d'alerte ne dit donc rien de la sante du pod.",
            "`container_memory_working_set_bytes` est la metrique que le "
            "kubelet compare a la limite pour decider d'un OOMKill — pas "
            "`container_memory_usage_bytes`, qui inclut le cache de fichiers "
            "recuperable et surestime largement la pression reelle.",
            "Le filtre `container!=\"\"` n'est pas cosmetique : cAdvisor expose "
            "aussi des series agregees au niveau du pod, avec un libelle "
            "`container` vide. Les compter deux fois double la consommation "
            "apparente.",
            "Le throttling CPU ne se voit pas dans "
            "`container_cpu_usage_seconds_total` : un pod bride consomme moins, "
            "donc parait sain. C'est "
            "`container_cpu_cfs_throttled_seconds_total` qui le montre.",
        ),
    ),
    Family(
        name=RuleFamily.RESTARTS.value,
        summary="Un conteneur redemarre en boucle",
        details=(
            "Un service peut repondre correctement et redemarrer toutes les "
            "dix minutes. Aucune des autres familles ne le voit : la "
            "disponibilite est bonne entre deux redemarrages, le taux d'erreur "
            "aussi.\n\n"
            "C'est souvent le premier signe visible d'une fuite memoire ou "
            "d'une sonde de vivacite mal reglee."
        ),
        alerts=alert_defs.RESTART_ALERTS,
        exporters=("kube-state-metrics",),
        traps=(
            "`kube_pod_container_status_restarts_total` est remis a zero quand "
            "le pod est recree — ce n'est pas un compteur monotone du point de "
            "vue du service. `increase()` gere la remise a zero d'une serie, "
            "mais pas la disparition d'une serie au profit d'une autre : un pod "
            "remplace fait perdre l'historique.",
            "Une sonde de vivacite trop stricte produit exactement cette "
            "alerte, alors que l'application va bien. Verifier le reglage de la "
            "sonde avant de chercher dans le code fait gagner des heures.",
            "kube-state-metrics doit tourner **et** etre collecte. Son absence "
            "rend cette famille silencieuse sans qu'aucune erreur n'apparaisse "
            "nulle part.",
        ),
    ),
    Family(
        name=RuleFamily.PROBE.value,
        summary="Sonde externe : joignabilite et expiration du certificat",
        details=(
            "La seule famille qui regarde le service **de l'exterieur**, comme "
            "un utilisateur. Un service peut tourner parfaitement et rester "
            "injoignable : DNS casse, ingress mal configure, certificat "
            "expire. Aucune metrique interne ne le montre.\n\n"
            "Exige un blackbox exporter joignable par le collecteur, et des URL "
            "a sonder declarees par environnement."
        ),
        alerts=alert_defs.PROBE_ALERTS,
        exporters=("blackbox exporter",),
        traps=(
            "La configuration de sonde du blackbox exporter est un ballet de "
            "`relabel_configs` : l'adresse a sonder passe par `__param_target`, "
            "puis devient `instance`, et `__address__` est finalement remplace "
            "par l'adresse de l'exporter. Sauter une etape fait sonder "
            "l'exporter lui-meme, qui repond toujours.",
            "`probe_ssl_earliest_cert_expiry` n'existe que pour les sondes "
            "**HTTPS**. Une URL en `http://` ne produit pas cette serie, et "
            "l'alerte de certificat reste muette sans que rien ne le signale.",
            "La sonde voit ce qu'un client voit depuis le reseau du "
            "collecteur. Si celui-ci est dans le cluster, elle ne teste ni le "
            "DNS public, ni le repartiteur de charge, ni le pare-feu — "
            "c'est-a-dire l'essentiel de ce qui casse.",
            "Un certificat renouvele automatiquement declenche quand meme "
            "l'alerte si le renouvellement echoue silencieusement. C'est le but ; "
            "ce n'est pas un faux positif.",
        ),
    ),
)

#: Familles indexees par nom.
BY_NAME: dict[str, Family] = {famille.name: famille for famille in FAMILIES}
