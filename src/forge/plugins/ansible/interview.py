"""Entretien du domaine Ansible (hook `forge_interview`).

Portage de `ansible_forge.prompts.flow` (MIGRATION.md §3). Deux differences de
fond avec l'outil d'origine, toutes deux dues au bloc `service:` partage :

* l'identite du projet et la liste des environnements ne sont plus demandees
  ici — le coeur les a deja obtenues (`forge.interview.service_flow`) et les
  passe dans `service` ;
* la sortie n'est pas un modele mais **la section `ansible:` de forge.yml**,
  c'est-a-dire un dict de types simples, directement serialisable en YAML et
  validable par `AnsibleSpec`.

Ce qui reste ici est ce qu'Ansible seul sait : famille d'OS, connexion SSH,
groupes de machines, inventaire par environnement, options des roles.

Les validateurs de ce module retournent `None | str` (contrat `Validator` du
prompter), la ou ceux de `names.py` levent `ValueError` pour pydantic : les deux
disent la meme chose, mais l'un s'affiche sous un champ et l'autre arrete la
validation du modele. Une reponse acceptee ici ne peut pas etre refusee ensuite.
"""

from __future__ import annotations

import ipaddress
import re
from typing import Any

from forge.interview.prompter import Prompter
from forge.plugins.ansible.catalog.registry import get_role, role_names
from forge.plugins.ansible.interview_roles import ask_role_options
from forge.plugins.ansible.names import (
    GROUP_NAME_RE,
    HOST_NAME_RE,
    MAX_PORT,
    MIN_PORT,
    RESERVED_GROUP_NAMES,
    USER_NAME_RE,
)
from forge.plugins.ansible.spec import OSFamily
from forge.spec.service import Environment, ServiceSpec

#: Groupe propose par defaut pour la premiere question de la boucle.
DEFAULT_GROUP = "webservers"

#: Au-dela, declarer les machines a la main dans forge.yml est plus rapide.
MAX_HOSTS_PER_GROUP = 100

#: Etiquette d'un nom de domaine, pour valider une adresse d'hote.
_FQDN_LABEL_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$", re.IGNORECASE)


def run(prompter: Prompter, service: ServiceSpec) -> dict[str, Any] | None:
    """Deroule l'entretien Ansible et retourne la section `ansible:` de forge.yml.

    Retourne `None` si l'utilisateur declare zero groupe : sans groupe il n'y a
    ni inventaire ni playbook, donc rien a generer. Le coeur a deja demande
    *quels* domaines generer, cet entretien ne repose pas la question.
    """
    connection = _ask_connection(prompter)
    groups = _ask_groups(prompter)
    if not groups:
        prompter.note("Aucun groupe déclaré : le domaine Ansible n'est pas généré.")
        return None

    hosts = _ask_hosts(prompter, service.environments, groups)
    roles = _ask_roles(prompter, groups)
    options = _ask_generation_options(prompter)

    # L'ordre des cles est celui des champs d'AnsibleSpec : forge.yml se lit
    # alors dans le meme ordre que le modele qui le valide.
    return {
        **connection,
        "options": options,
        "groups": groups,
        "hosts": hosts,
        "roles": roles,
    }


def _ask_connection(prompter: Prompter) -> dict[str, Any]:
    """Famille d'OS et parametres de connexion SSH communs a toutes les machines."""
    prompter.note("── Machines cibles et connexion ──")
    os_family = prompter.select(
        "Famille de système d'exploitation cible",
        [
            (OSFamily.DEBIAN.value, "Debian / Ubuntu"),
            (OSFamily.REDHAT.value, "RHEL / Rocky / Fedora"),
        ],
        default=OSFamily.DEBIAN.value,
    )
    remote_user = prompter.text(
        "Compte SSH utilisé par Ansible",
        default="ansible",
        validate=lambda value: _check_pattern(
            value, USER_NAME_RE, "Nom d'utilisateur SSH", "Attendu : un nom de compte POSIX."
        ),
    )
    ssh_port = prompter.text(
        "Port SSH des machines cibles",
        default="22",
        validate=_validate_port,
    )
    become = prompter.confirm("Utiliser sudo (escalade de privilèges) ?", default=True)
    python_interpreter = prompter.text("Interpréteur Python distant", default="auto_silent")

    return {
        "os_family": os_family,
        "remote_user": remote_user.strip(),
        "become": become,
        "ssh_port": int(ssh_port),
        "python_interpreter": python_interpreter.strip(),
    }


