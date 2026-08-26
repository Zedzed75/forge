"""Partie de la projection qui varie d'un environnement a l'autre.

Une racine Terraform par environnement, et pour chacune : son namespace, son
contexte de cluster, son emplacement d'etat, ses valeurs. Le module, lui, est
ecrit une seule fois — c'est tout l'interet de la disposition.

Deux invariants tiennent ce module :

* **deux environnements n'ecrivent jamais le meme etat.** La cle d'etat est
  derivee du service et de l'environnement quand la specification ne la donne
  pas ; deux racines partageant un etat se detruiraient mutuellement au premier
  apply, et rien dans Terraform ne le signale a l'avance.
* **aucune valeur secrete n'entre dans `terraform.tfvars`.** Le fichier ne
  reprend que des variables non secretes, et seulement celles que le module — ou
  la racine — declare : Terraform refuse un tfvars citant une variable inconnue.
"""

from __future__ import annotations

from typing import Any

from forge.plugins.terraform import derive, hcl
from forge.plugins.terraform.constants import DEFAULT_STATE_FILE
from forge.plugins.terraform.enums import ResourceFamily


def environments(spec: Any) -> list[dict[str, Any]]:
    """Une entree par environnement de `service.environments`, dans l'ordre."""
    variables = derive.root_variables(spec)
    defauts = {variable["name"]: variable for variable in variables}
    passages = [
        {"name": variable["name"], "value": f"var.{variable['name']}"}
        for variable in derive.variables(spec)
    ]
    return [_environment(spec, env, defauts, variables, passages) for env in spec.service.environments]


def _environment(
    spec: Any,
    env: Any,
    defauts: dict[str, dict[str, Any]],
    variables: list[dict[str, Any]],
    passages: list[dict[str, str]],
) -> dict[str, Any]:
    """Projection d'un environnement."""
    terraform = spec.terraform
    surcharge = terraform.overrides(env.name)
    namespace = terraform.namespace_for(spec.service.name, env.name)
    valeurs = _values(spec, env, surcharge, namespace, defauts)

    return {
        "name": env.name,
        "production": env.production,
        "domain": env.domain or "",
        "namespace": namespace,
        "kube_context": valeurs.get("kube_context", ""),
        "backend_config": _backend_config(spec, env, surcharge),
        "tfvars": [
            {"name": nom, "value": hcl.hcl_value(valeur)}
            for nom, valeur in valeurs.items()
            if nom in defauts and not defauts[nom]["sensitive"]
        ],
        "module_arguments": passages,
        "variable_names": [variable["name"] for variable in variables],
    }


def _values(
    spec: Any,
    env: Any,
    surcharge: Any,
    namespace: str,
    defauts: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Valeurs pre-remplies de l'environnement, dans l'ordre du `tfvars`.

    L'ordre est celui de la lecture : d'abord ce qui identifie l'environnement,
    puis l'acces au cluster, puis les reglages des familles retenues.
    """
    terraform = spec.terraform
    valeurs: dict[str, Any] = {
        "service_name": spec.service.name,
        "environment": env.name,
        "namespace": namespace,
        "labels": {**spec.service.labels, **surcharge.labels},
    }

    if "kube_context" in defauts:
        valeurs["kube_context"] = surcharge.kube_context or (
            env.name if terraform.kubernetes.context_per_environment else ""
        )

    if terraform.uses(ResourceFamily.QUOTA):
        quota = surcharge.quota
        for nom, attribut in (
            ("quota_cpu", "cpu"),
            ("quota_memory", "memory"),
            ("quota_pods", "pods"),
        ):
            explicite = getattr(quota, attribut, None) if quota else None
            valeurs[nom] = explicite if explicite is not None else _default(defauts, nom)

    if terraform.uses(ResourceFamily.TLS_CERTIFICATE):
        noms = list(surcharge.tls_dns_names)
        if not noms and env.domain:
            noms = [f"{spec.service.name}.{env.domain}"]
        valeurs["tls_dns_names"] = noms
        valeurs["tls_common_name"] = noms[0] if noms else ""

    return valeurs


def _default(defauts: dict[str, dict[str, Any]], name: str) -> Any:
    """Valeur par defaut declaree pour `name`, telle que le catalogue la donne.

    Elle est relue du catalogue plutot que recopiee ici : une valeur par defaut
    changee dans une famille doit se voir dans le `terraform.tfvars` sans qu'on
    ait a y penser.
    """
    return _CATALOG_DEFAULTS[name]


def _catalog_defaults() -> dict[str, Any]:
    """Valeurs par defaut de toutes les variables de famille, indexees par nom."""
    from forge.plugins.terraform.catalog.registry import all_families

    return {
        variable.name: variable.default
        for famille in all_families()
        for variable in famille.variables
    }


#: Calculees une fois : le catalogue est fige au chargement du module.
_CATALOG_DEFAULTS: dict[str, Any] = _catalog_defaults()


def _backend_config(spec: Any, env: Any, surcharge: Any) -> list[dict[str, str]]:
    """Cles de backend de cet environnement, communes puis propres, puis derivees.

    La cle d'etat est **toujours** presente en sortie : c'est elle qui garantit
    que deux environnements n'ecrivent pas au meme endroit.
    """
    configuration: dict[str, str] = {
        **spec.terraform.backend.config,
        **surcharge.backend_config,
    }
    kind = spec.terraform.backend.kind.value
    derivee = _state_key(spec.service.name, env.name, kind)
    for cle, valeur in derivee.items():
        configuration.setdefault(cle, valeur)
    return [
        {"name": cle, "value": hcl.hcl_value(valeur)}
        for cle, valeur in sorted(configuration.items())
    ]


def _state_key(service_name: str, environment: str, kind: str) -> dict[str, str]:
    """Emplacement d'etat derive, propre a l'environnement, selon le backend."""
    if kind == "local":
        return {"path": DEFAULT_STATE_FILE}
    if kind == "s3":
        return {"key": f"{service_name}/{environment}/{DEFAULT_STATE_FILE}"}
    if kind == "gcs":
        return {"prefix": f"{service_name}/{environment}"}
    if kind == "azurerm":
        return {"key": f"{service_name}-{environment}.tfstate"}
    return {}
