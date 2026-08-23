"""Construction des artefacts d'un rôle.

Trois fichiers sur cinq sont produits à partir des seules données du catalogue
(``defaults/main.yml``, ``meta/main.yml``, ``README.md``) : la documentation des
variables ne peut donc pas diverger de leur définition. Seule la logique des
tâches est écrite à la main, un template par rôle.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from ansible_forge.catalog.definition import RoleDefinition
from ansible_forge.catalog.registry import get_role
from ansible_forge.engine.artifact import Artifact
from ansible_forge.engine.renderer import render
from ansible_forge.errors import ForgeError
from ansible_forge.models.enums import OSFamily

#: Templates spécifiques à chaque rôle : (template source, destination dans le rôle).
#: Les rôles absents de ce tableau sont au catalogue mais pas encore implémentés.
ROLE_FILES: dict[str, tuple[tuple[str, str], ...]] = {
    "common": (
        ("roles/common/tasks.yml.j2", "tasks/main.yml"),
        ("roles/common/handlers.yml.j2", "handlers/main.yml"),
        ("roles/common/vars.yml.j2", "vars/main.yml"),
        ("roles/common/templates/motd.j2.j2", "templates/motd.j2"),
    ),
    "users": (
        ("roles/users/tasks.yml.j2", "tasks/main.yml"),
        ("roles/users/vars.yml.j2", "vars/main.yml"),
        ("roles/users/templates/sudoers.j2.j2", "templates/sudoers.j2"),
    ),
    "ssh_hardening": (
        ("roles/ssh_hardening/tasks.yml.j2", "tasks/main.yml"),
        ("roles/ssh_hardening/handlers.yml.j2", "handlers/main.yml"),
        ("roles/ssh_hardening/vars.yml.j2", "vars/main.yml"),
        ("roles/ssh_hardening/templates/hardening.conf.j2.j2", "templates/hardening.conf.j2"),
    ),
    "firewall": (
        ("roles/firewall/tasks.yml.j2", "tasks/main.yml"),
        ("roles/firewall/ufw.yml.j2", "tasks/ufw.yml"),
        ("roles/firewall/firewalld.yml.j2", "tasks/firewalld.yml"),
        ("roles/firewall/handlers.yml.j2", "handlers/main.yml"),
        ("roles/firewall/vars.yml.j2", "vars/main.yml"),
    ),
    "nginx": (
        ("roles/nginx/tasks.yml.j2", "tasks/main.yml"),
        ("roles/nginx/handlers.yml.j2", "handlers/main.yml"),
        ("roles/nginx/vars.yml.j2", "vars/main.yml"),
        ("roles/nginx/templates/nginx.conf.j2.j2", "templates/nginx.conf.j2"),
        ("roles/nginx/templates/vhost.conf.j2.j2", "templates/vhost.conf.j2"),
    ),
    "docker": (
        ("roles/docker/tasks.yml.j2", "tasks/main.yml"),
        ("roles/docker/repository_debian.yml.j2", "tasks/repository_debian.yml"),
        ("roles/docker/repository_redhat.yml.j2", "tasks/repository_redhat.yml"),
        ("roles/docker/handlers.yml.j2", "handlers/main.yml"),
        ("roles/docker/vars.yml.j2", "vars/main.yml"),
        ("roles/docker/templates/daemon.json.j2.j2", "templates/daemon.json.j2"),
    ),
    "postgresql": (
        ("roles/postgresql/tasks.yml.j2", "tasks/main.yml"),
        ("roles/postgresql/handlers.yml.j2", "handlers/main.yml"),
        ("roles/postgresql/vars.yml.j2", "vars/main.yml"),
    ),
}

#: Plateformes Galaxy déclarées dans meta/main.yml, par famille d'OS.
PLATFORMS: dict[OSFamily, tuple[str, ...]] = {
    OSFamily.DEBIAN: ("Debian", "Ubuntu"),
    OSFamily.REDHAT: ("EL", "Fedora"),
}

#: Variables internes documentées dans le README, par rôle.
INTERNAL_VARS: dict[str, tuple[dict[str, str], ...]] = {
    "users": (
        {
            "name": "users_sudoers_file",
            "description": "nom du fichier déposé dans /etc/sudoers.d",
        },
        {
            "name": "users_secondary_groups",
            "description": "groupes secondaires déduits de users_accounts",
        },
        {
            "name": "users_sudo_accounts",
            "description": "comptes présents disposant d'un accès sudo",
        },
    ),
    "ssh_hardening": (
        {
            "name": "ssh_hardening_dropin_dir",
            "description": "répertoire des fichiers de configuration additionnels de sshd",
        },
        {
            "name": "ssh_hardening_service",
            "description": "nom du service SSH, résolu selon la famille d'OS",
        },
    ),
    "firewall": (
        {
            "name": "firewall_effective_backend",
            "description": "backend réellement utilisé, une fois « auto » résolu",
        },
        {
            "name": "firewall_zone",
            "description": "zone firewalld dans laquelle les règles sont posées",
        },
        {
            "name": "firewall_zone_target",
            "description": "cible de zone firewalld déduite de la politique par défaut",
        },
    ),
    "nginx": (
        {
            "name": "nginx_user",
            "description": "compte système des workers, résolu selon la famille d'OS",
        },
        {
            "name": "nginx_config_dir",
            "description": "répertoire de configuration de nginx",
        },
        {
            "name": "nginx_default_site_path",
            "description": "site par défaut de la distribution, vide si absent",
        },
    ),
    "docker": (
        {
            "name": "docker_apt_arch",
            "description": "architecture APT déduite de l'architecture de la machine",
        },
        {
            "name": "docker_packages",
            "description": "liste finale des paquets, plugin Compose inclus si demandé",
        },
    ),
    "postgresql": (
        {
            "name": "postgresql_config_dir",
            "description": "répertoire de postgresql.conf et pg_hba.conf, selon la famille d'OS",
        },
        {
            "name": "postgresql_settings",
            "description": "paramètres appliqués au serveur, construits depuis les options",
        },
        {
            "name": "postgresql_users_with_password",
            "description": "rôles disposant d'une variable de mot de passe renseignée",
        },
    ),
    "common": (
        {
            "name": "common_ntp_package",
            "description": "paquet de synchronisation horaire résolu selon la famille d'OS",
        },
        {
            "name": "common_ntp_service",
            "description": "service de synchronisation horaire résolu selon la famille d'OS",
        },
    ),
}


def implemented_roles() -> list[str]:
    """Retourne les rôles du catalogue dont les templates existent."""
    return sorted(ROLE_FILES)


def option_context(role: RoleDefinition) -> list[dict[str, Any]]:
    """Décrit les options d'un rôle pour les templates (nom de variable préfixé)."""
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


