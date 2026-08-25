"""Valeurs derivees de la specification Helm, pretes pour les gabarits.

Ce module est le portage du **calcul de donnees** que faisaient
`helm_forge.models.spec` (dans ses validateurs) et
`helm_forge.engine.renderer._base_context` avant de rendre quoi que ce soit. Le
rendu et l'ecriture sont desormais l'affaire de copier.

Il couvre la partie **statique** du dict `domain` : identite du chart, image,
composants, emplacements par famille de ressource. Ce qui varie par
environnement vit dans :mod:`forge.plugins.helm.derive_env`.

Regle absolue : **toute sortie est JSON-serialisable et d'ordre fige**. Jamais
d'objet pydantic, jamais d'`Enum` (`.value` partout), jamais de `set` : ce dict
est ecrit tel quel dans `.copier-answers.yml` et rejoue par `copier update`.

Nommage : les cles reprennent celles que les gabarits legacy lisaient sur les
objets pydantic, afin que convertir un gabarit se reduise a prefixer `domain.`
ou a employer la variable de boucle d'un `yield`. Les trois ecarts de nommage
assumes sont signales en commentaire a l'endroit ou ils apparaissent.
"""

from __future__ import annotations

from typing import Any

from forge.plugins.helm.constants import (
    DEFAULT_MAINTAINER_EMAIL,
    DEFAULT_MAINTAINER_NAME,
)
from forge.plugins.helm.enums import AddonKind
from forge.plugins.helm.jinja_ext import values_ref
from forge.plugins.helm.tree import (
    FAMILY_ORDER,
    component_families,
    test_connection_target,
)

# ---------------------------------------------------------------------------
# Identite du chart
# ---------------------------------------------------------------------------


def maintainer(service: Any) -> dict[str, str]:
    """Mainteneur ecrit dans `Chart.yaml`, jamais vide.

    `Chart.yaml` refuse une entree `maintainers` sans nom ni adresse, alors que
    `service.owner_email` est facultatif dans le coeur : le plugin fournit donc
    les replis, qui sont ceux d'`AppMeta` legacy (`unknown`,
    `unknown@example.com`). Les cles gardent les noms legacy `maintainer_name`
    et `maintainer_email`.
    """
    return {
        "maintainer_name": service.owner or DEFAULT_MAINTAINER_NAME,
        "maintainer_email": service.owner_email or DEFAULT_MAINTAINER_EMAIL,
    }


def kubernetes(helm: Any) -> dict[str, str]:
    """Version de Kubernetes ciblee, avec ses deux formes derivees.

    `kube_version_constraint` alimente `Chart.yaml`, `full_version` alimente
    `kubeconform`. Toutes deux etaient des proprietes du modele legacy ; un dict
    JSON-serialisable ne peut pas porter de propriete, elles sont donc
    materialisees ici.
    """
    return {
        "version": helm.kubernetes.version,
        "kube_version_constraint": helm.kubernetes.kube_version_constraint,
        "full_version": helm.kubernetes.full_version,
    }


def image(helm: Any) -> dict[str, Any]:
    """Image de conteneur par defaut du projet.

    `strategy` et `pull_policy` sont rendues en chaines : les gabarits legacy
    ecrivaient deja `spec.image.strategy.value`.
    """
    return {
        "registry": helm.image.registry,
        "repository": helm.image.repository,
        "strategy": helm.image.strategy.value,
        "tag": helm.image.tag,
        "pull_policy": helm.image.pull_policy.value,
        "pull_secret_name": helm.image.pull_secret_name,
    }


def secrets(helm: Any) -> dict[str, str]:
    """Strategie de gestion des secrets. Aucune valeur secrete n'y transite."""
    return {
        "strategy": helm.secrets.strategy.value,
        "store_name": helm.secrets.store_name,
        "refresh_interval": helm.secrets.refresh_interval,
    }


def extras(helm: Any) -> dict[str, bool]:
    """Fichiers annexes demandes (`helmfile` et `ci` non portes : H7, H8)."""
    return {
        "makefile": helm.extras.makefile,
        "helm_tests": helm.extras.helm_tests,
    }


# ---------------------------------------------------------------------------
# Composants
# ---------------------------------------------------------------------------


