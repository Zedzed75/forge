"""Définition du rôle ``users`` : comptes locaux, sudo et clés SSH."""

from __future__ import annotations

from ansible_forge.catalog.definition import OptionKind, RoleDefinition, RoleOption

USER_FIELDS = (
    RoleOption(
        name="name",
        question="Nom du compte",
        description="Nom de connexion du compte local.",
        allowed="1 à 32 caractères, minuscules, chiffres, '_' ou '-'.",
        default="",
        kind=OptionKind.TEXT,
    ),
    RoleOption(
        name="groups",
        question="Groupes secondaires (séparés par des virgules)",
        description="Groupes secondaires auxquels le compte est ajouté.",
        allowed="Liste de noms de groupes existants ou créés par ailleurs.",
        default=[],
        kind=OptionKind.LIST,
    ),
    RoleOption(
        name="sudo",
        question="Accès sudo sans mot de passe ?",
        description="Ajoute une règle sudoers NOPASSWD pour ce compte.",
        allowed="true ou false.",
        default=False,
        kind=OptionKind.BOOL,
    ),
    RoleOption(
        name="shell",
        question="Shell de connexion",
        description="Shell attribué au compte.",
        allowed="Chemin absolu vers un shell présent dans /etc/shells.",
        default="/bin/bash",
        kind=OptionKind.TEXT,
    ),
    RoleOption(
        name="ssh_public_key",
        question="Clé publique SSH autorisée (vide pour aucune)",
        description="Clé publique installée dans ~/.ssh/authorized_keys.",
        allowed="Clé publique OpenSSH complète, ou chaîne vide.",
        default="",
        kind=OptionKind.TEXT,
    ),
    RoleOption(
        name="state",
        question="État du compte",
        description="Présence ou suppression du compte sur la machine.",
        allowed="present ou absent.",
        default="present",
        kind=OptionKind.CHOICE,
        choices=("present", "absent"),
    ),
)

ROLE = RoleDefinition(
    name="users",
    summary="Comptes locaux : création, groupes secondaires, sudo et clés SSH autorisées.",
    collections=("ansible.posix",),
    handlers=(),
    tags=("users", "security"),
    options=(
        RoleOption(
            name="accounts",
            question="Comptes à gérer",
            description="Liste des comptes locaux gérés par le rôle.",
            allowed="Liste de dictionnaires (name, groups, sudo, shell, ssh_public_key, state).",
            default=[],
            kind=OptionKind.RECORDS,
            fields=USER_FIELDS,
        ),
        RoleOption(
            name="manage_sudoers",
            question="Déployer les règles sudoers ?",
            description="Écrit un fichier dans /etc/sudoers.d pour les comptes marqués sudo.",
            allowed="true ou false.",
            default=True,
            kind=OptionKind.BOOL,
        ),
        RoleOption(
            name="remove_absent_home",
            question="Supprimer le répertoire personnel des comptes 'absent' ?",
            description="Supprime /home/<user> lorsque le compte passe à l'état absent.",
            allowed="true ou false.",
            default=False,
            kind=OptionKind.BOOL,
        ),
    ),
)
