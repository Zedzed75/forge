"""Entretien du domaine Helm.

Le coeur a deja demande l'identite du service et ses environnements ; cet
entretien ne repose aucune de ces questions. Il decrit ce qui est propre a Helm :
la version de Kubernetes visee, l'image, et les composants du chart avec leurs
ressources.

Le questionnaire suit la structure du catalogue (`catalog/families.py`) : pour
chaque composant, on demande son type de charge de travail, puis les familles de
ressources a lui adjoindre. L'utilisateur n'a jamais a connaitre le nom d'un kind
Kubernetes — le catalogue le traduit.
"""

from __future__ import annotations

from typing import Any

from forge.interview.prompter import Prompter, Validator
from forge.plugins.helm.catalog.registry import get_family
from forge.plugins.helm.constants import KUBERNETES_VERSIONS
from forge.plugins.helm.enums import (
    AddonKind,
    ComponentKind,
    ImagePullPolicy,
    NamespaceStrategy,
    TagStrategy,
)
from forge.spec.names import DNS_LABEL_RE
from forge.spec.service import ServiceSpec

#: Addons proposes a la selection, dans l'ordre du catalogue.
ADDONS_PROPOSES: tuple[str, ...] = (
    AddonKind.SERVICE.value,
    AddonKind.INGRESS.value,
    AddonKind.CONFIGMAP.value,
    AddonKind.SECRET.value,
    AddonKind.HPA.value,
    AddonKind.PDB.value,
    AddonKind.SERVICEACCOUNT.value,
    AddonKind.NETWORKPOLICY.value,
)

#: Addons coches par defaut : le strict necessaire d'un service exposable.
ADDONS_PAR_DEFAUT: tuple[str, ...] = (AddonKind.SERVICE.value,)


def _label_dns(valeur: str) -> str | None:
    if not DNS_LABEL_RE.match(valeur.strip()):
        return "attendu un label DNS : minuscules, chiffres et tirets internes"
    return None


def _entier(valeur: str) -> str | None:
    texte = valeur.strip()
    if not texte.isdigit() or int(texte) < 1:
        return "attendu un entier positif"
    return None


def _non_vide(valeur: str) -> str | None:
    return None if valeur.strip() else "valeur obligatoire"


def _libelle_famille(nom: str) -> str:
    """Libelle d'un addon : son resume de catalogue, pas son kind."""
    famille = get_family(nom)
    return f"{famille.summary} ({famille.kind})"


def _demander_composant(prompter: Prompter, rang: int, premier: bool) -> dict[str, Any] | None:
    """Questionne un composant ; retourne None si l'utilisateur s'arrete."""
    invite = "Nom du composant" if premier else f"Nom du composant n°{rang} (vide pour terminer)"
    validation: Validator | None = _label_dns if premier else None
    nom = prompter.text(invite, default="api" if premier else "").strip()
    if not nom:
        return None
    if validation is None and _label_dns(nom) is not None:
        prompter.note(f"Nom ignore : {_label_dns(nom)}")
        return None

    kind = prompter.select(
        f"Type de charge de travail pour « {nom} »",
        choices=[
            (ComponentKind.DEPLOYMENT.value, "Sans etat, repliquable (Deployment)"),
            (ComponentKind.STATEFULSET.value, "A etat, volume par pod (StatefulSet)"),
            (ComponentKind.CRONJOB.value, "Tache planifiee (CronJob)"),
        ],
        default=ComponentKind.DEPLOYMENT.value,
    )

    composant: dict[str, Any] = {"name": nom, "kind": kind}

    if kind == ComponentKind.CRONJOB.value:
        # Un CronJob n'a ni Service, ni Ingress, ni autoscaling : ne pas les proposer.
        composant["cron"] = {
            "schedule": prompter.text(
                f"Planification de « {nom} » (cron a cinq champs)", default="0 3 * * *"
            ).strip()
        }
        return composant

    proposables = [nom_addon for nom_addon in ADDONS_PROPOSES]
    if kind == ComponentKind.STATEFULSET.value:
        # Le Service headless et la persistance sont imposes par le modele.
        proposables = [a for a in proposables if a != AddonKind.SERVICE.value]

    addons = prompter.checkbox(
        f"Ressources a adjoindre a « {nom} »",
        choices=[(a, _libelle_famille(a)) for a in proposables],
        default=[a for a in ADDONS_PAR_DEFAUT if a in proposables],
    )
    if kind == ComponentKind.STATEFULSET.value:
        addons = [AddonKind.SERVICE.value, *addons]
    composant["addons"] = addons

    port = prompter.text(
        f"Port d'ecoute du conteneur « {nom} »", default="8080", validate=_entier
    )
    composant["container_port"] = int(port)

    if AddonKind.INGRESS.value in addons:
        composant["ingress"] = {
            "base_domain": prompter.text(
                f"Domaine de base pour l'exposition de « {nom} »",
                default="example.net",
                validate=_non_vide,
            ).strip()
        }
    return composant


