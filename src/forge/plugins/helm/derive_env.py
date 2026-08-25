"""Derivation par environnement : namespaces, profils, hotes, surcharges.

Partie **variable** du dict `domain`, separee de :mod:`forge.plugins.helm.derive`
qui n'en calcule que la partie statique. C'est ici que vit ce que le legacy
faisait dans `ProjectSpec._derive_namespaces`, `_derive_environment_defaults` et
`_hostname` — trois validateurs qui ecrivaient dans `__dict__` pour contourner
`validate_assignment=True`. Ce mode n'est pas reintroduit (arbitrage H11) : la
spec reste immuable apres validation, et la derivation produit directement des
dicts.

Ce qui rend un `forge.yml` minimal equivalent a un `forge.yml` complet tient en
une phrase : **une entree de surcharge est creee pour chaque composant de chaque
environnement**, meme absente de la specification, et le profil de
l'environnement y renseigne toute valeur laissee vide. Les gabarits n'ont donc
jamais a se demander si une surcharge existe.

Les valeurs restent a `None` la ou le legacy les laissait a `None` : les
gabarits de values testent `is not none` pour n'ecrire que des ecarts reels.
"""

from __future__ import annotations

from typing import Any

from forge.plugins.helm.derive import resources as resources_context
from forge.plugins.helm.enums import AddonKind, NamespaceStrategy
from forge.plugins.helm.profiles import EnvironmentProfile, profile_for

# ---------------------------------------------------------------------------
# Namespace
# ---------------------------------------------------------------------------


def namespace(helm: Any, service_name: str, env_name: str, override: Any) -> str:
    """Namespace de deploiement d'un environnement.

    Portage de `ProjectSpec._derive_namespaces` : un namespace explicite gagne
    toujours ; sinon `single` donne `<service>`, `per_env` donne
    `<service>-<env>`, et `custom` ne derive rien du tout — c'est le principe
    meme de cette strategie.

    Le modele refuse deja un namespace manquant pour un environnement **present**
    dans `helm.environments` ; ce qui reste ici est le cas d'un environnement
    qui n'y figure pas du tout, que seul le controle croise voit venir
    (`answers.cross_check`). L'erreur est levee plutot que devinee : un chart
    deploye dans un namespace invente serait pire qu'un echec de generation.
    """
    if override.namespace is not None:
        return override.namespace
    if helm.namespace_strategy is NamespaceStrategy.SINGLE:
        return service_name
    if helm.namespace_strategy is NamespaceStrategy.PER_ENV:
        return f"{service_name}-{env_name}"
    raise ValueError(
        f"environnement '{env_name}' : la strategie de namespace \"custom\" exige "
        f"un namespace explicite dans helm.environments.{env_name}.namespace"
    )


# ---------------------------------------------------------------------------
# Hote d'Ingress
# ---------------------------------------------------------------------------


def host_prefix(helm: Any, service_name: str, component_name: str) -> str:
    """Prefixe d'hote d'un composant expose.

    Portage de `ProjectSpec._hostname` : le **premier** composant expose, dans
    l'ordre de `components`, porte le nom du service seul ; les suivants sont
    prefixes de leur propre nom, afin que deux composants exposes ne se
    disputent pas le meme hote.
    """
    exposes = helm.exposed_components()
    if exposes and exposes[0] == component_name:
        return service_name
    return f"{component_name}-{service_name}"


def ingress_host(
    helm: Any,
    service_name: str,
    component: Any,
    env: Any,
    profile: EnvironmentProfile,
) -> str:
    """Hote d'Ingress d'un composant pour un environnement (arbitrages H1, H2).

    `service.environments[].domain` **l'emporte** quand il est renseigne :
    l'hote devient `<prefixe>.<domaine-de-l-env>`, **sans** reinserer le nom de
    l'environnement, puisque le domaine le porte deja. Sinon, repli litteral sur
    le comportement legacy :
    `<prefixe>[.<env> si profile.host_includes_env].<ingress.base_domain>`.

    `host_includes_env` vient du profil **resolu** (H2), donc de
    `production: true` s'il est present, du nom de l'environnement sinon.
    """
    prefixe = host_prefix(helm, service_name, component.name)
    if env.domain:
        return f"{prefixe}.{env.domain}"
    parties = [prefixe]
    if profile.host_includes_env:
        parties.append(env.name)
    parties.append(component.ingress.base_domain)
    return ".".join(parties)


# ---------------------------------------------------------------------------
# Surcharges par composant
# ---------------------------------------------------------------------------