def addon_flags(component: Any) -> dict[str, bool]:
    """Un booleen par addon, **toutes les cles toujours presentes**.

    Remplace `component.has(AddonKind.SERVICE)` des gabarits legacy par
    `c.has.service` : un dict complet garantit qu'un gabarit ne peut pas
    referencer une cle absente, meme pour un addon qu'aucun composant n'emploie.
    """
    presents = {addon.value for addon in component.addons}
    return {addon.value: addon.value in presents for addon in AddonKind}


def probes(component: Any) -> dict[str, Any]:
    """Sondes de sante. Le port interroge est `port_name`, jamais un numero."""
    p = component.probes
    return {
        "enabled": p.enabled,
        "liveness_path": p.liveness_path,
        "readiness_path": p.readiness_path,
        "startup_enabled": p.startup_enabled,
        "initial_delay_seconds": p.initial_delay_seconds,
        "period_seconds": p.period_seconds,
        "timeout_seconds": p.timeout_seconds,
        "failure_threshold": p.failure_threshold,
    }


def resources(spec_resources: Any) -> dict[str, str]:
    """Requests et limits d'un conteneur, profil compris (informatif)."""
    return {
        "profile": spec_resources.profile.value,
        "cpu_request": spec_resources.cpu_request,
        "memory_request": spec_resources.memory_request,
        "cpu_limit": spec_resources.cpu_limit,
        "memory_limit": spec_resources.memory_limit,
    }


def security(component: Any) -> dict[str, Any]:
    """Contexte de securite du pod et du conteneur."""
    s = component.security
    return {
        "strict": s.strict,
        "run_as_non_root": s.run_as_non_root,
        "run_as_user": s.run_as_user,
        "run_as_group": s.run_as_group,
        "fs_group": s.fs_group,
        "read_only_root_filesystem": s.read_only_root_filesystem,
        "allow_privilege_escalation": s.allow_privilege_escalation,
        "drop_capabilities": list(s.drop_capabilities),
        "seccomp_profile": s.seccomp_profile,
    }


def component_service(component: Any) -> dict[str, Any]:
    """Service exposant la charge de travail."""
    s = component.service
    return {
        "type": s.type.value,
        "port": s.port,
        "headless": s.headless,
        "node_port": s.node_port,
        "annotations": dict(s.annotations),
    }


def ingress(component: Any) -> dict[str, Any]:
    """Exposition HTTP. `class_name` est resolu ici, jamais dans un gabarit.

    Le modele documente `class_name` comme « absent = derive du controller » :
    la derivation est litterale (`nginx` -> `nginx`, `traefik` -> `traefik`),
    mais elle doit exister quelque part, et un gabarit n'a pas a la porter.
    L'hote, lui, depend de l'environnement : il vit dans `domain.environments`.
    """
    i = component.ingress
    return {
        "controller": i.controller.value,
        "base_domain": i.base_domain,
        "path": i.path,
        "path_type": i.path_type,
        "tls": i.tls,
        "issuer": i.issuer,
        "class_name": i.class_name or i.controller.value,
        "annotations": dict(i.annotations),
    }


def persistence(component: Any) -> dict[str, Any]:
    """Volume persistant attache a la charge de travail."""
    p = component.persistence
    return {
        "enabled": p.enabled,
        "storage_class": p.storage_class,
        "size": p.size,
        "access_mode": p.access_mode.value,
        "mount_path": p.mount_path,
    }


def hpa(component: Any) -> dict[str, Any]:
    """Bornes et cibles de l'autoscaling horizontal."""
    h = component.hpa
    return {
        "min_replicas": h.min_replicas,
        "max_replicas": h.max_replicas,
        "target_cpu": h.target_cpu,
        "target_memory": h.target_memory,
    }


def networkpolicy(component: Any) -> dict[str, Any]:
    """Restriction du trafic reseau entrant et sortant."""
    n = component.networkpolicy
    return {
        "allow_from_same_namespace": n.allow_from_same_namespace,
        "allow_from_namespaces": list(n.allow_from_namespaces),
        "allow_dns": n.allow_dns,
        "allow_egress_all": n.allow_egress_all,
    }