def _ask_groups(prompter: Prompter) -> list[dict[str, Any]]:
    """Groupes d'hotes et roles appliques a chacun.

    Une liste vide signifie « pas de projet Ansible » : c'est la seule facon de
    decliner le domaine une fois l'entretien commence, d'ou le premier nom
    laisse facultatif.
    """
    prompter.note("── Groupes de machines ──")
    prompter.note(
        "Un projet Ansible décrit au moins un groupe de machines ; "
        "laisser le premier nom vide abandonne le domaine Ansible."
    )
    catalog = [(name, f"{name} — {get_role(name).summary}") for name in role_names()]
    groups: list[dict[str, Any]] = []
    taken: set[str] = set()

    while True:
        first = not groups
        name = prompter.text(
            f"Nom du groupe n°{len(groups) + 1}",
            default=DEFAULT_GROUP if first else "",
            validate=lambda value, taken=taken, first=first: _validate_group_name(
                value, taken, allow_empty=first
            ),
        ).strip()
        if not name:
            return groups

        description = prompter.text(f"Description du groupe « {name} »", default="").strip()
        roles = prompter.checkbox(
            f"Rôles appliqués au groupe « {name} »", catalog, default=["common"]
        )
        if not roles:
            prompter.note("Aucun rôle choisi : le rôle « common » est appliqué par défaut.")
            roles = ["common"]

        group: dict[str, Any] = {"name": name}
        if description:
            group["description"] = description
        group["roles"] = list(roles)
        groups.append(group)
        taken.add(name)

        if not prompter.confirm("Ajouter un autre groupe ?", default=False):
            return groups


