"""Transformation d'une :class:`ProjectSpec` en liste d'artefacts.

Ce module est **pur** : il ne lit ni n'écrit aucun fichier. C'est ce qui permet
à ``--dry-run``, aux tests golden et à la génération réelle de partager le même
code, et ce qui rend la sortie reproductible.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from ansible_forge.catalog.registry import collections_for, get_role
from ansible_forge.engine.artifact import Artifact, sort_artifacts
from ansible_forge.engine.renderer import render
from ansible_forge.engine.role_planner import plan_role
from ansible_forge.engine.writer import build_tree
from ansible_forge.models.spec import EnvironmentSpec, ProjectSpec
from ansible_forge.spec_io import dump_spec

#: Commentaire posé sur les variables libres saisies par l'utilisateur.
UNDOCUMENTED = "TODO : décrire le rôle de cette variable et ses valeurs admises."


def plan(spec: ProjectSpec) -> list[Artifact]:
    """Produit tous les fichiers du projet décrit par ``spec``, triés par chemin."""
    artifacts: list[Artifact] = []
    artifacts.extend(_project_files(spec))
    artifacts.extend(_root_vars(spec))
    artifacts.extend(_inventories(spec))
    artifacts.extend(_playbooks(spec))
    artifacts.extend(_roles(spec))
    artifacts.append(_readme(spec, artifacts))
    return sort_artifacts(artifacts)


def plan_paths(spec: ProjectSpec) -> list[str]:
    """Retourne les chemins qui seraient générés, sans construire le contenu final."""
    return [artifact.posix_path for artifact in plan(spec)]


# ---------------------------------------------------------------------------
# Fichiers de la racine du projet
# ---------------------------------------------------------------------------


def _project_files(spec: ProjectSpec) -> list[Artifact]:
    """ansible.cfg, requirements.yml, configurations de lint et copie de la spec."""
    default_env = spec.environments[0].name
    collections = collections_for(spec.ordered_used_roles())
    artifacts = [
        Artifact(
            path=PurePosixPath("ansible.cfg"),
            content=render(
                "project/ansible.cfg.j2", {"spec": spec, "default_env": default_env}
            ),
        ),
        Artifact(
            path=PurePosixPath("requirements.yml"),
            content=render(
                "project/requirements.yml.j2",
                {
                    "spec": spec,
                    "collections": collections,
                    "collection_users": _collection_users(spec),
                },
            ),
        ),
    ]

    if spec.options.write_lint_config:
        artifacts.extend(
            [
                Artifact(
                    path=PurePosixPath(".gitignore"),
                    content=render("project/gitignore.j2", {"spec": spec}),
                ),
                Artifact(
                    path=PurePosixPath(".yamllint"),
                    content=render("project/yamllint.j2", {"spec": spec}),
                ),
                Artifact(
                    path=PurePosixPath(".ansible-lint"),
                    content=render("project/ansible_lint.j2", {"spec": spec}),
                ),
            ]
        )

    if spec.options.write_ci:
        artifacts.append(
            Artifact(
                path=PurePosixPath(".github/workflows/ansible-lint.yml"),
                content=render(
                    "project/ci.yml.j2",
                    {"spec": spec, "environments": [env.name for env in spec.environments]},
                ),
            )
        )

    if spec.options.embed_spec:
        artifacts.append(
            Artifact(path=PurePosixPath("forge.yml"), content=dump_spec(spec))
        )
    return artifacts


def _readme(spec: ProjectSpec, artifacts: list[Artifact]) -> Artifact:
    """README du projet, dont l'arborescence est déduite des artefacts déjà planifiés."""
    paths = [artifact.posix_path for artifact in artifacts] + ["README.md"]
    context = {
        "spec": spec,
        "tree": build_tree(paths, spec.project_name),
        "default_env": spec.environments[0].name,
        "collections": collections_for(spec.ordered_used_roles()),
        "groups": spec.groups,
        "roles": [get_role(name) for name in spec.ordered_used_roles()],
        "environments": [
            {"name": env.name, "host_count": len(env.all_hosts())} for env in spec.environments
        ],
    }
    return Artifact(path=PurePosixPath("README.md"), content=render("project/readme.md.j2", context))


