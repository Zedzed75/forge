"""Definition of the ``ssh_hardening`` role: hardening of the OpenSSH server."""

from __future__ import annotations

from forge.plugins.ansible.catalog.definition import OptionKind, RoleDefinition, RoleOption

ROLE = RoleDefinition(
    name="ssh_hardening",
    summary="OpenSSH hardening: root login, password authentication, limits.",
    collections=(),
    handlers=("Restart the SSH service",),
    tags=("ssh", "security", "hardening"),
    options=(
        RoleOption(
            name="port",
            question="Listening port of the SSH server",
            description="TCP port sshd listens on.",
            allowed="Integer from 1 to 65535.",
            default=22,
            kind=OptionKind.INT,
        ),
        RoleOption(
            name="permit_root_login",
            question="Root login allowed?",
            description="Value of the PermitRootLogin directive.",
            allowed="yes, no, prohibit-password or forced-commands-only.",
            default="prohibit-password",
            kind=OptionKind.CHOICE,
            choices=("yes", "no", "prohibit-password", "forced-commands-only"),
        ),
        RoleOption(
            name="password_authentication",
            question="Allow password authentication?",
            description="Value of the PasswordAuthentication directive.",
            allowed="true or false.",
            default=False,
            kind=OptionKind.BOOL,
        ),
        RoleOption(
            name="pubkey_authentication",
            question="Allow public key authentication?",
            description="Value of the PubkeyAuthentication directive.",
            allowed="true or false.",
            default=True,
            kind=OptionKind.BOOL,
        ),
        RoleOption(
            name="x11_forwarding",
            question="Allow X11 forwarding?",
            description="Value of the X11Forwarding directive.",
            allowed="true or false.",
            default=False,
            kind=OptionKind.BOOL,
        ),
        RoleOption(
            name="max_auth_tries",
            question="Maximum number of authentication attempts",
            description="Value of the MaxAuthTries directive.",
            allowed="Integer from 1 to 10.",
            default=3,
            kind=OptionKind.INT,
        ),
        RoleOption(
            name="allow_groups",
            question="Groups allowed to log in (empty = all)",
            description="Value of the AllowGroups directive; empty disables the directive.",
            allowed="List of system group names.",
            default=[],
            kind=OptionKind.LIST,
        ),
    ),
)
