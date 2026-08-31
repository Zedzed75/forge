"""Section `monitoring:` de forge.yml.

**Domaine autonome.** Il ne lit aucune autre section : ce qu'il surveille, il le
declare. C'est une decision de conception, pas une limite — un service peut etre
surveille sans etre deploye par forge, et un domaine qui lirait `helm.components`
cesserait de fonctionner le jour ou le chart vient d'ailleurs.

La coherence avec les autres domaines passe par le **vocabulaire des facettes**
(`namespaces`, `ingress_hosts`), compare par `forge validate` : si le chart
expose `boutique.example.net` et que la sonde regarde `api.example.net`, forge
le dit — sans qu'aucune regle « si helm alors monitoring » existe nulle part.

Ce que ce modele refuse, et pourquoi : un nom de metrique mal forme est refuse
par promtool de toute facon ; un nom **bien forme mais faux** produit une regle
valide et definitivement muette. Le modele ne peut pas verifier l'existence
d'une metrique, mais il peut exiger que celles dont il connait la source ne
soient pas redefinies au hasard.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, Field, field_validator, model_validator

from forge.plugins.monitoring.catalog.registry import family_names
from forge.plugins.monitoring.constants import (
    DURATION_RE,
    LABEL_NAME_RE,
    METRIC_NAME_RE,
    PROBE_URL_RE,
    TARGET_RE,
)
from forge.plugins.monitoring.enums import RuleFamily
from forge.spec.names import check_pattern, require_unique
from forge.spec.types import DnsLabel, ForgeModel


def _duration(value: str) -> str:
    return check_pattern(value, DURATION_RE, "une duree Prometheus (30s, 5m, 1h)")


def _metric_name(value: str) -> str:
    return check_pattern(value, METRIC_NAME_RE, "un nom de metrique Prometheus")


def _label_name(value: str) -> str:
    return check_pattern(value, LABEL_NAME_RE, "un nom de libelle Prometheus")


def _target(value: str) -> str:
    return check_pattern(value, TARGET_RE, "une cible de collecte 'hote:port'")


def _probe_url(value: str) -> str:
    return check_pattern(value, PROBE_URL_RE, "une URL http:// ou https://")


Duration = Annotated[str, AfterValidator(_duration)]
MetricName = Annotated[str, AfterValidator(_metric_name)]
LabelName = Annotated[str, AfterValidator(_label_name)]
Target = Annotated[str, AfterValidator(_target)]
ProbeUrl = Annotated[str, AfterValidator(_probe_url)]


class ScrapeSpec(ForgeModel):
    """Comment le collecteur interroge le service."""

    #: Periode entre deux collectes. Elle borne la finesse de tout ce qui suit :
    #: une fenetre `rate()` doit couvrir au moins deux collectes.
    interval: Duration = "30s"

    #: Delai au-dela duquel une collecte est abandonnee. Toujours inferieur a
    #: l'intervalle, sans quoi les collectes se chevauchent.
    timeout: Duration = "10s"

    #: Chemin exposant les metriques.
    metrics_path: str = "/metrics"

    @model_validator(mode="after")
    def _timeout_sous_intervalle(self) -> ScrapeSpec:
        if _seconds(self.timeout) > _seconds(self.interval):
            raise ValueError(
                f"scrape.timeout ({self.timeout}) depasse scrape.interval "
                f"({self.interval}) : les collectes se chevaucheraient."
            )
        return self


def _seconds(duration: str) -> float:
    """Convertit une duree Prometheus en secondes."""
    unites = {"ms": 0.001, "s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800, "y": 31536000}
    for suffixe in ("ms", "s", "m", "h", "d", "w", "y"):
        if duration.endswith(suffixe):
            return float(duration[: -len(suffixe)]) * unites[suffixe]
    raise ValueError(duration)  # pragma: no cover - le format est deja valide


class MetricNamesSpec(ForgeModel):
    """Noms des metriques exposees par l'application elle-meme.

    Elles ne sont pas normalisees : leur nom depend de la bibliotheque cliente.
    Les metriques d'infrastructure (`up`, `container_*`, `probe_*`) ne figurent
    pas ici — celles-la ont un nom fixe, et le laisser configurer inviterait a
    le changer pour un nom qui n'existe pas.
    """

    #: Compteur de requetes servies, avec un libelle de code de statut.
    requests_total: MetricName = "http_requests_total"

    #: Histogramme du temps de reponse. **Sans** le suffixe `_bucket` : les
    #: regles l'ajoutent. Un summary ne convient pas — il n'expose pas de seaux.
    request_duration_seconds: MetricName = "http_request_duration_seconds"

    #: Libelle portant le code de statut HTTP. `status`, `code` ou
    #: `status_code` selon la bibliotheque : se tromper donne une regle valide
    #: et definitivement muette.
    status_label: LabelName = "status"


class ThresholdsSpec(ForgeModel):
    """Seuils de declenchement. Toute cle omise garde la valeur du catalogue."""

    #: Proportion de reponses en erreur serveur (0.05 = 5 %).
    error_rate: float | None = Field(default=None, gt=0, lt=1)

    #: Quantile 95 du temps de reponse, en secondes.
    latency_p95_seconds: float | None = Field(default=None, gt=0)

    #: Proportion de la limite memoire (0.9 = 90 %).
    memory_ratio: float | None = Field(default=None, gt=0, le=1)

    #: Consommation CPU d'un pod, en cœurs.
    cpu_cores: float | None = Field(default=None, gt=0)

    #: Nombre de redemarrages en une heure au-dela duquel on alerte.
    restarts_per_hour: int | None = Field(default=None, gt=0)

    #: Jours restants avant expiration du certificat.
    certificate_days: int | None = Field(default=None, gt=0)

    def declared(self) -> dict[str, float | int]:
        """Seuils reellement renseignes, indexes par nom de champ."""
        return {
            nom: valeur
            for nom, valeur in self.model_dump().items()
            if valeur is not None
        }


class MonitoringEnvironmentSpec(ForgeModel):
    """Ce qui est surveille dans un environnement, et sous quels seuils."""

    #: Namespace Kubernetes observe. Necessaire aux familles `saturation` et
    #: `restarts`, qui filtrent les metriques de conteneur dessus.
    namespace: DnsLabel | None = None

    #: Cibles collectees, sous la forme `hote:port`. Ecrites dans la
    #: configuration plutot que decouvertes : une cible jamais declaree ne
    #: produit aucune serie, donc aucune alerte — le silence n'est pas la sante.
    targets: list[Target] = Field(default_factory=list)

    #: URL sondees de l'exterieur par le blackbox exporter. Seules les URL en
    #: `https://` permettent de surveiller l'expiration du certificat.
    probe_urls: list[ProbeUrl] = Field(default_factory=list)

    #: Seuils propres a cet environnement. La production merite souvent des
    #: seuils plus serres que le developpement.
    thresholds: ThresholdsSpec | None = None

    #: Libelles ajoutes a toutes les series de cet environnement.
    labels: dict[str, str] = Field(default_factory=dict)

    @field_validator("targets")
    @classmethod
    def _cibles_uniques(cls, value: list[str]) -> list[str]:
        require_unique(value, "cibles de collecte")
        return value

    @field_validator("probe_urls")
    @classmethod
    def _sondes_uniques(cls, value: list[str]) -> list[str]:
        require_unique(value, "URL sondees")
        return value


class MonitoringExtras(ForgeModel):
    """Fichiers annexes du projet genere."""

    #: Makefile de raccourcis (`make check`, `make test`).
    makefile: bool = True

    #: Tableau de bord Grafana. Ses panneaux reprennent les expressions des
    #: familles retenues : ce qu'on alerte est ce qu'on regarde.
    dashboard: bool = True

    # Les tests unitaires d'alerte ne sont **pas** une option, et c'est
    # delibere : une regle d'alerte non testee est une regle dont personne ne
    # sait si elle se declenche, et on ne l'apprend que le jour ou elle aurait
    # du le faire. Les rendre facultatifs aurait invite au mauvais choix.


class MonitoringSpec(ForgeModel):
    """Section `monitoring:` : sondes, regles d'alerte et leurs tests."""

    #: Comment le collecteur interroge le service.
    scrape: ScrapeSpec = Field(default_factory=ScrapeSpec)

    #: Noms des metriques exposees par l'application.
    metrics: MetricNamesSpec = Field(default_factory=MetricNamesSpec)

    #: Familles de regles retenues. L'ordre d'ecriture n'a pas d'importance :
    #: le catalogue les remet dans l'ordre canonique.
    rules: list[RuleFamily] = Field(
        default_factory=lambda: [RuleFamily.AVAILABILITY], min_length=1
    )

    #: Adresse du blackbox exporter, vue par le collecteur.
    blackbox_address: str = "blackbox-exporter:9115"

    #: Ce qui est surveille, environnement par environnement.
    environments: dict[str, MonitoringEnvironmentSpec] = Field(default_factory=dict)

    #: Fichiers annexes.
    extras: MonitoringExtras = Field(default_factory=MonitoringExtras)

    @field_validator("rules")
    @classmethod
    def _familles_uniques(cls, value: list[RuleFamily]) -> list[RuleFamily]:
        require_unique((famille.value for famille in value), "familles de regles")
        return value

    @model_validator(mode="after")
    def _familles_connues(self) -> MonitoringSpec:
        """Garde-fou : le catalogue et l'enumeration doivent rester d'accord."""
        connues = set(family_names())
        inconnues = sorted(f.value for f in self.rules if f.value not in connues)
        if inconnues:  # pragma: no cover - defaut de programmation du plugin
            raise ValueError(f"familles absentes du catalogue : {', '.join(inconnues)}.")
        return self

    # -- lecture ------------------------------------------------------------

    def overrides(self, environment: str) -> MonitoringEnvironmentSpec:
        """Ce qui est surveille dans `environment`, vide s'il n'est pas decrit."""
        return self.environments.get(environment) or MonitoringEnvironmentSpec()

    def uses(self, family: RuleFamily) -> bool:
        """Indique si la famille est retenue."""
        return family in self.rules

    def family_names(self) -> tuple[str, ...]:
        """Noms des familles retenues, tels qu'ecrits dans la specification."""
        return tuple(famille.value for famille in self.rules)

    def needs_blackbox(self) -> bool:
        """Vrai si une famille retenue repose sur une sonde externe."""
        from forge.plugins.monitoring.catalog.registry import selected

        return any(famille.needs_probe for famille in selected(self.family_names()))
