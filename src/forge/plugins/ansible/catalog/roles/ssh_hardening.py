"""Définition du rôle ``ssh_hardening`` : durcissement du serveur OpenSSH."""

from __future__ import annotations

from forge.plugins.ansible.catalog.definition import OptionKind, RoleDefinition, RoleOption

ROLE = RoleDefinition(
    name="ssh_hardening",
    summary="Durcissement OpenSSH : connexion root, authentification par mot de passe, limites.",
    collections=(),
    handlers=("Redémarrer le service SSH",),
    tags=("ssh", "security", "hardening"),
    options=(
        RoleOption(
            name="port",
            question="Port d'écoute du serveur SSH",
            description="Port TCP sur lequel sshd écoute.",
            allowed="Entier de 1 à 65535.",
            default=22,
            kind=OptionKind.INT,
        ),
        RoleOption(
            name="permit_root_login",
            question="Connexion root autorisée ?",
            description="Valeur de la directive PermitRootLogin.",
            allowed="yes, no, prohibit-password ou forced-commands-only.",
            default="prohibit-password",
            kind=OptionKind.CHOICE,
            choices=("yes", "no", "prohibit-password", "forced-commands-only"),
        ),
        RoleOption(
            name="password_authentication",
            question="Autoriser l'authentification par mot de passe ?",
            description="Valeur de la directive PasswordAuthentication.",
            allowed="true ou false.",
            default=False,
            kind=OptionKind.BOOL,
        ),
        RoleOption(
            name="pubkey_authentication",
            question="Autoriser l'authentification par clé publique ?",
            description="Valeur de la directive PubkeyAuthentication.",
            allowed="true ou false.",
            default=True,
            kind=OptionKind.BOOL,
        ),
        RoleOption(
            name="x11_forwarding",
            question="Autoriser le transfert X11 ?",
            description="Valeur de la directive X11Forwarding.",
            allowed="true ou false.",
            default=False,
            kind=OptionKind.BOOL,
        ),
        RoleOption(
            name="max_auth_tries",
            question="Nombre maximal de tentatives d'authentification",
            description="Valeur de la directive MaxAuthTries.",
            allowed="Entier de 1 à 10.",
            default=3,
            kind=OptionKind.INT,
        ),
        RoleOption(
            name="allow_groups",
            question="Groupes autorisés à se connecter (vide = tous)",
            description="Valeur de la directive AllowGroups ; vide désactive la directive.",
            allowed="Liste de noms de groupes système.",
            default=[],
            kind=OptionKind.LIST,
        ),
    ),
)
