"""Partie statique de la projection : ce qui ne depend pas d'un environnement.

Providers, variables, sorties, backend, labels : tout ce que le module declare
une fois pour toutes. La partie qui varie d'un environnement a l'autre vit dans
:mod:`forge.plugins.terraform.derive_env`.

Une regle gouverne ce module : **une seule source pour chaque nom**. La liste
des variables sert a la fois `variables.tf` du module, `variables.tf` de chaque
racine, le passage de parametres dans `main.tf` et le `terraform.tfvars`. Une
variable transmise a un module qui ne la declare pas est une erreur bruyante ;
une variable declaree et jamais transmise ne l'est pas — elle prend simplement
sa valeur par defaut, et l'ecart ne se voit jamais.
"""

from __future__ import annotations

from typing import Any

from forge.plugins.terraform import hcl
from forge.plugins.terraform.catalog.registry import (
    providers_for,
    selected,
    variables_for,
)
from forge.plugins.terraform.constants import DEFAULT_STATE_FILE
from forge.plugins.terraform.enums import KubernetesAuth, ResourceFamily
from forge.plugins.terraform.variables import Variable

#: Expression HCL rendue par chaque sortie du module. Les adresses citees ici
#: doivent correspondre aux ressources des gabarits de famille : c'est le seul
#: couplage entre ce module et les fichiers `.tf` ecrits a la main.
OUTPUT_VALUES: dict[str, str] = {
    "namespace": "local.namespace",
    "resource_quota_name": "kubernetes_resource_quota.this.metadata[0].name",
    "image_pull_secret_name": "kubernetes_secret.registry.metadata[0].name",
    "service_account_name": "kubernetes_service_account.deployer.metadata[0].name",
    "generated_secret_name": "kubernetes_secret.generated.metadata[0].name",
    "tls_secret_name": "kubernetes_secret.tls.metadata[0].name",
}

#: Sortie presente quelles que soient les familles retenues : c'est par elle que
#: le reste de la chaine — un chart Helm, un pipeline — apprend ou deployer.
BASE_OUTPUTS: dict[str, str] = {
    "namespace": "Namespace dans lequel le service est deploye.",
}

#: Variables propres a la racine d'environnement : elles configurent le
#: provider, pas le module. Le module, lui, ne sait pas comment on joint le
#: cluster — c'est la separation qui rend le module reutilisable.
ROOT_ONLY_VARIABLES: tuple[Variable, ...] = (
    Variable(
        name="kube_config_path",
        type="string",
        description=(
            "Chemin du fichier kubeconfig employe pour joindre le cluster. "
            "Propre a la machine : laissez la valeur par defaut et surchargez-la "
            "par TF_VAR_kube_config_path si besoin."
        ),
        default="~/.kube/config",
    ),
    Variable(
        name="kube_context",
        type="string",
        description=(
            "Contexte kubeconfig vise. Ne le laissez jamais vide : sans "
            "contexte explicite, Terraform applique sur le contexte courant de "
            "la machine, quel qu'il soit."
        ),
        default="",
        per_environment=True,
    ),
)


def variables(spec: Any) -> list[dict[str, Any]]:
    """Variables du module, communes puis propres aux familles retenues."""
    familles = selected(spec.terraform.family_names())
    return [_variable(variable) for variable in variables_for(familles)]


def root_variables(spec: Any) -> list[dict[str, Any]]:
    """Variables d'une racine d'environnement : celles du module, plus l'acces.

    Les variables d'acces au cluster ne sont ajoutees qu'en authentification par
    kubeconfig : en mode `in_cluster`, le provider lit le jeton monte dans le
    pod et un chemin de kubeconfig n'aurait aucun sens.
    """
    liste = variables(spec)
    if spec.terraform.kubernetes.auth is KubernetesAuth.KUBECONFIG:
        acces = [_variable(variable) for variable in ROOT_ONLY_VARIABLES]
        acces[0]["default"] = hcl.hcl_value(spec.terraform.kubernetes.config_path)
        liste = acces + liste
    return liste


def _variable(variable: Variable) -> dict[str, Any]:
    """Rend une variable en dict JSON-serialisable, defaut deja en HCL."""
    return {
        "name": variable.name,
        "type": variable.type,
        "description": variable.description,
        "has_default": variable.has_default,
        "default": hcl.hcl_value(variable.default) if variable.has_default else "",
        "sensitive": variable.sensitive,
        "per_environment": variable.per_environment,
    }


def providers(spec: Any) -> list[dict[str, str]]:
    """Providers exiges, tries par nom local."""
    familles = selected(spec.terraform.family_names())
    return [
        {
            "name": provider.name,
            "source": provider.source,
            "version": provider.version,
            "reason": provider.reason,
        }
        for provider in providers_for(familles)
    ]


def outputs(spec: Any) -> list[dict[str, str]]:
    """Sorties du module : la sortie de base, puis celles des familles.

    Dedoublonnees par nom : la famille `namespace` declare la meme sortie que la
    base, et c'est bien la meme.
    """
    descriptions = dict(BASE_OUTPUTS)
    for famille in selected(spec.terraform.family_names()):
        for nom, description in famille.outputs.items():
            descriptions.setdefault(nom, description)
    return [
        {"name": nom, "description": description, "value": OUTPUT_VALUES[nom]}
        for nom, description in descriptions.items()
    ]


def backend(spec: Any) -> dict[str, Any]:
    """Backend d'etat : son type, et les cles communes a tous les environnements.

    Les cles propres a un environnement — `key`, `prefix` — sont ajoutees par
    `derive_env`, pour que deux environnements n'ecrivent jamais le meme etat.
    """
    configuration = spec.terraform.backend
    return {
        "kind": configuration.kind.value,
        "config": dict(configuration.config),
        "is_local": configuration.kind.value == "local",
        "state_file": DEFAULT_STATE_FILE,
    }


def kubernetes(spec: Any) -> dict[str, Any]:
    """Comment le provider joint le cluster."""
    acces = spec.terraform.kubernetes
    return {
        "auth": acces.auth.value,
        "config_path": acces.config_path,
        "context_per_environment": acces.context_per_environment,
        "uses_kubeconfig": acces.auth is KubernetesAuth.KUBECONFIG,
    }


def base_labels(spec: Any) -> dict[str, str]:
    """Labels metier du service, repris a l'identique par tous les domaines.

    Les labels `app.kubernetes.io/*` ne figurent pas ici : ils sont calcules
    dans `locals.tf`, a partir de variables, pour que le module reste juste
    quand on l'appelle avec d'autres valeurs que celles engendrees.
    """
    return dict(spec.service.labels)


def extras(spec: Any) -> dict[str, bool]:
    """Fichiers annexes demandes."""
    annexes = spec.terraform.extras
    return {"makefile": annexes.makefile, "tflint_config": annexes.tflint_config}


def families(spec: Any) -> list[dict[str, Any]]:
    """Familles retenues, avec ce que le README du module doit en dire."""
    return [
        {
            "name": famille.name,
            "summary": famille.summary,
            "details": famille.details,
            "resources": list(famille.resources),
            "providers": list(famille.providers),
            "traps": list(famille.traps),
            "variables": [variable.name for variable in famille.variables],
            "outputs": sorted(famille.outputs),
        }
        for famille in selected(spec.terraform.family_names())
    ]


def creates_namespace(spec: Any) -> bool:
    """Vrai si Terraform cree le namespace au lieu de s'y rattacher."""
    return spec.terraform.uses(ResourceFamily.NAMESPACE)