def plan_role(
    role_name: str,
    *,
    author: str,
    os_family: OSFamily,
    example_group: str,
) -> list[Artifact]:
    """Produit tous les fichiers du rôle ``role_name``."""
    role = get_role(role_name)
    if role_name not in ROLE_FILES:
        available = ", ".join(implemented_roles())
        raise ForgeError(
            f"Le rôle '{role_name}' figure au catalogue mais ses templates ne sont pas "
            f"encore disponibles. Rôles générables : {available}."
        )

    base = PurePosixPath("roles") / role.name
    platforms = list(PLATFORMS[os_family])
    options = option_context(role)
    shared_context: dict[str, Any] = {
        "role": role,
        "options": options,
        "platforms": platforms,
        "author": author,
        "example_group": example_group,
        "internal_vars": list(INTERNAL_VARS.get(role.name, ())),
    }

    artifacts = [
        Artifact(
            path=base / "defaults" / "main.yml",
            content=render("roles/_shared/defaults.yml.j2", shared_context),
        ),
        Artifact(
            path=base / "meta" / "main.yml",
            content=render("roles/_shared/meta.yml.j2", shared_context),
        ),
        Artifact(
            path=base / "README.md",
            content=render("roles/_shared/readme.md.j2", shared_context),
        ),
    ]
    artifacts.extend(
        Artifact(path=base / destination, content=render(template, shared_context))
        for template, destination in ROLE_FILES[role.name]
    )
    return artifacts