def cron(component: Any) -> dict[str, Any] | None:
    """Parametres du CronJob, ou `None` pour tout autre type de composant."""
    c = component.cron
    if c is None:
        return None
    return {
        "schedule": c.schedule,
        "concurrency_policy": c.concurrency_policy,
        "restart_policy": c.restart_policy,
        "successful_jobs_history_limit": c.successful_jobs_history_limit,
        "failed_jobs_history_limit": c.failed_jobs_history_limit,
        "backoff_limit": c.backoff_limit,
        "starting_deadline_seconds": c.starting_deadline_seconds,
    }


def component_context(component: Any, helm: Any, *, service_name: str) -> dict[str, Any]:
    """Contexte complet d'un composant, tel que le voient tous les gabarits.

    Trois valeurs sont **resolues** plutot que recopiees, parce que chaque
    gabarit legacy refaisait la meme resolution :

    * `image_repository` : `component.image_repository or spec.image.repository`
      — jamais nul, contrairement au champ du modele ;
    * `values_ref` : l'expression d'acces a la cle de values du composant, qui
      gere le cas du nom a tiret (`[% set v = values_ref(component.name) %]`
      en tete de chaque gabarit legacy) ;
    * `helper` : le prefixe des helpers du composant
      (`[% set h = spec.app.name ~ "." ~ component.name %]`).

    `families` liste les fichiers que ce composant fera generer : c'est ce qui
    permet au README du chart de se documenter sans reimplementer le filtrage.
    """
    return {
        "name": component.name,
        "kind": component.kind.value,
        "is_workload": component.is_workload,
        "addons": [addon.value for addon in component.addons],
        "has": addon_flags(component),
        "families": component_families(component),
        "values_ref": values_ref(component.name),
        "helper": f"{service_name}.{component.name}",
        "image_repository": component.image_repository or helm.image.repository,
        "command": list(component.command),
        "args": list(component.args),
        "replicas": component.replicas,
        "container_port": component.container_port,
        "port_name": component.port_name,
        "probes": probes(component),
        "resources": resources(component.resources),
        "security": security(component),
        "service": component_service(component),
        "ingress": ingress(component),
        "persistence": persistence(component),
        "hpa": hpa(component),
        "pdb": {"min_available": component.pdb.min_available},
        "networkpolicy": networkpolicy(component),
        "rbac": {
            "create": component.rbac.create,
            "rules": [dict(regle) for regle in component.rbac.rules],
        },
        "config": {
            "keys": list(component.config.keys),
            "mount_as": component.config.mount_as,
        },
        "secret": {
            "keys": list(component.secret.keys),
            "mount_as": component.secret.mount_as,
        },
        "cron": cron(component),
    }


def components(helm: Any, *, service_name: str) -> list[dict[str, Any]]:
    """Contextes des composants, dans l'**ordre de la specification**.

    Cet ordre est significatif a deux titres : il fixe l'ordre des fichiers
    generes, et le premier composant expose porte l'hote d'Ingress nu.
    """
    return [
        component_context(composant, helm, service_name=service_name)
        for composant in helm.components
    ]


def component_slots(
    helm: Any, contextes: list[dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    """Un emplacement par famille de ressource, deja filtre par kind et addon.

    Sur le modele de `ansible.derive.role_slots`. Chaque cle porte la liste des
    contextes de composant concernes, dans l'ordre de la specification ; un
    gabarit s'ecrit alors, dans un **nom de chemin** :

        templates/[% yield c from domain.component_slots.ingress %]
        ingress-[[ c.name ]][% endyield %].yaml.jinja

    Une liste vide fait disparaitre le fichier. **Toutes les cles sont
    toujours presentes**, y compris vides, pour qu'un gabarit ne puisse jamais
    referencer une cle absente.

    `test_connection` est un cas a part : zero ou un element, le premier
    composant expose non headless, et seulement si `extras.helm_tests`
    (portage de `planner.first_exposed` et de sa condition d'appel).
    """
    slots: dict[str, list[dict[str, Any]]] = {
        famille: [
            contexte for contexte in contextes if famille in contexte["families"]
        ]
        for famille in FAMILY_ORDER
    }
    cible = test_connection_target(helm)
    par_nom = {contexte["name"]: contexte for contexte in contextes}
    slots["test_connection"] = [] if cible is None else [par_nom[cible.name]]
    return slots
