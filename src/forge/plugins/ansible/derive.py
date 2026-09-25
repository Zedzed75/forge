"""Valeurs derivees de la specification Ansible, pretes pour les gabarits.

Ce module est le portage du **calcul de donnees** que faisaient
`ansible_forge.engine.planner` et `ansible_forge.engine.role_planner` avant de
rendre quoi que ce soit : tris, dedoublonnages, valeurs deduites, documentation
des variables. Le rendu et l'ecriture, eux, sont desormais l'affaire de copier.

Regle absolue : **toute sortie est JSON-serialisable et d'ordre fige**. Jamais
d'objet pydantic, jamais d'`Enum`, jamais de `set` : ce dict est ecrit tel quel
dans `.copier-answers.yml` et rejoue par `copier update`.

Chaque fonction porte, en commentaire, le nom de la fonction legacy dont elle
reproduit le comportement — c'est ce qui rend la parite verifiable.
"""

from __future__ import annotations

from typing import Any

from forge.plugins.ansible.catalog.definition import RoleDefinition
from forge.plugins.ansible.catalog.collections import requirements_for
from forge.plugins.ansible.catalog.registry import (
    collection_requirements_for,
    get_role,
    role_names,
)

#: Comment placed on the free-form variables the user typed in.
#: The text used to be copied **word for word** from the legacy
#: (`planner.UNDOCUMENTED`), which forbade touching it: the parity snapshots
#: compared the two outputs. Those snapshots went away with `_legacy/` in
#: phase 10, and the constraint with them.
UNDOCUMENTED = "TODO: describe what this variable does and its allowed values."

#: Plateformes Galaxy declarees dans `meta/main.yml`, par famille d'OS.
#: Portage de `role_planner.PLATFORMS` (clefs converties en chaines : le dict
#: `domain` ne doit contenir aucun `Enum`).
PLATFORMS: dict[str, tuple[str, ...]] = {
    "debian": ("Debian", "Ubuntu"),
    "redhat": ("EL", "Fedora"),
}

#: Internal variables documented in the README of each role.
#: Port of `role_planner.INTERNAL_VARS`: these texts are written into the
#: generated files, so they follow the language of the output.
INTERNAL_VARS: dict[str, tuple[dict[str, str], ...]] = {
    "users": (
        {
            "name": "users_sudoers_file",
            "description": "name of the file written to /etc/sudoers.d",
        },
        {
            "name": "users_secondary_groups",
            "description": "secondary groups derived from users_accounts",
        },
        {
            "name": "users_sudo_accounts",
            "description": "present accounts that have sudo access",
        },
    ),
    "ssh_hardening": (
        {
            "name": "ssh_hardening_dropin_dir",
            "description": "directory of the additional configuration files of sshd",
        },
        {
            "name": "ssh_hardening_service",
            "description": "name of the SSH service, resolved per OS family",
        },
    ),
    "firewall": (
        {
            "name": "firewall_effective_backend",
            "description": "backend actually used, once \"auto\" is resolved",
        },
        {
            "name": "firewall_zone",
            "description": "firewalld zone the rules are set in",
        },
        {
            "name": "firewall_zone_target",
            "description": "firewalld zone target derived from the default policy",
        },
    ),
    "nginx": (
        {
            "name": "nginx_user",
            "description": "system account of the workers, resolved per OS family",
        },
        {
            "name": "nginx_config_dir",
            "description": "configuration directory of nginx",
        },
        {
            "name": "nginx_default_site_path",
            "description": "default site of the distribution, empty if there is none",
        },
    ),
    "docker": (
        {
            "name": "docker_apt_arch",
            "description": "APT architecture derived from the architecture of the machine",
        },
        {
            "name": "docker_packages",
            "description": "final list of the packages, Compose plugin included if requested",
        },
    ),
    "postgresql": (
        {
            "name": "postgresql_config_dir",
            "description": "directory of postgresql.conf and pg_hba.conf, per OS family",
        },
        {
            "name": "postgresql_settings",
            "description": "parameters applied to the server, built from the options",
        },
        {
            "name": "postgresql_users_with_password",
            "description": "roles that have a password variable filled in",
        },
    ),
    "common": (
        {
            "name": "common_ntp_package",
            "description": "time synchronisation package resolved per OS family",
        },
        {
            "name": "common_ntp_service",
            "description": "time synchronisation service resolved per OS family",
        },
    ),
}


# ---------------------------------------------------------------------------
# Variables libres
# ---------------------------------------------------------------------------


def free_vars(values: dict[str, Any]) -> list[dict[str, Any]]:
    """Convertit un dictionnaire de variables libres en entrees documentees.

    Portage de `planner._free_vars`. Le tri par nom est ce qui rend les fichiers
    `group_vars` et `host_vars` reproductibles quel que soit l'ordre de saisie.
    """
    return [
        {"name": nom, "description": UNDOCUMENTED, "value": values[nom]}
        for nom in sorted(values)
    ]


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------