def run(prompter: Prompter, service: ServiceSpec) -> dict[str, Any] | None:
    """Conduit l'entretien du domaine Helm et retourne sa section de forge.yml.

    Retourne None si l'utilisateur ne declare aucun composant : un chart sans
    composant n'aurait rien a deployer.
    """
    prompter.note("── Chart Helm ──")

    version = prompter.select(
        "Version de Kubernetes visee",
        choices=[(v, v) for v in KUBERNETES_VERSIONS],
        default=KUBERNETES_VERSIONS[-1],
    )
    chart_version = prompter.text("Version du chart (semver)", default="0.1.0").strip()
    app_version = prompter.text(
        "Version applicative (appVersion)", default="1.0.0", validate=_non_vide
    ).strip()

    prompter.note("── Image ──")
    registry = prompter.text("Registre d'images", default="docker.io").strip()
    repository = prompter.text(
        "Depot de l'image (sans le registre)", default=service.name, validate=_non_vide
    ).strip()
    strategy = prompter.select(
        "Comment le tag d'image est-il choisi ?",
        choices=[
            (TagStrategy.APP_VERSION.value, "Le tag suit l'appVersion du chart"),
            (TagStrategy.PER_ENV.value, "Un tag par environnement"),
            (TagStrategy.FIXED.value, "Un tag fixe, identique partout"),
        ],
        default=TagStrategy.APP_VERSION.value,
    )
    image: dict[str, Any] = {
        "registry": registry,
        "repository": repository,
        "strategy": strategy,
        "pull_policy": ImagePullPolicy.IF_NOT_PRESENT.value,
    }
    if strategy == TagStrategy.FIXED.value:
        image["tag"] = prompter.text("Tag fixe", default="1.0.0", validate=_non_vide).strip()

    prompter.note("── Namespaces ──")
    namespace_strategy = prompter.select(
        "Comment les namespaces sont-ils repartis ?",
        choices=[
            (NamespaceStrategy.PER_ENV.value, "Un namespace par environnement"),
            (NamespaceStrategy.SINGLE.value, "Un seul namespace, partage"),
            (NamespaceStrategy.CUSTOM.value, "Un namespace precise pour chaque environnement"),
        ],
        default=NamespaceStrategy.PER_ENV.value,
    )

    prompter.note("── Composants du chart ──")
    composants: list[dict[str, Any]] = []
    while True:
        composant = _demander_composant(prompter, len(composants) + 1, not composants)
        if composant is None:
            break
        composants.append(composant)
        if not prompter.confirm("Ajouter un autre composant ?", default=False):
            break
    if not composants:
        return None

    section: dict[str, Any] = {
        "chart_version": chart_version,
        "app_version": app_version,
        "kubernetes": {"version": version},
        "namespace_strategy": namespace_strategy,
        "image": image,
        "components": composants,
    }

    if namespace_strategy == NamespaceStrategy.CUSTOM.value:
        section["environments"] = {
            env.name: {
                "namespace": prompter.text(
                    f"Namespace de l'environnement « {env.name} »",
                    default=f"{service.name}-{env.name}",
                    validate=_non_vide,
                ).strip()
            }
            for env in service.environments
        }

    section["extras"] = {
        "makefile": prompter.confirm("Generer un Makefile de raccourcis ?", default=True),
        "helm_tests": prompter.confirm("Generer un test `helm test` ?", default=True),
    }
    return section
