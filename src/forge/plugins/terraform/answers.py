"""Projection de la specification vers le dict `domain` de copier, et controles croises.

Meme contrat que les deux autres domaines (`forge_answers`, DESIGN.md §2.2) :
sortie JSON-serialisable, ordre fige, aucun objet pydantic. Le calcul vit dans
:mod:`derive`, :mod:`derive_env` et :mod:`tree` ; ce module assemble, et porte
les controles que le sous-modele ne peut pas faire parce qu'il ne voit pas
`service:`.
"""

from __future__ import annotations

from typing import Any

from forge.plugins.terraform import derive, derive_env, tree
from forge.plugins.terraform.constants import MAX_NAMESPACE_LENGTH
from forge.plugins.terraform.enums import BackendKind, NamespaceStrategy, ResourceFamily
from forge.plugins_api.types import Issue


def build(spec: Any) -> dict[str, Any]:
    """Construit le dict `domain` passe a copier pour le domaine Terraform."""
    service = spec.service
    terraform = spec.terraform

    return {
        # -- identite du module ------------------------------------------------
        "module_dir": tree.module_dir(service.name),
        "module_name": service.name,
        "terraform_version": terraform.terraform_version,
        "providers": derive.providers(spec),
        # -- ce que le module recoit et rend -----------------------------------
        "variables": derive.variables(spec),
        "root_variables": derive.root_variables(spec),
        "outputs": derive.outputs(spec),
        # -- socle -------------------------------------------------------------
        "backend": derive.backend(spec),
        "kubernetes": derive.kubernetes(spec),
        "namespace_strategy": terraform.namespace_strategy.value,
        "creates_namespace": derive.creates_namespace(spec),
        "labels": derive.base_labels(spec),
        # -- familles retenues --------------------------------------------------
        "resources": [famille["name"] for famille in derive.families(spec)],
        "families": derive.families(spec),
        "resource_slots": tree.resource_slots(spec),
        # -- environnements ------------------------------------------------------
        "env_names": [env.name for env in service.environments],
        "default_env": service.environments[0].name,
        "environments": derive_env.environments(spec),
        # -- annexes et documentation ---------------------------------------------
        "extras": derive.extras(spec),
        "root_files": tree.root_files(spec),
        "module_files": tree.module_files(spec),
        "environment_files": tree.environment_files(),
        "expected_paths": tree.expected_paths(spec),
    }


# ---------------------------------------------------------------------------
# Controles croises
# ---------------------------------------------------------------------------


def cross_check(spec: Any) -> list[Issue]:
    """Controles que `TerraformSpec` ne peut pas faire : elle ne voit pas `service:`.

    Ordre deterministe : la liste est affichee telle quelle.
    """
    terraform = getattr(spec, "terraform", None)
    if terraform is None:
        return []

    issues: list[Issue] = []
    issues.extend(_check_environment_keys(spec, terraform))
    issues.extend(_check_custom_namespaces(spec, terraform))
    issues.extend(_check_namespace_lengths(spec, terraform))
    issues.extend(_check_orphan_overrides(spec, terraform))
    issues.extend(_check_state_safety(spec, terraform))
    issues.extend(_check_cluster_context(spec, terraform))
    return issues


def _check_environment_keys(spec: Any, terraform: Any) -> list[Issue]:
    """Refuse une cle de `terraform.environments` absente de `service.environments`."""
    connus = {env.name for env in spec.service.environments}
    declares = ", ".join(env.name for env in spec.service.environments)
    return [
        Issue(
            level="error",
            message=(
                f"terraform.environments cite l'environnement '{nom}', absent "
                f"de service.environments (declares : {declares})."
            ),
            hint=(
                f"Ajoutez un environnement '{nom}' a service.environments, ou "
                f"corrigez la cle '{nom}' dans terraform.environments."
            ),
            domains=("terraform",),
        )
        for nom in sorted(set(terraform.environments) - connus)
    ]


def _check_custom_namespaces(spec: Any, terraform: Any) -> list[Issue]:
    """Exige un namespace explicite pour chaque environnement, strategie `custom`.

    Le sous-modele ne verifie que les environnements **presents** dans
    `terraform.environments` ; celui qui n'y figure pas du tout n'est visible
    que d'ici.
    """
    if terraform.namespace_strategy is not NamespaceStrategy.CUSTOM:
        return []
    return [
        Issue(
            level="error",
            message=(
                f"environnement '{env.name}' : la strategie de namespace "
                '"custom" exige un namespace explicite, et aucun n\'est declare.'
            ),
            hint=(
                f"Renseignez terraform.environments.{env.name}.namespace, ou "
                "passez terraform.namespace_strategy a per_env pour deriver "
                f"'{spec.service.name}-{env.name}'."
            ),
            domains=("terraform",),
        )
        for env in spec.service.environments
        if terraform.overrides(env.name).namespace is None
    ]


