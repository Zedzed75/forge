"""Les alertes elles-memes : expression PromQL, et de quoi la mettre a l'epreuve.

Chaque alerte porte **son propre test unitaire** : une serie temporelle
synthetique, l'instant d'evaluation, et les libelles attendus. `promtool test
rules` fait tourner l'un contre l'autre. Une regle d'alerte non testee est une
regle dont personne ne sait si elle se declenche, et on ne l'apprend que le jour
ou elle aurait du le faire.

Les jetons `@…@` sont remplaces a la projection (`derive.py`). Ni `str.format`
ni `string.Template` ne conviennent ici : PromQL est plein d'accolades
(`{job="x"}`) et les annotations sont plein de `$` (`{{ $labels.pod }}`). Un
marqueur qui n'existe dans aucun des deux langages evite toute regle
d'echappement.

**Aucune metrique inventee.** `up` vient de Prometheus ; `container_*` de
cAdvisor ; `kube_pod_container_status_restarts_total` de kube-state-metrics ;
`probe_*` du blackbox exporter. Les noms propres a l'application — compteur de
requetes, histogramme de duree — sont **configurables**, parce qu'ils dependent
de la bibliotheque cliente employee et qu'en deviner un serait engendrer une
alerte qui ne se declenchera jamais.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from forge.plugins.monitoring.enums import Severity


@dataclass(frozen=True)
class Alert:
    """Une regle d'alerte, et le test unitaire qui la met a l'epreuve."""

    #: Suffixe du nom d'alerte. Le nom complet est `<Service><Suffixe>`.
    name: str

    #: Expression PromQL, jetons `@…@` compris.
    expr: str

    #: Duree pendant laquelle la condition doit tenir avant de declencher.
    #: Sans elle, toute oscillation devient une alerte.
    for_duration: str

    #: Gravite portee par le label `severity`.
    severity: Severity

    #: Phrase courte : ce qui ne va pas.
    summary: str

    #: Phrase longue : ou, depuis quand, et sous quel seuil. Peut employer
    #: `{{ $labels.<nom> }}`, que le test resout mecaniquement.
    description: str

    #: Champ de `ThresholdsSpec` qui alimente `@threshold@`, ou None.
    threshold_field: str | None = None

    #: Valeur par defaut du seuil.
    threshold_default: float | int | None = None

    #: Unite du seuil, pour les textes et le README.
    threshold_unit: str = ""

    #: Series d'entree du test unitaire : (serie, valeurs), jetons compris.
    test_series: tuple[tuple[str, str], ...] = ()

    #: Instant d'evaluation du test. Doit depasser `for_duration`.
    test_eval_time: str = "10m"

    #: Libelles que l'expression laisse survivre, tels que le test les attend.
    #: Une agregation `sum(...)` sans `by` n'en laisse aucun.
    test_result_labels: dict[str, str] = field(default_factory=dict)

    #: Vrai si l'alerte a besoin d'un namespace Kubernetes.
    needs_namespace: bool = False

    #: Vrai si l'alerte a besoin d'une sonde blackbox.
    needs_probe: bool = False


AVAILABILITY_ALERTS: tuple[Alert, ...] = (
    Alert(
        name="CibleInjoignable",
        expr='up{job="@job@"} == 0',
        for_duration="5m",
        severity=Severity.CRITICAL,
        summary="La cible ne repond plus au collecteur",
        description=(
            "L'instance {{ $labels.instance }} du job {{ $labels.job }} ne "
            "repond plus depuis 5 minutes."
        ),
        test_series=(('up{job="@job@", instance="@instance@"}', "0+0x10"),),
        test_eval_time="6m",
        test_result_labels={"job": "@job@", "instance": "@instance@"},
    ),
)

ERROR_RATE_ALERTS: tuple[Alert, ...] = (
    Alert(
        name="TauxErreurEleve",
        expr=(
            'sum(rate(@requests@{job="@job@", @status@=~"5.."}[5m]))\n'
            "  /\n"
            'sum(rate(@requests@{job="@job@"}[5m]))\n'
            "  > @threshold@"
        ),
        for_duration="10m",
        severity=Severity.CRITICAL,
        summary="Trop de reponses en erreur",
        description=(
            "Plus de @threshold_pct@ % des reponses du service sont en erreur "
            "serveur depuis 10 minutes."
        ),
        threshold_field="error_rate",
        threshold_default=0.05,
        threshold_unit="proportion (0.05 = 5 %)",
        # Les pas sont calcules a partir du seuil : une serie figee ne
        # prouverait la regle que pour le seuil qui avait cours le jour ou on
        # l'a ecrite. Le ratio vise (1 + seuil) / 2, donc strictement entre le
        # seuil et 1, pour tout seuil admissible.
        test_series=(
            ('@requests@{job="@job@", @status@="500"}', "0+1000x20"),
            ('@requests@{job="@job@", @status@="200"}', "0+@error_other_step@x20"),
        ),
        test_eval_time="15m",
        # `sum(...)` sans `by` ne laisse survivre aucun libelle : l'alerte ne
        # porte que ceux que la regle ajoute.
        test_result_labels={},
    ),
)

LATENCY_ALERTS: tuple[Alert, ...] = (
    Alert(
        name="LatenceElevee",
        expr=(
            "histogram_quantile(0.95,\n"
            '  sum by (le) (rate(@duration@_bucket{job="@job@"}[5m]))\n'
            ") > @threshold@"
        ),
        for_duration="10m",
        severity=Severity.WARNING,
        summary="Le service repond trop lentement",
        description=(
            "Le quantile 95 du temps de reponse depasse @threshold@ seconde(s) "
            "depuis 10 minutes."
        ),
        threshold_field="latency_p95_seconds",
        threshold_default=1.0,
        threshold_unit="secondes",
        # Trois seaux cumulatifs, dont les bornes suivent le seuil : 10
        # observations sous le seuil, 90 entre le seuil et son double, aucune
        # au-dela. Le quantile 95 tombe dans le second seau et vaut, par
        # interpolation, environ 1.94 fois le seuil — donc au-dessus, quel que
        # soit le seuil.
        test_series=(
            ('@duration@_bucket{job="@job@", le="@threshold@"}', "0+10x20"),
            ('@duration@_bucket{job="@job@", le="@latency_high_le@"}', "0+100x20"),
            ('@duration@_bucket{job="@job@", le="+Inf"}', "0+100x20"),
        ),
        test_eval_time="15m",
        test_result_labels={},
    ),
)

SATURATION_ALERTS: tuple[Alert, ...] = (
    Alert(
        name="MemoireProcheDeLaLimite",
        expr=(
            'container_memory_working_set_bytes{namespace="@namespace@", container!=""}\n'
            "  /\n"
            'container_spec_memory_limit_bytes{namespace="@namespace@", container!=""}\n'
            "  > @threshold@"
        ),
        for_duration="10m",
        severity=Severity.WARNING,
        summary="Un conteneur approche de sa limite memoire",
        description=(
            "Le conteneur {{ $labels.container }} du pod {{ $labels.pod }} "
            "depasse @threshold_pct@ % de sa limite memoire depuis 10 minutes. "
            "Un depassement effectif provoque un OOMKill, pas un ralentissement."
        ),
        threshold_field="memory_ratio",
        threshold_default=0.9,
        threshold_unit="proportion de la limite (0.9 = 90 %)",
        # La consommation visee est (1 + seuil) / 2 de la limite : strictement
        # au-dessus du seuil, quel que soit celui-ci.
        test_series=(
            (
                "container_memory_working_set_bytes"
                '{namespace="@namespace@", pod="@pod@", container="@container@"}',
                "@memory_used@+0x20",
            ),
            (
                "container_spec_memory_limit_bytes"
                '{namespace="@namespace@", pod="@pod@", container="@container@"}',
                "@memory_limit@+0x20",
            ),
        ),
        test_eval_time="15m",
        test_result_labels={
            "namespace": "@namespace@",
            "pod": "@pod@",
            "container": "@container@",
        },
        needs_namespace=True,
    ),
    Alert(
        name="CpuEleve",
        expr=(
            "sum by (pod) (\n"
            "  rate(container_cpu_usage_seconds_total"
            '{namespace="@namespace@", container!=""}[5m])\n'
            ") > @threshold@"
        ),
        for_duration="10m",
        severity=Severity.WARNING,
        summary="Un pod consomme durablement beaucoup de CPU",
        description=(
            "Le pod {{ $labels.pod }} consomme plus de @threshold@ cœur(s) "
            "depuis 10 minutes."
        ),
        threshold_field="cpu_cores",
        threshold_default=1.5,
        threshold_unit="cœurs",
        # Le pas du compteur vaut (seuil + 1) x 60 : la derivee depasse donc
        # le seuil d'un cœur entier, quel que soit le seuil.
        test_series=(
            (
                "container_cpu_usage_seconds_total"
                '{namespace="@namespace@", pod="@pod@", container="@container@"}',
                "0+@cpu_step@x20",
            ),
        ),
        test_eval_time="15m",
        # `sum by (pod)` ne laisse survivre que `pod`.
        test_result_labels={"pod": "@pod@"},
        needs_namespace=True,
    ),
)

RESTART_ALERTS: tuple[Alert, ...] = (
    Alert(
        name="RedemarragesEnBoucle",
        expr=(
            "increase(\n"
            "  kube_pod_container_status_restarts_total"
            '{namespace="@namespace@"}[1h]\n'
            ") > @threshold@"
        ),
        for_duration="5m",
        severity=Severity.WARNING,
        summary="Un conteneur redemarre en boucle",
        description=(
            "Le conteneur {{ $labels.container }} du pod {{ $labels.pod }} a "
            "redemarre plus de @threshold@ fois en une heure."
        ),
        threshold_field="restarts_per_hour",
        threshold_default=3,
        threshold_unit="redemarrages par heure",
        # Le pas est choisi pour que l'augmentation sur une heure vaille au
        # moins le double du seuil.
        test_series=(
            (
                "kube_pod_container_status_restarts_total"
                '{namespace="@namespace@", pod="@pod@", container="@container@"}',
                "0+@restart_step@x70",
            ),
        ),
        test_eval_time="70m",
        test_result_labels={
            "namespace": "@namespace@",
            "pod": "@pod@",
            "container": "@container@",
        },
        needs_namespace=True,
    ),
)

PROBE_ALERTS: tuple[Alert, ...] = (
    Alert(
        name="SondeExterneEnEchec",
        expr='probe_success{job="@blackbox_job@"} == 0',
        for_duration="5m",
        severity=Severity.CRITICAL,
        summary="Le service n'est plus joignable de l'exterieur",
        description=(
            "La sonde externe sur {{ $labels.instance }} echoue depuis 5 "
            "minutes. Le service peut tourner et rester injoignable : c'est "
            "precisement ce que cette sonde voit et que les autres ne voient pas."
        ),
        test_series=(
            (
                'probe_success{job="@blackbox_job@", instance="@probe_url@"}',
                "0+0x10",
            ),
        ),
        test_eval_time="6m",
        test_result_labels={"job": "@blackbox_job@", "instance": "@probe_url@"},
        needs_probe=True,
    ),
    Alert(
        name="CertificatBientotExpire",
        expr=(
            "(\n"
            '  probe_ssl_earliest_cert_expiry{job="@blackbox_job@"} - time()\n'
            ") / 86400 < @threshold@"
        ),
        for_duration="15m",
        severity=Severity.WARNING,
        summary="Un certificat TLS approche de son expiration",
        description=(
            "Le certificat servi sur {{ $labels.instance }} expire dans moins "
            "de @threshold@ jours. Un certificat expire ne previent pas : il "
            "casse toutes les connexions d'un coup."
        ),
        threshold_field="certificate_days",
        threshold_default=21,
        threshold_unit="jours avant expiration",
        # La date d'expiration est placee a la moitie du seuil : l'alerte doit
        # donc se declencher, quel que soit le nombre de jours demande.
        test_series=(
            (
                "probe_ssl_earliest_cert_expiry"
                '{job="@blackbox_job@", instance="@probe_url@"}',
                "@cert_value@+0x25",
            ),
        ),
        test_eval_time="20m",
        test_result_labels={"job": "@blackbox_job@", "instance": "@probe_url@"},
        needs_probe=True,
    ),
)


#: Expression a **afficher** pour chaque alerte, sans sa comparaison au seuil.
#:
#: Un tableau de bord qui trace la condition d'alerte ne montre qu'une courbe a
#: deux valeurs : vrai ou faux. Ce qu'on veut voir, c'est la grandeur elle-meme
#: et sa distance au seuil — d'ou cette seconde expression, qui est la premiere
#: privee de sa derniere comparaison.
#:
#: Indexee par nom d'alerte : une alerte absente de cette table est tracee par
#: son expression complete, ce qui reste juste, seulement moins lisible.
PANEL_EXPRESSIONS: dict[str, str] = {
    "CibleInjoignable": 'up{job="@job@"}',
    "TauxErreurEleve": (
        'sum(rate(@requests@{job="@job@", @status@=~"5.."}[5m]))\n'
        "  /\n"
        'sum(rate(@requests@{job="@job@"}[5m]))'
    ),
    "LatenceElevee": (
        "histogram_quantile(0.95,\n"
        '  sum by (le) (rate(@duration@_bucket{job="@job@"}[5m]))\n'
        ")"
    ),
    "MemoireProcheDeLaLimite": (
        'container_memory_working_set_bytes{namespace="@namespace@", container!=""}\n'
        "  /\n"
        'container_spec_memory_limit_bytes{namespace="@namespace@", container!=""}'
    ),
    "CpuEleve": (
        "sum by (pod) (\n"
        "  rate(container_cpu_usage_seconds_total"
        '{namespace="@namespace@", container!=""}[5m])\n'
        ")"
    ),
    "RedemarragesEnBoucle": (
        "increase(\n"
        "  kube_pod_container_status_restarts_total"
        '{namespace="@namespace@"}[1h]\n'
        ")"
    ),
    "SondeExterneEnEchec": 'probe_success{job="@blackbox_job@"}',
    "CertificatBientotExpire": (
        "(\n"
        '  probe_ssl_earliest_cert_expiry{job="@blackbox_job@"} - time()\n'
        ") / 86400"
    ),
}
