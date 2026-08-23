"""Règles de validation partagées.

Ce module est la source unique de vérité des contraintes de nommage : il est
utilisé aussi bien par le modèle pydantic (validation stricte, levée
d'exception) que par le questionnaire interactif (validation immédiate, message
d'erreur affiché sous le champ). Les deux chemins ne peuvent donc pas diverger.

Note d'architecture : le design initial plaçait ces règles dans
``prompts/validators.py``. Elles ont été remontées ici pour éviter que la couche
modèle ne dépende de la couche interactive.
"""

from __future__ import annotations

import ipaddress
import re

#: Nom de projet : minuscules, chiffres, tiret et souligné, 2 à 63 caractères.
PROJECT_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{1,62}$")

#: Nom d'environnement : pas de tiret, utilisé comme nom de répertoire et de groupe.
ENV_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")

#: Nom de groupe Ansible : les tirets sont interdits dans les noms de groupes.
GROUP_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]{0,63}$")

#: Nom d'hôte d'inventaire : tirets et points autorisés.
HOST_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,62}$")

#: Nom de compte système POSIX.
USER_NAME_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")

#: Nom de variable Ansible.
VAR_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]*$")

#: Étiquette d'un nom de domaine.
_FQDN_LABEL_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$", re.IGNORECASE)

#: Noms de groupes réservés par Ansible, interdits comme groupe utilisateur.
RESERVED_GROUP_NAMES = frozenset({"all", "ungrouped", "local"})

MIN_PORT = 1
MAX_PORT = 65535


def is_valid_fqdn(value: str) -> bool:
    """Indique si la chaîne est un nom de domaine syntaxiquement valide."""
    if not value or len(value) > 253:
        return False
    labels = value.rstrip(".").split(".")
    return all(_FQDN_LABEL_RE.match(label) for label in labels)


def is_valid_ip(value: str) -> bool:
    """Indique si la chaîne est une adresse IPv4 ou IPv6 valide."""
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def check_host_address(value: str) -> str | None:
    """Valide une adresse d'hôte (IP ou FQDN).

    Retourne ``None`` si la valeur est acceptable, sinon le message d'erreur.
    """
    if not value:
        return "L'adresse de l'hôte est obligatoire (adresse IP ou nom de domaine)."
    if is_valid_ip(value) or is_valid_fqdn(value):
        return None
    return f"'{value}' n'est ni une adresse IP ni un nom de domaine valide."


def check_pattern(value: str, pattern: re.Pattern[str], label: str, hint: str) -> str | None:
    """Valide une chaîne contre une expression régulière.

    Retourne ``None`` si la valeur est acceptable, sinon le message d'erreur.
    """
    if pattern.match(value):
        return None
    return f"{label} invalide : '{value}'. {hint}"


def check_port(value: int) -> str | None:
    """Valide un numéro de port TCP/UDP.

    Retourne ``None`` si la valeur est acceptable, sinon le message d'erreur.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        return f"Le port doit être un entier, reçu : {value!r}."
    if MIN_PORT <= value <= MAX_PORT:
        return None
    return f"Le port doit être compris entre {MIN_PORT} et {MAX_PORT}, reçu : {value}."


def find_duplicates(values: list[str]) -> list[str]:
    """Retourne les valeurs apparaissant plus d'une fois, triées."""
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)