def _check_namespace_lengths(spec: Any, terraform: Any) -> list[Issue]:
    """Verifie les namespaces **derives**, que le sous-modele n'a jamais vus.

    `<service>-<env>` peut depasser 63 caracteres alors que ni le nom du service
    ni celui de l'environnement ne depassent leur propre plafond : le produit
    n'existe qu'ici.
    """
    issues: list[Issue] = []
    for env in spec.service.environments:
        namespace = terraform.namespace_for(spec.service.name, env.name)
        if len(namespace) <= MAX_NAMESPACE_LENGTH:
            continue
        issues.append(
            Issue(
                level="error",
                message=(
                    f"le namespace derive pour '{env.name}' est "
                    f"'{namespace}' ({len(namespace)} caracteres) ; Kubernetes "
                    f"en admet {MAX_NAMESPACE_LENGTH} au plus."
                ),
                hint=(
                    "Raccourcissez service.name ou le nom de l'environnement, "
                    f"ou fixez terraform.environments.{env.name}.namespace."
                ),
                domains=("terraform",),
            )
        )
    return issues


def _check_orphan_overrides(spec: Any, terraform: Any) -> list[Issue]:
    """Signale une surcharge sans effet parce que sa famille n'est pas retenue.

    Une valeur soigneusement reglee et silencieusement ignoree est pire qu'une
    erreur : rien ne la distingue d'une valeur appliquee.
    """
    issues: list[Issue] = []
    controles = (
        (ResourceFamily.QUOTA, "quota", "quota", "un budget de namespace"),
        (
            ResourceFamily.TLS_CERTIFICATE,
            "tls_dns_names",
            "tls_certificate",
            "des noms DNS de certificat",
        ),
    )
    for famille, attribut, nom_famille, libelle in controles:
        if terraform.uses(famille):
            continue
        for nom in sorted(terraform.environments):
            if not getattr(terraform.environments[nom], attribut, None):
                continue
            issues.append(
                Issue(
                    level="warning",
                    message=(
                        f"terraform.environments.{nom}.{attribut} declare "
                        f"{libelle}, mais la famille '{nom_famille}' n'est pas "
                        "dans terraform.resources : cette valeur ne sera pas "
                        "appliquee."
                    ),
                    hint=(
                        f"Ajoutez '{nom_famille}' a terraform.resources, ou "
                        f"retirez terraform.environments.{nom}.{attribut}."
                    ),
                    domains=("terraform",),
                )
            )
    return issues


def _check_state_safety(spec: Any, terraform: Any) -> list[Issue]:
    """Signale un etat local sur un environnement de production.

    L'etat Terraform porte en clair tout ce que les ressources exposent — dont
    les mots de passe engendres par la famille `random_secret`. En backend
    `local`, il vit dans le repertoire de travail, sans verrou ni chiffrement.
    """
    if terraform.backend.kind is not BackendKind.LOCAL:
        return []
    production = [env.name for env in spec.service.environments if env.production]
    if not production:
        return []
    secrets = terraform.uses(ResourceFamily.RANDOM_SECRET) or terraform.uses(
        ResourceFamily.TLS_CERTIFICATE
    )
    detail = (
        " ; il portera en clair les valeurs engendrees par les familles "
        "random_secret / tls_certificate"
        if secrets
        else ""
    )
    return [
        Issue(
            level="warning",
            message=(
                f"l'environnement de production '{production[0]}' emploie le "
                f"backend d'etat 'local' : l'etat n'est ni partage, ni verrouille, "
                f"ni chiffre{detail}."
            ),
            hint=(
                "Passez terraform.backend.kind a s3, gcs, azurerm ou http pour "
                "la production."
            ),
            domains=("terraform",),
        )
    ]


def _check_cluster_context(spec: Any, terraform: Any) -> list[Issue]:
    """Signale les environnements qui appliqueront sur le contexte courant.

    C'est l'accident le plus banal du provider Kubernetes : sans contexte
    nomme, `terraform apply` part vers le cluster que le kubeconfig de la
    machine designe au moment ou on lance la commande.
    """
    acces = terraform.kubernetes
    if acces.auth.value != "kubeconfig" or acces.context_per_environment:
        return []
    muets = [
        env.name
        for env in spec.service.environments
        if not terraform.overrides(env.name).kube_context
    ]
    if not muets:
        return []
    return [
        Issue(
            level="warning",
            message=(
                "terraform.kubernetes.context_per_environment est a false et "
                f"aucun contexte n'est nomme pour : {', '.join(muets)}. "
                "Terraform appliquera sur le contexte courant de la machine."
            ),
            hint=(
                "Repassez context_per_environment a true, ou renseignez "
                "terraform.environments.<env>.kube_context."
            ),
            domains=("terraform",),
        )
    ]