def _collection_users(spec: ProjectSpec) -> dict[str, list[str]]:
    """Associe chaque collection Galaxy aux rôles qui l'exigent."""
    users: dict[str, list[str]] = {}
    for role_name in spec.ordered_used_roles():
        for collection in get_role(role_name).collections:
            users.setdefault(collection, []).append(role_name)
    return {name: sorted(roles) for name, roles in sorted(users.items())}


# ---------------------------------------------------------------------------
# Variables de la racine du projet
# ---------------------------------------------------------------------------


def _root_vars(spec: ProjectSpec) -> list[Artifact]:
    """group_vars/all.yml et group_vars/<groupe>.yml."""
    artifacts = [
        Artifact(
            path=PurePosixPath("group_vars/all.yml"),
            content=render(
                "project/vars/group_all.yml.j2",
                {"spec": spec, "overrides": _role_overrides(spec)},
            ),
        )
    ]
    for group in spec.groups:
        artifacts.append(
            Artifact(
                path=PurePosixPath(f"group_vars/{group.name}.yml"),
                content=render(
                    "project/vars/group.yml.j2",
                    {
                        "spec": spec,
                        "group": group,
                        "roles": [get_role(name) for name in group.roles],
                        "variables": _free_vars(group.vars),
                    },
                ),
            )
        )
    return artifacts


def _role_overrides(spec: ProjectSpec) -> list[dict[str, Any]]:
    """Liste les options de rôle dont la valeur diffère du défaut du catalogue.

    Seules ces valeurs sont écrites dans ``group_vars/all.yml`` : les autres
    restent documentées à un seul endroit, ``roles/<rôle>/defaults/main.yml``.
    """
    overrides: list[dict[str, Any]] = []
    for role_name in spec.ordered_used_roles():
        role = get_role(role_name)
        chosen = spec.role_options(role_name)
        for option in role.options:
            value = chosen.get(option.name, option.default)
            if value != option.default:
                overrides.append(
                    {
                        "name": f"{role.name}_{option.name}",
                        "description": option.description,
                        "allowed": option.allowed,
                        "value": value,
                    }
                )
    return overrides


def _free_vars(values: dict[str, Any]) -> list[dict[str, Any]]:
    """Convertit un dictionnaire de variables libres en entrées documentées."""
    return [
        {"name": name, "description": UNDOCUMENTED, "value": values[name]}
        for name in sorted(values)
    ]


# ---------------------------------------------------------------------------
# Inventaires
# ---------------------------------------------------------------------------


def _inventories(spec: ProjectSpec) -> list[Artifact]:
    """inventories/<env>/ : inventaire, group_vars, host_vars et modèle de vault."""
    artifacts: list[Artifact] = []
    env_names = [env.name for env in spec.environments]

    for env in spec.environments:
        base = PurePosixPath("inventories") / env.name
        artifacts.append(
            Artifact(
                path=base / "hosts.yml",
                content=render(
                    "project/inventory/hosts.yml.j2",
                    {"spec": spec, "env": env, "groups": _inventory_groups(spec, env)},
                ),
            )
        )
        artifacts.append(
            Artifact(
                path=base / "group_vars" / "all" / "main.yml",
                content=render(
                    "project/vars/env_all.yml.j2",
                    {
                        "spec": spec,
                        "env": env,
                        "env_names": env_names,
                        "variables": _free_vars(env.group_vars.get("all", {})),
                    },
                ),
            )
        )
        if spec.options.use_vault:
            artifacts.append(
                Artifact(
                    path=base / "group_vars" / "all" / "vault.yml.example",
                    content=render(
                        "project/vars/vault.yml.j2",
                        {"spec": spec, "env": env, "secrets": _vault_secrets(spec, env)},
                    ),
                )
            )
        for group in spec.groups:
            artifacts.append(
                Artifact(
                    path=base / "group_vars" / f"{group.name}.yml",
                    content=render(
                        "project/vars/env_group.yml.j2",
                        {
                            "spec": spec,
                            "env": env,
                            "group": group,
                            "variables": _free_vars(env.group_vars.get(group.name, {})),
                        },
                    ),
                )
            )
        for host in env.all_hosts():
            artifacts.append(
                Artifact(
                    path=base / "host_vars" / f"{host.name}.yml",
                    content=render(
                        "project/vars/host.yml.j2",
                        {
                            "spec": spec,
                            "env": env,
                            "host": host,
                            "variables": _free_vars(host.vars),
                        },
                    ),
                )
            )
    return artifacts


