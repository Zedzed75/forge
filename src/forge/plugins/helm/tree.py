"""Chemins que le domaine Helm va ecrire — reduction du planner a ses chemins.

`helm_forge.engine.planner.plan` construisait la liste ordonnee des fichiers du
projet **et** leur contexte de rendu. copier reprend le rendu et la
multiplicite (balises `yield`, MIGRATION.md §2.1) ; ce module ne conserve que la
liste des chemins, dont deux fichiers generes ont besoin :

* le README du chart, qui documente sa structure fichier par fichier ;
* le README du projet, qui affiche une arborescence.

**Aucun constructeur d'arborescence ASCII n'est fourni, et c'est un constat, pas
un oubli** : l'arborescence du README de projet legacy est une liste *annotee et
repliee* (chaque ligne porte un commentaire de fin de ligne, et `templates/` n'est
pas developpe). Un rendu mecanique a partir des chemins ne la reproduirait pas ;
elle reste donc ecrite litteralement dans le gabarit, ou seule la boucle sur les
environnements est dynamique. Le portage Ansible, lui, affichait une
arborescence complete : d'ou `tree.build_tree` la-bas et son absence ici.

Ce module est le **seul** endroit du domaine Helm qui duplique la connaissance
de l'arborescence de gabarit : si un gabarit est ajoute, retire ou renomme, il
faut le repercuter ici, sinon les deux README mentent. Le test de parite le
detecte, parce qu'il compare ces fichiers octet pour octet.
"""

from __future__ import annotations

from typing import Any, Final

from forge.plugins.helm.enums import AddonKind, ComponentKind

#: Ordre canonique des familles de ressources d'un composant. Il fixe l'ordre
#: des fichiers dans `templates/`, celui des lignes du README du chart, et celui
#: des cles de `domain.component_slots`.
#:
#: La charge de travail vient en tete (c'est elle que les autres ressources
#: accompagnent), puis les addons dans l'ordre canonique d'`AddonKind`, `rbac`
#: s'inserant juste apres `serviceaccount` : un Role et un RoleBinding n'ont de
#: sens qu'avec un sujet, et ce sujet est le ServiceAccount du composant.
FAMILY_ORDER: Final[tuple[str, ...]] = (
    "deployment",
    "statefulset",
    "cronjob",
    "service",
    "ingress",
    "configmap",
    "secret",
    "hpa",
    "pdb",
    "serviceaccount",
    "rbac",
    "networkpolicy",
)

#: Familles portees par le **type** du composant : au plus une par composant.
KIND_FAMILIES: Final[dict[str, str]] = {
    ComponentKind.DEPLOYMENT.value: "deployment",
    ComponentKind.STATEFULSET.value: "statefulset",
    ComponentKind.CRONJOB.value: "cronjob",
}

#: Familles portees par un **addon**, associees a l'addon qui les declenche.
#: `rbac` partage l'addon `serviceaccount` : c'est le seul moyen de generer un
#: Role et un RoleBinding qui aient un sujet.
ADDON_FAMILIES: Final[dict[str, str]] = {
    "service": AddonKind.SERVICE.value,
    "ingress": AddonKind.INGRESS.value,
    "configmap": AddonKind.CONFIGMAP.value,
    "secret": AddonKind.SECRET.value,
    "hpa": AddonKind.HPA.value,
    "pdb": AddonKind.PDB.value,
    "serviceaccount": AddonKind.SERVICEACCOUNT.value,
    "rbac": AddonKind.SERVICEACCOUNT.value,
    "networkpolicy": AddonKind.NETWORKPOLICY.value,
}

#: Libelle de chaque famille, repris tel quel dans le README du chart : ce sont
#: des noms de `kind` Kubernetes, ecrits comme l'API les ecrit.
FAMILY_LABELS: Final[dict[str, str]] = {
    "deployment": "Deployment",
    "statefulset": "StatefulSet",
    "cronjob": "CronJob",
    "service": "Service",
    "ingress": "Ingress",
    "configmap": "ConfigMap",
    "secret": "Secret",
    "hpa": "HorizontalPodAutoscaler",
    "pdb": "PodDisruptionBudget",
    "serviceaccount": "ServiceAccount",
    "rbac": "Role et RoleBinding",
    "networkpolicy": "NetworkPolicy",
    "test_connection": "Test de connexion",
}

#: Chemin, relatif au chart, du test execute par `helm test`. Contrairement aux
#: autres ressources, il n'est jamais suffixe par le nom du composant : il n'y
#: en a qu'un par chart (portage litteral du planner legacy).
TEST_CONNECTION_PATH: Final[str] = "templates/tests/test-connection.yaml"

#: Fichiers de la racine du chart, dans l'ordre du planner legacy.
CHART_ROOT_FILES: Final[tuple[str, ...]] = ("Chart.yaml", "values.yaml")

#: Fichiers du chart ecrits apres les `values-<env>.yaml`.
CHART_TAIL_FILES: Final[tuple[str, ...]] = (".helmignore", "README.md")