def component_override(
    helm: Any,
    service_name: str,
    component: Any,
    env: Any,
    profile: EnvironmentProfile,
    override: Any,
) -> dict[str, Any]:
    """Ecarts d'un composant pour un environnement, profil applique.

    Portage de `ProjectSpec._derive_environment_defaults`, condition par
    condition. Une valeur reste a `None` exactement la ou le legacy la laissait
    a `None` :

    * `replicas` : le profil ne renseigne que les **charges de travail** ; un
      CronJob n'a pas de replicas, la cle reste nulle ;
    * `hpa_enabled` / `pdb_enabled` : nuls si le composant ne porte pas l'addon
      correspondant, faute de quoi les values annonceraient un autoscaling
      qu'aucune ressource n'implemente ;
    * `ingress_host` : nul si le composant n'est pas expose ;
    * `resources` : nulles quand le multiplicateur du profil vaut 1 — il n'y a
      alors aucun ecart a ecrire dans `values-<env>.yaml` ;
    * `image_tag` : jamais derive. Il ne vaut que ce que la specification
      contient ; la strategie de tag du projet vit dans `domain.image.strategy`,
      et c'est le gabarit de values qui en tire les consequences.
    """
    replicas = override.replicas
    if replicas is None and component.is_workload:
        replicas = profile.replicas

    hpa_enabled = override.hpa_enabled
    if hpa_enabled is None and component.has(AddonKind.HPA):
        hpa_enabled = profile.hpa_enabled

    pdb_enabled = override.pdb_enabled
    if pdb_enabled is None and component.has(AddonKind.PDB):
        pdb_enabled = profile.pdb_enabled

    hote = override.ingress_host
    if hote is None and component.has(AddonKind.INGRESS):
        hote = ingress_host(helm, service_name, component, env, profile)

    ressources = override.resources
    if ressources is None and profile.resource_multiplier != 1:
        ressources = component.resources.scaled(profile.resource_multiplier)

    return {
        "name": component.name,
        "replicas": replicas,
        "hpa_enabled": hpa_enabled,
        "pdb_enabled": pdb_enabled,
        "ingress_host": hote,
        "resources": None if ressources is None else resources_context(ressources),
        "image_tag": override.image_tag,
    }


# ---------------------------------------------------------------------------
# Environnements
# ---------------------------------------------------------------------------


def profile_context(profile: EnvironmentProfile) -> dict[str, Any]:
    """Profil resolu d'un environnement, sous forme JSON-serialisable.

    Expose tel quel pour que les gabarits puissent documenter *pourquoi* une
    valeur vaut ce qu'elle vaut (« profil prod : 3 repliques ») sans reimplementer
    la reconnaissance par le nom.
    """
    return {
        "replicas": profile.replicas,
        "hpa_enabled": profile.hpa_enabled,
        "pdb_enabled": profile.pdb_enabled,
        "log_level": profile.log_level,
        "resource_multiplier": profile.resource_multiplier,
        "host_includes_env": profile.host_includes_env,
    }


def environments(spec: Any) -> list[dict[str, Any]]:
    """Un environnement par entree de `service.environments`, dans son ordre.

    L'ordre de promotion (dev -> staging -> prod) est celui du bloc partage : le
    dict `helm.environments` ne porte plus que des surcharges (arbitrage H4).

    `components` est un dict **cle par nom de composant**, dans l'ordre de
    `helm.components` : c'est la forme que lisaient les gabarits legacy
    (`env.components[component.name]`). Une entree existe pour chaque composant,
    meme absente de la specification.
    """
    helm = spec.helm
    service_name = spec.service.name
    resultat: list[dict[str, Any]] = []

    for env in spec.service.environments:
        surcharges = helm.overrides(env.name)
        profil = profile_for(env.name, production=env.production)
        par_composant: dict[str, dict[str, Any]] = {}
        for composant in helm.components:
            propre = surcharges.components.get(composant.name)
            par_composant[composant.name] = component_override(
                helm,
                service_name,
                composant,
                env,
                profil,
                propre if propre is not None else _EMPTY_OVERRIDE,
            )
        resultat.append(
            {
                "name": env.name,
                "namespace": namespace(helm, service_name, env.name, surcharges),
                "domain": env.domain or "",
                "production": env.production,
                "log_level": surcharges.log_level or profil.log_level,
                "profile": profile_context(profil),
                "components": par_composant,
                "extra_values": dict(surcharges.extra_values),
            }
        )
    return resultat


def _empty_override() -> Any:
    """Surcharge vide, employee pour un composant absent de `helm.environments`.

    Construite une seule fois : le modele est immuable, la partager est sans
    risque et evite d'instancier un modele pydantic par composant et par
    environnement.
    """
    from forge.plugins.helm.spec import EnvironmentOverride

    return EnvironmentOverride()


#: Surcharge neutre partagee (cf. :func:`_empty_override`).
_EMPTY_OVERRIDE = _empty_override()
