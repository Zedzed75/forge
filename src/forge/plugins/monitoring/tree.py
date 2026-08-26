"""Chemins que le domaine monitoring ecrit, et ce que chacun contient.

Meme role — et meme mise en garde — que dans les trois autres domaines : c'est
le seul endroit qui duplique la connaissance de l'arborescence de gabarit, et un
test le confronte au rendu reel (arbitrage R3, PLAN.md).

Une particularite : **les regles sont ecrites par environnement, pas une fois
pour toutes**. Deux raisons, et elles sont independantes — les seuils different
(la production merite plus serre que le developpement), et le namespace observe
aussi. Une regle partagee entre environnements devrait donc porter des filtres
larges et des seuils moyens, c'est-a-dire ne bien servir aucun des deux.
"""

from __future__ import annotations

from typing import Any, Final, NamedTuple


class Entry(NamedTuple):
    """Un fichier genere et la phrase qui le decrit."""

    path: str
    purpose: str


#: Repertoire de la configuration du collecteur.
PROMETHEUS_DIR: Final[str] = "prometheus"

#: Repertoire des regles d'alerte. Hors de `prometheus/` et symetrique de
#: `tests/` : les deux se lisent cote a cote, et un fichier de regles a un
#: fichier de test au meme chemin relatif.
RULES_DIR: Final[str] = "rules"

#: Repertoire des tests unitaires d'alerte.
TESTS_DIR: Final[str] = "tests"

#: Repertoire des tableaux de bord.
DASHBOARDS_DIR: Final[str] = "grafana/dashboards"


def environment_dir(environment: str) -> str:
    """Repertoire de configuration d'un environnement."""
    return f"{PROMETHEUS_DIR}/{environment}"


def rules_dir(environment: str) -> str:
    """Repertoire des regles d'un environnement."""
    return f"{RULES_DIR}/{environment}"


def rule_file(environment: str, family: str) -> str:
    """Fichier de regles d'une famille, dans un environnement."""
    return f"{rules_dir(environment)}/{family}.yml"


def test_file(environment: str, family: str) -> str:
    """Fichier de test unitaire d'une famille, dans un environnement."""
    return f"{TESTS_DIR}/{environment}/{family}.yml"


def config_file(environment: str) -> str:
    """Configuration du collecteur pour un environnement."""
    return f"{environment_dir(environment)}/prometheus.yml"


def dashboard_file(service_name: str) -> str:
    """Tableau de bord Grafana du service."""
    return f"{DASHBOARDS_DIR}/{service_name}.json"


def root_files(spec: Any) -> list[dict[str, str]]:
    """Fichiers de niveau `monitoring/`, hors configuration et regles."""
    entrees = [
        {"path": "README.md", "purpose": "Ce fichier : ce qui est surveille, et comment."},
        {
            "path": ".gitignore",
            "purpose": "Exclut les donnees du collecteur et les rendus locaux.",
        },
        {
            "path": ".copier-answers.yml",
            "purpose": "Reponses du gabarit, relues par `forge update`. Ne pas editer.",
        },
    ]
    if spec.monitoring.extras.makefile:
        entrees.append(
            {
                "path": "Makefile",
                "purpose": "Raccourcis : `make check`, `make test`, `make check ENV=prod`.",
            }
        )
    return sorted(entrees, key=lambda entree: entree["path"])


def environment_files(spec: Any, environment: str) -> list[dict[str, str]]:
    """Fichiers propres a un environnement, dans l'ordre de lecture."""
    monitoring = spec.monitoring
    entrees = [
        {
            "path": config_file(environment),
            "purpose": (
                "Configuration du collecteur : cibles, intervalle, fichiers de regles."
            ),
        }
    ]
    for famille in monitoring.family_names():
        entrees.append(
            {
                "path": rule_file(environment, famille),
                "purpose": f"Regles d'alerte de la famille « {famille} ».",
            }
        )
    for famille in monitoring.family_names():
        entrees.append(
            {
                "path": test_file(environment, famille),
                "purpose": (
                    f"Test unitaire des alertes « {famille} », joue par "
                    "`promtool test rules`."
                ),
            }
        )
    return entrees


def expected_paths(spec: Any) -> list[str]:
    """Tous les chemins ecrits par le domaine, tries."""
    chemins = [entree["path"] for entree in root_files(spec)]
    for env in spec.service.environments:
        chemins += [entree["path"] for entree in environment_files(spec, env.name)]
    if spec.monitoring.extras.dashboard:
        chemins.append(dashboard_file(spec.service.name))
    return sorted(chemins)


def dashboard_slot(spec: Any) -> list[dict[str, str]]:
    """Emplacement du tableau de bord : une entree, ou aucune.

    Motif partage avec les trois autres domaines (arbitrage R4, DESIGN.md §5.3).
    """
    return [{"name": spec.service.name}] if spec.monitoring.extras.dashboard else []