#: Gabarits Helm communs a tout le chart.
CHART_SHARED_TEMPLATES: Final[tuple[str, ...]] = (
    "templates/_helpers.tpl",
    "templates/NOTES.txt",
)

#: Fichiers ecrits par copier mais volontairement absents de la documentation :
#: `.copier-answers.yml` est de la plomberie de generation, pas du projet Helm
#: (MIGRATION.md §7, ecart 1).
HIDDEN_ENTRIES: Final[tuple[str, ...]] = (".copier-answers.yml",)


def chart_dir(service_name: str) -> str:
    """Repertoire du chart, relatif a la racine du domaine (`helm/`).

    Portage de `planner.chart_dir`, ou la racine etait celle du projet : la
    sortie de chaque domaine vit desormais dans son propre sous-repertoire
    (MIGRATION.md §7, ecart 2).
    """
    return f"charts/{service_name}"


def resource_filename(family: str, component_name: str) -> str:
    """Nom de fichier d'une ressource, toujours suffixe par le composant."""
    return f"{family}-{component_name}.yaml"


def component_families(component: Any) -> list[str]:
    """Familles de ressources generees pour un composant, en ordre canonique.

    Filtre par le **type** du composant (une seule charge de travail) puis par
    ses **addons**. C'est la fonction dont `derive.component_slots` est
    l'inverse : elle repond « quelles familles pour ce composant », le slot
    repond « quels composants pour cette famille ».
    """
    retenues: list[str] = []
    for famille in FAMILY_ORDER:
        attendu = KIND_FAMILIES.get(famille)
        if attendu is not None:
            if component.kind.value == attendu:
                retenues.append(famille)
            continue
        addon = ADDON_FAMILIES[famille]
        if any(existant.value == addon for existant in component.addons):
            retenues.append(famille)
    return retenues


def test_connection_target(helm: Any) -> Any | None:
    """Premier composant joignable par un Service classique, s'il existe.

    Portage litteral de `planner.first_exposed`, augmente de la condition que le
    planner appliquait a l'appelant : sans `extras.helm_tests`, aucun test n'est
    genere. Un Service headless est ecarte — il n'a pas d'adresse virtuelle, un
    test de connexion fonde sur le nom du Service n'y aurait aucun sens.
    """
    if not helm.extras.helm_tests:
        return None
    for composant in helm.components:
        if composant.has(AddonKind.SERVICE) and not composant.service.headless:
            return composant
    return None


def chart_files(spec: Any) -> list[dict[str, str]]:
    """Ressources Kubernetes generees, annotees, dans l'ordre des fichiers.

    Une entree par fichier de `templates/` propre a un composant, plus le test
    de connexion s'il est genere. Le README du chart en fait son tableau
    « Structure du chart » ; la phrase elle-meme est composee dans le gabarit,
    ce module ne fournit que les elements (`label`, `component`).
    """
    helm = spec.helm
    entrees: list[dict[str, str]] = []
    for composant in helm.components:
        for famille in component_families(composant):
            entrees.append(
                {
                    "family": famille,
                    "label": FAMILY_LABELS[famille],
                    "component": composant.name,
                    "path": f"templates/{resource_filename(famille, composant.name)}",
                }
            )
    cible = test_connection_target(helm)
    if cible is not None:
        entrees.append(
            {
                "family": "test_connection",
                "label": FAMILY_LABELS["test_connection"],
                "component": cible.name,
                "path": TEST_CONNECTION_PATH,
            }
        )
    return entrees


def expected_paths(spec: Any) -> list[str]:
    """Chemins que forge va ecrire sous `helm/`, dans l'ordre du planner legacy.

    L'ordre est celui de `planner.plan` — fichiers de niveau projet, racine du
    chart, values par environnement, gabarits communs, puis les ressources de
    chaque composant — et non l'ordre alphabetique : c'est lui que suivent les
    tableaux des README generes.

    Trois ecarts avec le legacy, tous inscrits dans MIGRATION.md §7 :
    la sentinelle `@spec` disparait (H10, ecart 3), la sortie vit sous `helm/`
    (ecart 2), et `.copier-answers.yml` s'y ajoute sans etre documente (ecart 1).
    """
    helm = spec.helm
    racine = chart_dir(spec.service.name)

    chemins: list[str] = ["README.md", ".gitignore"]
    if helm.extras.makefile:
        chemins.append("Makefile")

    chemins += [f"{racine}/{nom}" for nom in CHART_ROOT_FILES]
    chemins += [
        f"{racine}/values-{env.name}.yaml" for env in spec.service.environments
    ]
    chemins += [f"{racine}/{nom}" for nom in CHART_TAIL_FILES]
    chemins += [f"{racine}/{nom}" for nom in CHART_SHARED_TEMPLATES]
    chemins += [f"{racine}/{entree['path']}" for entree in chart_files(spec)]
    return chemins
