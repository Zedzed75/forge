"""Projection de la specification unifiee vers le dict `domain` de copier.

Implementation du hook `forge_answers` (DESIGN.md §2.2) pour le domaine Helm, et
piece centrale du portage : tous les gabarits lisent ce que ce module produit.

Contrat, tenu par :func:`build` :

* **memes noms que dans le generateur legacy** — convertir un gabarit se reduit
  a prefixer `domain.` (ou a employer la variable de boucle d'un `yield`) ;
* **JSON-serialisable** — aucun objet pydantic, aucun `Enum`, aucun `set` : le
  dict est ecrit tel quel dans `.copier-answers.yml` et rejoue par
  `copier update` ;
* **ordre fige** — cles inserees dans un ordre stable, listes dans l'ordre de la
  specification, jamais par hasard.

Le calcul vit dans :mod:`forge.plugins.helm.derive` (partie statique),
:mod:`forge.plugins.helm.derive_env` (partie par environnement) et
:mod:`forge.plugins.helm.tree` (chemins generes) ; ce module ne fait
qu'assembler, et porter les controles croises que le sous-modele ne peut pas
faire lui-meme.
"""

from __future__ import annotations

from typing import Any

from forge.plugins.helm import derive, derive_env, tree
from forge.plugins.helm.constants import (
    MAX_DESCRIPTION_LENGTH,
    MAX_ENVIRONMENT_NAME_LENGTH,
    MAX_SERVICE_NAME_LENGTH,
)
from forge.plugins.helm.enums import NamespaceStrategy
from forge.plugins.helm.names import is_valid_email
from forge.plugins.helm.profiles import is_production_name
from forge.plugins_api import checks
from forge.plugins_api.types import Issue


def build(spec: Any) -> dict[str, Any]:
    """Construit le dict `domain` passe a copier pour le domaine Helm.

    `spec` est le modele racine assemble : `spec.service` (bloc partage) et
    `spec.helm` (instance de `HelmSpec`).
    """
    service = spec.service
    helm = spec.helm

    contextes = derive.components(helm, service_name=service.name)

    return {
        # -- identite du chart -----------------------------------------------
        "chart_dir": tree.chart_dir(service.name),
        # Prefixe de tous les helpers Helm generes : `<chart>.<suffixe>`.
        # Portage de la cle `helper` du contexte de rendu legacy.
        "helper": service.name,
        "chart_version": helm.chart_version,
        "app_version": helm.app_version,
        **derive.maintainer(service),
        "kubernetes": derive.kubernetes(helm),
        # -- disposition et namespaces ---------------------------------------
        "layout": helm.layout.value,
        "namespace_strategy": helm.namespace_strategy.value,
        "create_namespace": helm.create_namespace,
        # -- image, secrets, annexes ------------------------------------------
        "image": derive.image(helm),
        "secrets": derive.secrets(helm),
        "extras": derive.extras(helm),
        # -- composants --------------------------------------------------------
        "components": contextes,
        "component_names": [contexte["name"] for contexte in contextes],
        "component_slots": derive.component_slots(helm, contextes),
        # -- environnements -----------------------------------------------------
        "env_names": [env.name for env in service.environments],
        "default_env": service.environments[0].name,
        "environments": derive_env.environments(spec),
        # -- documentation -------------------------------------------------------
        "chart_files": tree.chart_files(spec),
        "expected_paths": tree.expected_paths(spec),
    }


# ---------------------------------------------------------------------------
# Controles croises
# ---------------------------------------------------------------------------


def cross_check(spec: Any) -> list[Issue]:
    """Controles que `HelmSpec` ne peut pas faire : elle ne voit pas `service:`.

    Quatre familles, toutes justifiees par un arbitrage de MIGRATION.md :

    * **H4** — les cles de `helm.environments` doivent figurer dans
      `service.environments`, qui porte desormais le nom et l'ordre ;
    * **H6** — plafonds de longueur et format d'adresse : ce sont des
      contraintes de `Chart.yaml` et du budget de 63 caracteres des noms de
      ressources Kubernetes, que le coeur n'a pas a connaitre ;
    * **namespaces `custom`** — un environnement absent de `helm.environments`
      echappe au controle du modele ;
    * **H2** — divergence entre le drapeau `production` et la reconnaissance par
      le nom, signalee en *warning* plutot que tranchee en silence.

    L'ordre de la liste est deterministe : elle est affichee telle quelle.
    """
    helm = getattr(spec, "helm", None)
    if helm is None:
        return []

    issues: list[Issue] = []
    issues.extend(
        checks.unknown_environments(
            spec, "helm", {"helm.environments": helm.environments}
        )
    )
    issues.extend(_check_limits(spec))
    issues.extend(_check_custom_namespaces(spec, helm))
    issues.extend(_check_production_divergence(spec))
    return issues


