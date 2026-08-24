"""Regles de nommage propres a Ansible.

Portage de la partie **domaine** de `ansible_forge.validation` (MIGRATION.md §3) :
`find_duplicates` et la verification de motif sont montees dans le coeur
(`forge.spec.names`), ces regex-ci restent ici parce qu'elles decrivent ce
qu'Ansible accepte, pas ce que forge accepte.
"""

from __future__ import annotations

import re

#: Nom d'environnement : pas de tiret, il sert de nom de repertoire et de groupe.
ENV_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")

#: Nom de groupe Ansible : les tirets y sont interdits.
GROUP_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]{0,63}$")

#: Nom d'hote d'inventaire : tirets et points autorises.
HOST_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,62}$")

#: Nom de compte systeme POSIX.
USER_NAME_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")

#: Nom de variable Ansible.
VAR_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]*$")

#: Noms de groupes reserves par Ansible, interdits comme groupe utilisateur.
RESERVED_GROUP_NAMES = frozenset({"all", "ungrouped", "local"})

#: Bornes d'un port TCP.
MIN_PORT = 1
MAX_PORT = 65535


def check_var_names(variables: dict[str, object], contexte: str) -> dict[str, object]:
    """Valide les noms de variables libres, ou leve `ValueError`.

    `contexte` situe l'erreur pour l'utilisateur : « group_vars », « host_vars »
    ou `inventories/<env>/group_vars/<portee>`.
    """
    for nom in variables:
        if not VAR_NAME_RE.match(nom):
            raise ValueError(
                f"Nom de variable invalide dans {contexte} : '{nom}'. "
                "Attendu : minuscules, chiffres et soulignes, commencant par une "
                "lettre ou un souligne."
            )
    return variables
