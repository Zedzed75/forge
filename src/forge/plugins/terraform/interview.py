"""Entretien du domaine Terraform.

Ecrit contre le protocole `Prompter` du coeur, jamais contre questionary : c'est
ce qui rend l'entretien rejouable par `tests/scripted_prompter.py`.

L'ordre des questions suit celui de la decision reelle : d'abord **ce que
Terraform pose** (les familles), parce que tout le reste en depend ; ensuite
**ou vit l'etat**, qui est le choix de securite ; enfin **comment on joint le
cluster**. Les questions sans objet ne sont pas posees : un backend `local` ne
demande aucune cle, une authentification dans le cluster ne demande aucun
kubeconfig.

Conformement a l'arbitrage R7 (PLAN.md), retourner `None` ne signifie pas que
l'utilisateur refuse le domaine — le coeur le lui a deja demande — mais qu'il
n'y a rien a generer : ici, aucune famille retenue.
"""

from __future__ import annotations

from typing import Any

from forge.interview.prompter import Prompter
from forge.plugins.terraform.catalog.registry import all_families
from forge.plugins.terraform.constants import REQUIRED_BACKEND_KEYS
from forge.plugins.terraform.enums import (
    BackendKind,
    KubernetesAuth,
    NamespaceStrategy,
    ResourceFamily,
)
from forge.spec.names import DNS_LABEL_RE
from forge.spec.service import ServiceSpec

#: Version de Terraform proposee par defaut. Bornee sur la majeure : une
#: contrainte sans borne haute laisse une version 2 future casser le projet.
DEFAULT_VERSION = "~> 1.9"

#: Libelles des strategies de namespace, dans l'ordre propose.
NAMESPACE_CHOICES: list[tuple[str, str]] = [
    (
        NamespaceStrategy.PER_ENV.value,
        "un namespace par environnement (<service>-<env>) — recommande",
    ),
    (NamespaceStrategy.SAME.value, "un seul namespace pour tous les environnements"),
    (NamespaceStrategy.CUSTOM.value, "je nomme moi-meme chaque namespace"),
]

#: Libelles des backends, dans l'ordre propose.
BACKEND_CHOICES: list[tuple[str, str]] = [
    (BackendKind.LOCAL.value, "local — fichier dans le repertoire de travail (decouverte)"),
    (BackendKind.S3.value, "s3 — bucket S3 ou compatible"),
    (BackendKind.GCS.value, "gcs — bucket Google Cloud Storage"),
    (BackendKind.AZURERM.value, "azurerm — compte de stockage Azure"),
    (BackendKind.HTTP.value, "http — service implementant l'API d'etat (GitLab, Atlantis)"),
]

#: Libelles des modes d'authentification.
AUTH_CHOICES: list[tuple[str, str]] = [
    (KubernetesAuth.KUBECONFIG.value, "kubeconfig — un fichier et un contexte nomme"),
    (KubernetesAuth.IN_CLUSTER.value, "in_cluster — Terraform tourne dans le cluster vise"),
]


def run(prompter: Prompter, service: ServiceSpec) -> dict[str, Any] | None:
    """Conduit l'entretien et retourne la section `terraform:` de forge.yml."""
    prompter.note(
        "Terraform pose le socle : le namespace, son budget, l'identite qui y "
        "deploie. La charge applicative, elle, appartient au domaine Helm."
    )

    familles = _ask_families(prompter)
    if not familles:
        prompter.note("Aucune famille retenue : le domaine terraform n'est pas genere.")
        return None

    section: dict[str, Any] = {
        "terraform_version": prompter.text(
            "Contrainte de version Terraform", default=DEFAULT_VERSION
        ),
        "resources": familles,
    }

    strategie = prompter.select(
        "Comment nommer les namespaces ?", NAMESPACE_CHOICES, NamespaceStrategy.PER_ENV.value
    )
    section["namespace_strategy"] = strategie

    backend = _ask_backend(prompter)
    if backend:
        section["backend"] = backend

    acces = _ask_kubernetes(prompter)
    if acces:
        section["kubernetes"] = acces

    environnements = _ask_environments(prompter, service, strategie)
    if environnements:
        section["environments"] = environnements

    section["extras"] = {
        "makefile": prompter.confirm(
            "Ajouter un Makefile de raccourcis (make plan ENV=prod) ?", default=True
        ),
        "tflint_config": prompter.confirm(
            "Ajouter un fichier .tflint.hcl ?", default=True
        ),
    }
    return section


def _ask_families(prompter: Prompter) -> list[str]:
    """Familles de ressources retenues."""
    choix = [(famille.name, f"{famille.name} — {famille.summary}") for famille in all_families()]
    return prompter.checkbox(
        "Que Terraform doit-il poser ?", choix, [ResourceFamily.NAMESPACE.value]
    )


def _ask_backend(prompter: Prompter) -> dict[str, Any]:
    """Backend d'etat et ses cles obligatoires.

    Aucune cle secrete n'est demandee : le modele les refuserait, et un fichier
    genere ne porte jamais de secret.
    """
    kind = prompter.select("Ou conserver l'etat Terraform ?", BACKEND_CHOICES, BackendKind.LOCAL.value)
    if kind == BackendKind.LOCAL.value:
        prompter.note(
            "Etat local : ni verrou ni chiffrement. A ne pas garder pour un "
            "environnement partage."
        )
        return {}

    config: dict[str, str] = {}
    for cle in REQUIRED_BACKEND_KEYS[kind]:
        if cle in ("key", "prefix"):
            # Derivees par environnement : les demander produirait un etat
            # partage entre environnements, exactement ce qu'il faut eviter.
            continue
        config[cle] = prompter.text(f"backend {kind} : {cle}", validate=_non_vide)
    return {"kind": kind, "config": config}


def _ask_kubernetes(prompter: Prompter) -> dict[str, Any]:
    """Acces au cluster."""
    auth = prompter.select(
        "Comment Terraform joint-il le cluster ?", AUTH_CHOICES, KubernetesAuth.KUBECONFIG.value
    )
    if auth == KubernetesAuth.IN_CLUSTER.value:
        return {"auth": auth}

    chemin = prompter.text("Chemin du kubeconfig", default="~/.kube/config")
    par_env = prompter.confirm(
        "Un contexte kubeconfig different par environnement ?", default=True
    )
    acces: dict[str, Any] = {}
    if chemin != "~/.kube/config":
        acces["config_path"] = chemin
    if not par_env:
        acces["context_per_environment"] = False
    return acces


def _ask_environments(
    prompter: Prompter, service: ServiceSpec, strategie: str
) -> dict[str, Any]:
    """Surcharges par environnement. Seule la strategie `custom` en exige."""
    if strategie != NamespaceStrategy.CUSTOM.value:
        return {}
    return {
        env.name: {
            "namespace": prompter.text(
                f"Namespace de l'environnement '{env.name}'",
                default=f"{service.name}-{env.name}",
                validate=_label_dns,
            )
        }
        for env in service.environments
    }


def _non_vide(valeur: str) -> str | None:
    return None if valeur.strip() else "Une valeur est necessaire."


def _label_dns(valeur: str) -> str | None:
    if not DNS_LABEL_RE.match(valeur):
        return "Un label DNS : minuscules, chiffres et tirets."
    return None