def _check_limits(spec: Any) -> list[Issue]:
    """Applique les plafonds de longueur et le format d'adresse (H6).

    Ces controles portent sur le bloc partage `service:`, mais ce sont des
    contraintes Helm : le nom du service devient le nom du chart et le prefixe
    de toutes les ressources, la description est reprise dans `Chart.yaml`, et
    l'adresse alimente sa liste `maintainers`.
    """
    service = spec.service
    issues: list[Issue] = []

    if len(service.name) > MAX_SERVICE_NAME_LENGTH:
        issues.append(
            Issue(
                level="error",
                message=(
                    f"service.name fait {len(service.name)} caracteres ; Helm en "
                    f"admet {MAX_SERVICE_NAME_LENGTH} au plus, le nom servant de "
                    "nom de chart et de prefixe a toutes les ressources."
                ),
                hint=(
                    "Raccourcissez service.name : Kubernetes plafonne un nom de "
                    "ressource a 63 caracteres, suffixes compris."
                ),
                domains=("helm",),
            )
        )

    if len(service.description) > MAX_DESCRIPTION_LENGTH:
        issues.append(
            Issue(
                level="error",
                message=(
                    f"service.description fait {len(service.description)} "
                    f"caracteres ; le champ description de Chart.yaml en admet "
                    f"{MAX_DESCRIPTION_LENGTH} au plus."
                ),
                hint=(
                    "Resumez service.description en une ligne ; le detail a sa "
                    "place dans le README du projet."
                ),
                domains=("helm",),
            )
        )

    for env in service.environments:
        if len(env.name) > MAX_ENVIRONMENT_NAME_LENGTH:
            issues.append(
                Issue(
                    level="error",
                    message=(
                        f"le nom d'environnement '{env.name}' fait "
                        f"{len(env.name)} caracteres ; Helm en admet "
                        f"{MAX_ENVIRONMENT_NAME_LENGTH} au plus."
                    ),
                    hint=(
                        f"Raccourcissez '{env.name}' : ce nom entre dans le "
                        "namespace derive et dans l'hote d'Ingress."
                    ),
                    domains=("helm",),
                )
            )

    if service.owner_email and not is_valid_email(service.owner_email):
        issues.append(
            Issue(
                level="error",
                message=(
                    f"service.owner_email '{service.owner_email}' n'est pas une "
                    "adresse electronique valide ; elle alimente la liste "
                    "maintainers de Chart.yaml."
                ),
                hint="Employez la forme 'equipe@exemple.fr'.",
                domains=("helm",),
            )
        )
    return issues


def _check_custom_namespaces(spec: Any, helm: Any) -> list[Issue]:
    """Exige un namespace explicite pour chaque environnement, strategie `custom`.

    `HelmSpec` verifie deja les environnements presents dans
    `helm.environments` ; ce controle ajoute ceux qui n'y figurent pas du tout,
    et que seule la liste complete de `service.environments` revele.
    """
    if helm.namespace_strategy is not NamespaceStrategy.CUSTOM:
        return []
    return [
        Issue(
            level="error",
            message=(
                f"environnement '{env.name}' : la strategie de namespace "
                '"custom" exige un namespace explicite, et aucun n\'est declare.'
            ),
            hint=(
                f"Renseignez helm.environments.{env.name}.namespace, ou passez "
                "helm.namespace_strategy a per_env pour deriver "
                f"'{spec.service.name}-{env.name}'."
            ),
            domains=("helm",),
        )
        for env in spec.service.environments
        if helm.overrides(env.name).namespace is None
    ]


def _check_production_divergence(spec: Any) -> list[Issue]:
    """Signale un desaccord entre `production:` et le nom de l'environnement (H2).

    Deux sources decrivent la meme chose : le drapeau explicite du coeur et la
    reconnaissance du nom heritee du legacy. Le drapeau l'emporte, mais le
    silence serait un piege — un environnement nomme `prod` sans
    `production: true` recoit bien le profil de production par son nom, alors
    qu'un environnement nomme `live` avec `production: true` le recoit par le
    drapeau : dans les deux cas l'utilisateur croit avoir ecrit autre chose.
    """
    issues: list[Issue] = []
    for env in spec.service.environments:
        par_nom = is_production_name(env.name)
        if env.production == par_nom:
            continue
        if env.production:
            message = (
                f"l'environnement '{env.name}' porte production: true alors que "
                "son nom n'est pas reconnu comme un nom de production ; le "
                "drapeau l'emporte et le profil prod est applique."
            )
            hint = (
                f"Renommez '{env.name}' en 'prod' pour lever l'ambiguite, ou "
                "conservez ce nom si votre convention le veut ainsi."
            )
        else:
            message = (
                f"l'environnement '{env.name}' porte un nom de production mais "
                "pas production: true ; le profil prod lui est applique par "
                "reconnaissance du nom."
            )
            hint = (
                f"Ajoutez production: true a l'environnement '{env.name}' pour "
                "rendre l'intention explicite."
            )
        issues.append(
            Issue(level="warning", message=message, hint=hint, domains=("helm",))
        )
    return issues