def _ask_hosts(
    prompter: Prompter, environments: list[Environment], groups: list[dict[str, Any]]
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Machines de chaque groupe, environnement par environnement.

    Les environnements viennent du bloc `service:` : l'entretien ne les redemande
    pas, il se contente de les parcourir dans l'ordre de promotion.
    """
    prompter.note("── Machines ──")
    detailed = prompter.confirm(
        "Préciser un port ou un compte SSH spécifique par machine ?", default=False
    )
    hosts: dict[str, dict[str, list[dict[str, Any]]]] = {}

    for environment in environments:
        hosts[environment.name] = {}
        for group in groups:
            entries = _ask_hosts_of_group(prompter, environment, group["name"], detailed)
            if entries:
                hosts[environment.name][group["name"]] = entries
    return hosts


def _ask_hosts_of_group(
    prompter: Prompter, environment: Environment, group: str, detailed: bool
) -> list[dict[str, Any]]:
    """Machines d'un groupe dans un environnement donne."""
    env = environment.name
    count = prompter.text(
        f"Nombre de machines dans « {group} » pour l'environnement « {env} »",
        default="1",
        validate=_validate_count,
    )
    entries: list[dict[str, Any]] = []
    taken: set[str] = set()

    for index in range(1, int(count) + 1):
        name = prompter.text(
            f"  Nom de la machine {index}/{count} ({group}/{env})",
            default=f"{group}-{env}-{index:02d}",
            validate=lambda value, taken=taken: _validate_host_name(value, taken),
        ).strip()
        taken.add(name)
        entry: dict[str, Any] = {
            "name": name,
            # Nouveaute par rapport au legacy : quand l'environnement declare un
            # domaine dans le bloc `service:`, l'adresse par defaut en decoule.
            "ansible_host": prompter.text(
                f"  Adresse IP ou nom de domaine de « {name} »",
                default=f"{name}.{environment.domain}" if environment.domain else "",
                validate=_validate_host_address,
            ).strip(),
        }
        if detailed:
            port = prompter.text(
                f"  Port SSH de « {name} » (vide = valeur du projet)",
                default="",
                validate=lambda value: None if not value.strip() else _validate_port(value),
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
    """Options des roles reellement appliques, dans l'ordre du catalogue."""
    used = {role for group in groups for role in group["roles"]}
    ordered = [name for name in role_names() if name in used]
    if not ordered:
        return []

    prompter.note("── Réglages des rôles ──")
    if not prompter.confirm(
        "Personnaliser les réglages des rôles ? (non = valeurs par défaut documentées)",
        default=False,
    ):
        # `AnsibleSpec` complete les options manquantes avec les defauts du
        # catalogue : citer les roles suffit, la sortie reste complete.
        return [{"name": name} for name in ordered]

    return [
        {"name": name, "options": ask_role_options(prompter, get_role(name))} for name in ordered
    ]


def _ask_generation_options(prompter: Prompter) -> dict[str, Any]:
    """Fichiers annexes a produire en plus des roles et de l'inventaire."""
    prompter.note("── Options de génération ──")
    return {
        "use_vault": prompter.confirm(
            "Générer les modèles de fichiers vault (secrets) ?", default=True
        ),
        "write_lint_config": prompter.confirm(
            "Générer .gitignore, .yamllint et .ansible-lint ?", default=True
        ),
        "write_ci": prompter.confirm(
            "Générer un workflow GitHub Actions exécutant ansible-lint ?", default=False
        ),
    }


# -- validateurs de saisie --------------------------------------------------


def _check_pattern(value: str, pattern: re.Pattern[str], label: str, hint: str) -> str | None:
    """Valide une chaine contre une expression reguliere."""
    if pattern.match(value.strip()):
        return None
    return f"{label} invalide : '{value}'. {hint}"


def _validate_port(value: str) -> str | None:
    """Valide une saisie de port TCP."""
    try:
        parsed = int(value.strip())
    except ValueError:
        return f"Un entier est attendu, reçu : « {value} »."
    if not MIN_PORT <= parsed <= MAX_PORT:
        return f"Le port doit être compris entre {MIN_PORT} et {MAX_PORT}, reçu : {parsed}."
    return None


def _validate_count(value: str) -> str | None:
    """Valide un nombre de machines."""
    if not value.strip().isdigit():
        return f"Un entier positif ou nul est attendu, reçu : « {value} »."
    if int(value) > MAX_HOSTS_PER_GROUP:
        return (
            f"Au-delà de {MAX_HOSTS_PER_GROUP} machines, déclarez-les directement "
            "dans forge.yml."
        )
    return None


def _validate_group_name(value: str, taken: set[str], *, allow_empty: bool = False) -> str | None:
    """Valide un nom de groupe, unicite et noms reserves compris."""
    value = value.strip()
    if allow_empty and not value:
        return None
    error = _check_pattern(
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
    """Valide un nom de machine, unicite comprise."""
    value = value.strip()
    error = _check_pattern(
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


def _validate_host_address(value: str) -> str | None:
    """Valide une adresse d'hote : adresse IP ou nom de domaine."""
    value = value.strip()
    if not value:
        return "L'adresse de l'hôte est obligatoire (adresse IP ou nom de domaine)."
    if _is_ip(value) or _is_fqdn(value):
        return None
    return f"'{value}' n'est ni une adresse IP ni un nom de domaine valide."


def _is_ip(value: str) -> bool:
    """Indique si la chaine est une adresse IPv4 ou IPv6 valide."""
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def _is_fqdn(value: str) -> bool:
    """Indique si la chaine est un nom de domaine syntaxiquement valide."""
    if not value or len(value) > 253:
        return False
    labels = value.rstrip(".").split(".")
    return all(_FQDN_LABEL_RE.match(label) for label in labels)
