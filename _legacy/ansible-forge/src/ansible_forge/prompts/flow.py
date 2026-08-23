"""Questionnaire interactif produisant une :class:`ProjectSpec`.

L'entretien suit l'ordre du design : identité, connexion, environnements,
groupes, machines, options des rôles, options de génération. Toutes les
validations proviennent de :mod:`ansible_forge.validation`, les mêmes que
celles du modèle : une réponse acceptée ici ne peut pas être refusée ensuite.
"""

from __future__ import annotations

from typing import Any

from ansible_forge.catalog.registry import get_role, role_names
from ansible_forge.models.enums import OSFamily
from ansible_forge.models.spec import ProjectSpec
from ansible_forge.prompts.prompter import Prompter
from ansible_forge.prompts.role_questions import ask_role_options
from ansible_forge.validation import (
    ENV_NAME_RE,
    GROUP_NAME_RE,
    HOST_NAME_RE,
    PROJECT_NAME_RE,
    RESERVED_GROUP_NAMES,
    USER_NAME_RE,
    check_host_address,
    check_pattern,
    check_port,
)

#: Environnements proposés par défaut.
DEFAULT_ENVIRONMENTS = ("dev", "staging", "prod")

#: Groupe proposé par défaut lorsque l'utilisateur n'en déclare aucun.
DEFAULT_GROUP = "webservers"


def run_interview(prompter: Prompter, *, default_project_name: str = "mon-projet") -> ProjectSpec:
    """Déroule l'entretien complet et retourne la spécification obtenue."""
    identity = _ask_identity(prompter, default_project_name)
    connection = _ask_connection(prompter)
    environments = _ask_environments(prompter)
    groups = _ask_groups(prompter)
    hosts = _ask_hosts(prompter, environments, groups)
    roles = _ask_roles(prompter, groups)
    options = _ask_generation_options(prompter)

    return ProjectSpec.model_validate(
        {
            **identity,
            **connection,
            "groups": groups,
            "environments": [
                {"name": name, "hosts": hosts[name], "group_vars": {}} for name in environments
            ],
            "roles": roles,
            "options": options,
        }
    )


def _ask_identity(prompter: Prompter, default_project_name: str) -> dict[str, Any]:
    """Nom, description et auteur du projet."""
    prompter.note("── Identité du projet ──")
    name = prompter.text(
        "Nom du projet",
        default=default_project_name,
        validate=lambda value: check_pattern(
            value,
            PROJECT_NAME_RE,
            "Nom de projet",
            "Attendu : minuscules, chiffres, '-' et '_', 2 à 63 caractères.",
        ),
    )
    return {
        "project_name": name,
        "description": prompter.text("Description courte du projet", default=""),
        "author": prompter.text("Auteur ou équipe responsable", default=""),
    }


def _ask_connection(prompter: Prompter) -> dict[str, Any]:
    """Famille d'OS et paramètres de connexion SSH."""
    prompter.note("── Machines cibles et connexion ──")
    os_family = prompter.select(
        "Famille de système d'exploitation cible",
        [(OSFamily.DEBIAN.value, "Debian / Ubuntu"), (OSFamily.REDHAT.value, "RHEL / Rocky / Fedora")],
        default=OSFamily.DEBIAN.value,
    )
    remote_user = prompter.text(
        "Compte SSH utilisé par Ansible",
        default="ansible",
        validate=lambda value: check_pattern(
            value, USER_NAME_RE, "Nom d'utilisateur SSH", "Attendu : un nom de compte POSIX."
        ),
    )
    ssh_port = prompter.text(
        "Port SSH des machines cibles",
        default="22",
        validate=_port_validator,
    )
    return {
        "os_family": os_family,
        "remote_user": remote_user,
        "ssh_port": int(ssh_port),
        "become": prompter.confirm("Utiliser sudo (escalade de privilèges) ?", default=True),
        "python_interpreter": prompter.text(
            "Interpréteur Python distant", default="auto_silent"
        ),
    }


def _ask_environments(prompter: Prompter) -> list[str]:
    """Liste des environnements du projet, dans l'ordre de déclaration."""
    prompter.note("── Environnements ──")
    selected = prompter.checkbox(
        "Environnements à générer",
        [(name, name) for name in DEFAULT_ENVIRONMENTS],
        default=list(DEFAULT_ENVIRONMENTS),
    )
    extra = prompter.text(
        "Environnements supplémentaires (séparés par des virgules, vide si aucun)",
        default="",
        validate=lambda value: _validate_names(
            value, ENV_NAME_RE, "Nom d'environnement", "Attendu : minuscules, chiffres et '_'."
        ),
    )
    names = list(selected) + [item.strip() for item in extra.split(",") if item.strip()]
    if not names:
        prompter.note("Aucun environnement choisi : « dev » est ajouté par défaut.")
        names = ["dev"]
    return list(dict.fromkeys(names))


def _ask_groups(prompter: Prompter) -> list[dict[str, Any]]:
    """Groupes d'hôtes et rôles appliqués à chacun."""
    prompter.note("── Groupes de machines ──")
    catalog = [(name, f"{name} — {get_role(name).summary}") for name in role_names()]
    groups: list[dict[str, Any]] = []
    taken: set[str] = set()

    while True:
        default_name = DEFAULT_GROUP if not groups else ""
        name = prompter.text(
            f"Nom du groupe n°{len(groups) + 1}",
            default=default_name,
            validate=lambda value, taken=taken: _validate_group_name(value, taken),
        )
        description = prompter.text(f"Description du groupe « {name} »", default="")
        roles = prompter.checkbox(
            f"Rôles appliqués au groupe « {name} »", catalog, default=["common"]
        )
        if not roles:
            prompter.note("Aucun rôle choisi : le rôle « common » est appliqué par défaut.")
            roles = ["common"]

        groups.append({"name": name, "description": description, "roles": roles, "vars": {}})
        taken.add(name)
        if not prompter.confirm("Ajouter un autre groupe ?", default=False):
            return groups