def option_context(role: RoleDefinition) -> list[dict[str, Any]]:
    """Decrit les options d'un role pour les gabarits (nom de variable prefixe).

    Portage de `role_planner.option_context`. `default` est la valeur du
    **catalogue**, pas celle choisie dans la spec : `roles/<r>/defaults/main.yml`
    documente le role tel qu'il est reutilisable, et les choix du projet vont
    dans `group_vars/all.yml` (cf. :func:`role_overrides`).
    """
    return [
        {
            "name": option.name,
            "var_name": f"{role.name}_{option.name}",
            "description": option.description,
            "allowed": option.allowed,
            "default": option.default,
        }
        for option in role.options
    ]


def role_context(
    role_name: str,
    *,
    author: str,
    os_family: str,
    example_group: str,
) -> dict[str, Any]:
    """Contexte complet d'un role : catalogue + valeurs deduites du projet.

    Portage du `shared_context` de `role_planner.plan_role`, augmente des champs
    du `RoleDefinition` que les gabarits lisaient directement sur l'objet
    (`name`, `summary`, `tags`, `handlers`, `collections`).
    """
    role = get_role(role_name)
    return {
        "name": role.name,
        "summary": role.summary,
        "tags": list(role.tags),
        "handlers": list(role.handlers),
        "collections": _role_collections(role.collections),
        "os_families": list(role.os_families),
        "options": option_context(role),
        "platforms": list(PLATFORMS[os_family]),
        "author": author,
        "example_group": example_group,
        "internal_vars": [dict(item) for item in INTERNAL_VARS.get(role.name, ())],
    }


def first_group_using(groups: list[Any]) -> dict[str, str]:
    """Associe chaque role au premier groupe qui l'applique (exemple du README).

    Portage de `planner._first_group_using` : l'ordre de `groups` n'est pas trie,
    c'est celui de la specification.
    """
    mapping: dict[str, str] = {}
    for groupe in groups:
        for nom in groupe.roles:
            mapping.setdefault(nom, groupe.name)
    return mapping


def role_contexts(ansible: Any, *, author: str) -> list[dict[str, Any]]:
    """Contextes des roles reellement appliques, dans l'ordre du catalogue.

    Portage de `planner._roles` : l'ordre vient du catalogue, jamais de
    l'alphabet, et le groupe d'exemple retombe sur le premier groupe declare.
    """
    exemples = first_group_using(ansible.groups)
    defaut = ansible.groups[0].name
    return [
        role_context(
            nom,
            author=author,
            os_family=ansible.os_family.value,
            example_group=exemples.get(nom, defaut),
        )
        for nom in ansible.ordered_used_roles()
    ]


