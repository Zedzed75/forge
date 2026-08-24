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


def convertir_fichier(chemin: Path) -> dict[str, Any]:
    """Charge et convertit une specification legacy Ansible."""
    return convertir_ansible(charger(chemin))