def _ask_hosts(
    prompter: Prompter, environments: list[str], groups: list[dict[str, Any]]
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Machines de chaque groupe, environnement par environnement."""
    prompter.note("── Machines ──")
    detailed = prompter.confirm(
        "Préciser un port ou un compte SSH spécifique par machine ?", default=False
    )
    hosts: dict[str, dict[str, list[dict[str, Any]]]] = {}

    for env in environments:
        hosts[env] = {}
        for group in groups:
            entries = _ask_hosts_of_group(prompter, env, group["name"], detailed)
            if entries:
                hosts[env][group["name"]] = entries
    return hosts


def _ask_hosts_of_group(
    prompter: Prompter, env: str, group: str, detailed: bool
) -> list[dict[str, Any]]:
    """Machines d'un groupe dans un environnement donné."""
    count = prompter.text(
        f"Nombre de machines dans « {group} » pour l'environnement « {env} »",
        default="1",
        validate=_count_validator,
    )
    entries: list[dict[str, Any]] = []
    taken: set[str] = set()

    for index in range(1, int(count) + 1):
        name = prompter.text(
            f"  Nom de la machine {index}/{count} ({group}/{env})",
            default=f"{group}-{env}-{index:02d}",
            validate=lambda value, taken=taken: _validate_host_name(value, taken),
        )
        taken.add(name)
        entry: dict[str, Any] = {
            "name": name,
            "ansible_host": prompter.text(
                f"  Adresse IP ou nom de domaine de « {name} »",
                default="",
                validate=check_host_address,
            ),
        }
        if detailed:
            port = prompter.text(
                f"  Port SSH de « {name} » (vide = valeur du projet)",
                default="",
                validate=lambda value: None if not value.strip() else _port_validator(value),
            )
            user = prompter.text(
                f"  Compte SSH de « {name} » (vide = valeur du projet)", default=""
            )
            if port.strip():
                entry["ansible_port"] = int(port)
            if user.strip():
                entry["ansible_user"] = user.strip()
        entries.append(entry)
    return entries


def _ask_roles(prompter: Prompter, groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Options des rôles réellement appliqués, dans l'ordre du catalogue."""
    used = {role for group in groups for role in group["roles"]}
    ordered = [name for name in role_names() if name in used]
    if not ordered:
        return []

    prompter.note("── Réglages des rôles ──")
    if not prompter.confirm(
        "Personnaliser les réglages des rôles ? (non = valeurs par défaut documentées)",
        default=False,
    ):
        return [{"name": name} for name in ordered]

    return [
        {"name": name, "options": ask_role_options(prompter, get_role(name))} for name in ordered
    ]


def _ask_generation_options(prompter: Prompter) -> dict[str, Any]:
    """Fichiers annexes à produire."""
    prompter.note("── Options de génération ──")
    return {
        "use_vault": prompter.confirm(
            "Générer les modèles de fichiers vault (secrets) ?", default=True
        ),
        "write_lint_config": prompter.confirm(
            "Générer .gitignore, .yamllint et .ansible-lint ?", default=True
        ),
        "embed_spec": prompter.confirm(
            "Copier forge.yml dans le projet généré (rejouabilité) ?", default=True
        ),
        "write_ci": prompter.confirm(
            "Générer un workflow GitHub Actions exécutant ansible-lint ?", default=False
        ),
    }


def _port_validator(value: str) -> str | None:
    """Valide une saisie de port."""
    try:
        parsed = int(value.strip())
    except ValueError:
        return f"Un entier est attendu, reçu : « {value} »."
    return check_port(parsed)


def _count_validator(value: str) -> str | None:
    """Valide un nombre de machines."""
    if not value.strip().isdigit():
        return f"Un entier positif ou nul est attendu, reçu : « {value} »."
    if int(value) > 100:
        return "Au-delà de 100 machines, déclarez-les directement dans forge.yml."
    return None


def _validate_group_name(value: str, taken: set[str]) -> str | None:
    """Valide un nom de groupe, unicité comprise."""
    error = check_pattern(
        value,
        GROUP_NAME_RE,
        "Nom de groupe",
        "Attendu : minuscules, chiffres et '_' (le tiret est interdit).",
    )
    if error:
        return error
    if value in RESERVED_GROUP_NAMES:
        return f"Le nom « {value} » est réservé par Ansible."
    if value in taken:
        return f"Le groupe « {value} » est déjà déclaré."
    return None


def _validate_host_name(value: str, taken: set[str]) -> str | None:
    """Valide un nom de machine, unicité comprise."""
    error = check_pattern(
        value,
        HOST_NAME_RE,
        "Nom d'hôte",
        "Attendu : minuscules, chiffres, '.', '-' et '_'.",
    )
    if error:
        return error
    if value in taken:
        return f"La machine « {value} » est déjà déclarée dans cet environnement."
    return None


def _validate_names(value: str, pattern, label: str, hint: str) -> str | None:
    """Valide une saisie « a, b, c » contre une expression régulière."""
    for item in (part.strip() for part in value.split(",")):
        if not item:
            continue
        error = check_pattern(item, pattern, label, hint)
        if error:
            return error
    return None
