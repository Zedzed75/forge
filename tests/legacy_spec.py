"""Conversion des specifications legacy vers `forge.yml` — helper de test.

Decision Q5 (`DESIGN.md` §8) : forge ne livre **pas** de commande `forge import`.
Aucun `forge.yml` legacy n'existe hors des depots d'origine ; seul le harnais de
parite en a besoin, pour rejouer les specifications d'`ansible-forge` et de
`helm-forge` contre le plugin porte.

La conversion est purement structurelle : elle deplace des champs, elle n'en
invente ni n'en supprime aucun.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

#: Champs de la specification Ansible legacy qui restent dans la section `ansible:`.
CHAMPS_ANSIBLE = (
    "os_family",
    "remote_user",
    "become",
    "ssh_port",
    "python_interpreter",
    "options",
    "groups",
    "roles",
)

#: Options legacy qui n'ont plus de sens dans forge (cf. MIGRATION.md §7).
OPTIONS_ABANDONNEES = ("embed_spec",)

#: Champs de la specification Helm legacy qui restent dans la section `helm:`.
CHAMPS_HELM = (
    "kubernetes",
    "layout",
    "namespace_strategy",
    "create_namespace",
    "image",
    "components",
    "secrets",
    "extras",
)

#: Champs d'`app` qui restent dans `helm:` ; le reste monte dans `service:`.
CHAMPS_HELM_APP = ("chart_version", "app_version")

#: Cles d'`extras` non portees (arbitrages H7 et H8) : aucun gabarit ne les
#: rendait, et la CI est de niveau depot (decision Q6).
EXTRAS_ABANDONNES = ("helmfile", "ci")

#: Blocs de composant non portes (arbitrage H7, hors perimetre phase 4).
COMPOSANT_ABANDONNES = ("servicemonitor",)

#: Cles portees par un environnement legacy qui deviennent des surcharges
#: `helm.environments.<env>` ; `name` devient la cle du dict (arbitrage H4).
CLES_ENVIRONNEMENT_HELM = ("namespace", "log_level", "components", "extra_values")

#: Defauts d'`AppMeta` legacy, reappliques ici parce que `service.owner` et
#: `service.owner_email` n'ont pas les memes defauts dans le coeur.
DEFAUT_MAINTAINER_NAME = "unknown"
DEFAUT_MAINTAINER_EMAIL = "unknown@example.com"


def charger(chemin: Path) -> dict[str, Any]:
    """Charge une specification legacy telle quelle."""
    return yaml.safe_load(Path(chemin).read_text(encoding="utf-8"))


def convertir_ansible(legacy: dict[str, Any]) -> dict[str, Any]:
    """Traduit une specification `ansible-forge` en `forge.yml` unifie.

    L'identite du projet monte dans le bloc partage `service:` ; les hotes et
    les variables d'inventaire, portes par chaque environnement dans le legacy,
    sont regroupes par environnement sous `ansible.hosts` et `ansible.group_vars`
    (cf. `DESIGN.md` §3.1).
    """
    environnements = legacy.get("environments") or []

    service: dict[str, Any] = {
        "name": legacy["project_name"],
        "description": legacy.get("description") or f"Projet {legacy['project_name']}",
        "owner": legacy.get("author") or "Equipe",
        "environments": [{"name": env["name"]} for env in environnements],
    }

    ansible: dict[str, Any] = {}
    for champ in CHAMPS_ANSIBLE:
        if champ in legacy and legacy[champ] is not None:
            ansible[champ] = legacy[champ]

    options = ansible.get("options")
    if isinstance(options, dict):
        ansible["options"] = {
            cle: valeur
            for cle, valeur in options.items()
            if cle not in OPTIONS_ABANDONNEES
        }

    hosts: dict[str, Any] = {}
    group_vars: dict[str, Any] = {}
    for env in environnements:
        if env.get("hosts"):
            hosts[env["name"]] = env["hosts"]
        if env.get("group_vars"):
            group_vars[env["name"]] = env["group_vars"]
    if hosts:
        ansible["hosts"] = hosts
    if group_vars:
        ansible["group_vars"] = group_vars

    return {"forge_version": 1, "service": service, "ansible": ansible}


def convertir_helm(legacy: dict[str, Any]) -> dict[str, Any]:
    """Traduit une specification `helm-forge` en `forge.yml` unifie.

    Le bloc `app` est scinde : le nom, la description et le mainteneur montent
    dans `service:`, les deux versions de chart restent dans `helm:`. La liste
    `environments`, qui portait son `name` dans le legacy, devient le dict
    `helm.environments` cle par nom, l'ordre etant desormais porte par
    `service.environments` (arbitrage H4, cf. `DESIGN.md` §3.1).

    Les champs abandonnes par les arbitrages H7 et H8 sont retires : les
    conserver ferait echouer la validation, `HelmSpec` etant `extra="forbid"`.
    """
    app = legacy.get("app") or {}
    environnements = legacy.get("environments") or []

    service: dict[str, Any] = {
        "name": app["name"],
        "description": app["description"],
        "owner": app.get("maintainer_name") or DEFAUT_MAINTAINER_NAME,
        "owner_email": app.get("maintainer_email") or DEFAUT_MAINTAINER_EMAIL,
        "environments": [{"name": env["name"]} for env in environnements],
    }

    helm: dict[str, Any] = {}
    for champ in CHAMPS_HELM_APP:
        if app.get(champ) is not None:
            helm[champ] = app[champ]
    for champ in CHAMPS_HELM:
        if legacy.get(champ) is not None:
            helm[champ] = legacy[champ]

    extras = helm.get("extras")
    if isinstance(extras, dict):
        helm["extras"] = {
            cle: valeur for cle, valeur in extras.items() if cle not in EXTRAS_ABANDONNES
        }

    composants = helm.get("components")
    if isinstance(composants, list):
        helm["components"] = [
            {
                cle: valeur
                for cle, valeur in composant.items()
                if cle not in COMPOSANT_ABANDONNES
            }
            if isinstance(composant, dict)
            else composant
            for composant in composants
        ]

    surcharges: dict[str, Any] = {}
    for env in environnements:
        propres = {
            cle: env[cle]
            for cle in CLES_ENVIRONNEMENT_HELM
            if env.get(cle) not in (None, {}, [])
        }
        if propres:
            surcharges[env["name"]] = propres
    if surcharges:
        helm["environments"] = surcharges

    return {"forge_version": 1, "service": service, "helm": helm}


def convertir_fichier(chemin: Path) -> dict[str, Any]:
    """Charge et convertit une specification legacy Ansible."""
    return convertir_ansible(charger(chemin))


def convertir_fichier_helm(chemin: Path) -> dict[str, Any]:
    """Charge et convertit une specification legacy Helm."""
    return convertir_helm(charger(chemin))