def _inventory_groups(spec: ProjectSpec, env: EnvironmentSpec) -> list[dict[str, Any]]:
    """Décrit chaque groupe du projet pour l'inventaire d'un environnement."""
    return [
        {
            "name": group.name,
            "description": group.description,
            "roles": group.roles,
            "hosts": sorted(env.hosts.get(group.name, []), key=lambda host: host.name),
        }
        for group in spec.groups
    ]


def _vault_secrets(spec: ProjectSpec, env: EnvironmentSpec) -> list[dict[str, str]]:
    """Déduit les secrets attendus par les rôles sélectionnés.

    Aujourd'hui seul ``postgresql`` déclare des mots de passe ; la liste reste
    ouverte pour les rôles ajoutés ensuite.
    """
    secrets: list[dict[str, str]] = []
    if "postgresql" in spec.used_roles():
        for user in spec.role_options("postgresql").get("db_users", []):
            variable = user.get("password_var")
            if variable:
                secrets.append(
                    {
                        "name": variable,
                        "description": (
                            f"Mot de passe du rôle PostgreSQL « {user.get('name', '?')} » "
                            f"en environnement « {env.name} »."
                        ),
                        "placeholder": "CHANGEZ-MOI",
                    }
                )
    if not secrets:
        secrets.append(
            {
                "name": "vault_example_secret",
                "description": (
                    "Exemple de secret. Remplacez-le par les vôtres, un par ligne, "
                    "chacun précédé d'un commentaire."
                ),
                "placeholder": "CHANGEZ-MOI",
            }
        )
    return secrets


# ---------------------------------------------------------------------------
# Playbooks et rôles
# ---------------------------------------------------------------------------


def _playbooks(spec: ProjectSpec) -> list[Artifact]:
    """site.yml, un playbook par groupe et le test de connectivité."""
    artifacts = [
        Artifact(
            path=PurePosixPath("playbooks/site.yml"),
            content=render("project/playbooks/site.yml.j2", {"spec": spec, "groups": spec.groups}),
        ),
        Artifact(
            path=PurePosixPath("playbooks/ping.yml"),
            content=render("project/playbooks/ping.yml.j2", {"spec": spec}),
        ),
    ]
    for group in spec.groups:
        artifacts.append(
            Artifact(
                path=PurePosixPath(f"playbooks/{group.name}.yml"),
                content=render(
                    "project/playbooks/group.yml.j2",
                    {
                        "spec": spec,
                        "group": group,
                        "roles": [get_role(name) for name in group.roles],
                    },
                ),
            )
        )
    return artifacts


def _roles(spec: ProjectSpec) -> list[Artifact]:
    """Arborescence complète de chaque rôle réellement appliqué."""
    example_group = _first_group_using(spec)
    artifacts: list[Artifact] = []
    for role_name in spec.ordered_used_roles():
        artifacts.extend(
            plan_role(
                role_name,
                author=spec.author or spec.project_name,
                os_family=spec.os_family,
                example_group=example_group.get(role_name, spec.groups[0].name),
            )
        )
    return artifacts


def _first_group_using(spec: ProjectSpec) -> dict[str, str]:
    """Associe chaque rôle au premier groupe qui l'applique (exemple du README)."""
    mapping: dict[str, str] = {}
    for group in spec.groups:
        for role_name in group.roles:
            mapping.setdefault(role_name, group.name)
    return mapping