def role_slots(contextes: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Un emplacement par role du catalogue, vide si le role n'est pas applique.

    Sert aux gabarits propres a un role :
    `roles/[% yield r from domain.role_slots.firewall %][[ r.name ]][% endyield %]/...`
    Une liste vide fait disparaitre le fichier ; les sept clefs sont **toujours**
    presentes, pour qu'un gabarit ne puisse jamais referencer une clef absente.
    """
    par_nom = {contexte["name"]: contexte for contexte in contextes}
    return {
        nom: ([par_nom[nom]] if nom in par_nom else [])
        for nom in role_names()
    }


def collection_users(ansible: Any) -> dict[str, list[str]]:
    """Associe chaque collection Galaxy aux roles qui l'exigent.

    Portage de `planner._collection_users` : collections triees par nom, roles
    tries par nom a l'interieur de chaque collection.
    """
    utilisateurs: dict[str, list[str]] = {}
    for nom_role in ansible.ordered_used_roles():
        for collection in get_role(nom_role).collections:
            utilisateurs.setdefault(collection, []).append(nom_role)
    return {nom: sorted(roles) for nom, roles in sorted(utilisateurs.items())}


def collections(ansible: Any) -> list[dict[str, str]]:
    """Collections Galaxy requises par les roles appliques, avec leur contrainte de version.

    Triees par nom et dedoublonnees. Chaque entree porte de quoi ecrire une
    dependance complete : le nom, l'intervalle accepte, la version contre
    laquelle forge valide, et la raison du plancher reprise en commentaire.
    """
    return [
        {
            "name": besoin.name,
            "version": besoin.version,
            "validated": besoin.validated,
            "reason": besoin.reason,
        }
        for besoin in collection_requirements_for(ansible.ordered_used_roles())
    ]


def _role_collections(names: tuple[str, ...]) -> list[dict[str, str]]:
    """Collections d'un role : le nom et l'intervalle, rien de plus.

    La justification du plancher n'est portee qu'une fois, par `collections` :
    la repeter par role la recopierait dans `.copier-answers.yml` autant de fois
    qu'il y a de roles, pour un fichier cense rester relisible.
    """
    return [
        {"name": besoin.name, "version": besoin.version}
        for besoin in requirements_for(names)
    ]


def role_overrides(ansible: Any) -> list[dict[str, Any]]:
    """Options de role dont la valeur choisie differe du defaut du catalogue.

    Portage de `planner._role_overrides`. Seules ces valeurs sont ecrites dans
    `group_vars/all.yml` : les autres restent documentees a un seul endroit,
    `roles/<role>/defaults/main.yml`. L'ordre est celui du catalogue (roles),
    puis celui de declaration des options.
    """
    surcharges: list[dict[str, Any]] = []
    for nom_role in ansible.ordered_used_roles():
        role = get_role(nom_role)
        choisies = ansible.role_options(nom_role)
        for option in role.options:
            valeur = choisies.get(option.name, option.default)
            if valeur != option.default:
                surcharges.append(
                    {
                        "name": f"{role.name}_{option.name}",
                        "description": option.description,
                        "allowed": option.allowed,
                        "value": valeur,
                    }
                )
    return surcharges


# ---------------------------------------------------------------------------
# Groupes, hotes et environnements
# ---------------------------------------------------------------------------


def _group_base(groupe: Any, contextes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Partie commune aux groupes de projet et aux groupes d'inventaire.

    Les deux niveaux exposent la meme forme — `role_names` pour les simples noms
    (l'inventaire et le README les joignent par des virgules), `roles` pour les
    definitions completes — afin qu'un gabarit n'ait jamais a se demander a quel
    niveau il se trouve. Les definitions sont donc repetees dans le fichier de
    reponses ; c'est le prix assume de cette uniformite.
    """
    return {
        "name": groupe.name,
        "description": groupe.description,
        "role_names": list(groupe.roles),
        "roles": [contextes[nom] for nom in groupe.roles],
    }


def project_groups(
    ansible: Any, contextes: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Groupes du projet, dans l'ordre **non trie** de la specification.

    Portage des contextes de `planner._root_vars` et `planner._playbooks` :
    `group_vars/<groupe>.yml` et `playbooks/<groupe>.yml` recoivent les
    definitions completes des roles du groupe, plus ses variables libres.
    """
    par_nom = {contexte["name"]: contexte for contexte in contextes}
    return [
        {**_group_base(groupe, par_nom), "variables": free_vars(groupe.vars)}
        for groupe in ansible.groups
    ]


def host_context(hote: Any) -> dict[str, Any]:
    """Une machine d'inventaire, telle que la voient `hosts.yml` et `host_vars`."""
    return {
        "name": hote.name,
        "ansible_host": hote.ansible_host,
        "ansible_port": hote.ansible_port,
        "ansible_user": hote.ansible_user,
        "vars": dict(hote.vars),
        "variables": free_vars(hote.vars),
    }


def vault_secrets(ansible: Any, env_name: str) -> list[dict[str, str]]:
    """Secrets attendus par les roles selectionnes, pour un environnement.

    Portage de `planner._vault_secrets` : aujourd'hui seul `postgresql` declare
    des mots de passe ; a defaut, un secret d'exemple est ecrit pour que le
    fichier modele ne soit jamais vide.
    """
    secrets: list[dict[str, str]] = []
    if "postgresql" in ansible.used_roles():
        for utilisateur in ansible.role_options("postgresql").get("db_users", []):
            variable = utilisateur.get("password_var")
            if variable:
                secrets.append(
                    {
                        "name": variable,
                        "description": (
                            f"Password of the \"{utilisateur.get('name', '?')}\" PostgreSQL "
                            f"role in the \"{env_name}\" environment."
                        ),
                        "placeholder": "CHANGE-ME",
                    }
                )
    if not secrets:
        secrets.append(
            {
                "name": "vault_example_secret",
                "description": (
                    "Example secret. Replace it with your own, one per line, each one "
                    "preceded by a comment."
                ),
                "placeholder": "CHANGE-ME",
            }
        )
    return secrets


def environments(spec: Any, contextes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Un environnement par entree de `service.environments`, ordre de promotion.

    Reunit ce que `planner._inventories` calculait par environnement : groupes
    d'inventaire (hotes tries par nom), liste **plate** des hotes, variables de
    portee `all`, variables par groupe et secrets de coffre.
    """
    ansible = spec.ansible
    par_nom = {contexte["name"]: contexte for contexte in contextes}
    resultat: list[dict[str, Any]] = []
    for env in spec.service.environments:
        par_groupe = ansible.hosts.get(env.name, {})
        portees = ansible.group_vars.get(env.name, {})
        groupes = []
        for groupe in ansible.groups:
            hotes = sorted(par_groupe.get(groupe.name, []), key=lambda h: h.name)
            groupes.append(
                {
                    **_group_base(groupe, par_nom),
                    "hosts": [host_context(hote) for hote in hotes],
                    "variables": free_vars(portees.get(groupe.name, {})),
                }
            )
        plats = sorted(
            (hote for hotes in par_groupe.values() for hote in hotes),
            key=lambda h: h.name,
        )
        resultat.append(
            {
                "name": env.name,
                "domain": env.domain or "",
                "production": env.production,
                "host_count": len(plats),
                "groups": groupes,
                "hosts": [host_context(hote) for hote in plats],
                "vars_all": free_vars(portees.get("all", {})),
                "group_vars": {
                    groupe.name: free_vars(portees.get(groupe.name, {}))
                    for groupe in ansible.groups
                },
                "vault_secrets": vault_secrets(ansible, env.name),
            }
        )
    return resultat
